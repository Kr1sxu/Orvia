"""受信本地嵌入工作器：独立进程、固定工件、离线加载和可终止资源预算。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from uuid import uuid4

import httpx
import psutil

from .model import FILES, MODEL, REVISION, SIGNATURE

PREPARE_SECONDS = 180


class EmbeddingError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def ordinary(path: Path, directory=False):
    """检查整条路径，拒绝Windows联接/重解析点；不接受网络路径或相对目录。"""
    if not path.is_absolute() or str(path).startswith("\\\\"):
        raise EmbeddingError("MODEL_PATH_INVALID")
    for item in reversed([path, *path.parents]):
        info = item.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise EmbeddingError("MODEL_PATH_INVALID")
    info = path.stat()
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise EmbeddingError("MODEL_PATH_INVALID")


def verify(directory: Path):
    """逐文件大小和官方内容摘要验证，拒绝额外代码/配置文件参与加载。"""
    ordinary(directory, True)
    if set(item.name for item in directory.iterdir()) != set(FILES):
        raise EmbeddingError("MODEL_CHECKSUM_FAILED")
    for name, (size, algorithm, expected) in FILES.items():
        path = directory / name
        ordinary(path)
        if path.stat().st_size != size:
            raise EmbeddingError("MODEL_CHECKSUM_FAILED")
        digest = hashlib.sha256() if algorithm == "sha256" else hashlib.sha1()
        if algorithm == "git-sha1":
            digest.update(f"blob {size}\0".encode())
        # 流式摘要避免一次读入1.1GiB权重；读完复核句柄身份，拒绝准备期间替换。
        before = path.stat()
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            if (opened.st_ino, opened.st_size) != (before.st_ino, before.st_size):
                raise EmbeddingError("MODEL_CHECKSUM_FAILED")
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        after = path.stat()
        if digest.hexdigest() != expected or (before.st_ino, before.st_mtime_ns) != (after.st_ino, after.st_mtime_ns):
            raise EmbeddingError("MODEL_CHECKSUM_FAILED")


class LocalEmbedder:
    signature = SIGNATURE

    def __init__(self, data_directory: Path):
        self.directory = data_directory / "models" / "qwen3-embedding-0.6b" / REVISION
        self.config = data_directory / "embedding-model.json"
        self.process = None
        self.reason = "MODEL_MISSING"
        self.lock = asyncio.Lock()
        self.peak_bytes = 0
        self.children: dict[int, psutil.Process] = {}

    def status(self):
        ready = self.process is not None and self.process.returncode is None
        return {"ready": ready, "reason": None if ready else self.reason or "MODEL_WORKER_FAILED", "signature": self.signature,
                "peak_bytes": self.peak_bytes, "memory_limit_bytes": 6 * 1024**3,
                "threads": 4, "batch": 4, "max_tokens": 1024}

    async def close(self):
        if self.process is not None:
            # Windows虚拟环境python.exe可能是启动器；关闭全部已核验自有后代。
            try:
                for child in psutil.Process(self.process.pid).children(recursive=True):
                    self.children[child.pid] = child
            except psutil.NoSuchProcess:
                pass
            for child in reversed(list(self.children.values())):
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            self.children.clear()
            if self.process.stdin is not None:
                self.process.stdin.close()
            if self.process.returncode is None:
                self.process.kill()
            await self.process.wait()
            self.process = None

    def _memory(self):
        """RSS合计包括虚拟环境启动器和自有后代，不把4MiB启动器当模型占用。"""
        parent = psutil.Process(self.process.pid)
        for child in parent.children(recursive=True):
            self.children[child.pid] = child
        if len(self.children) > 4:
            raise EmbeddingError("MODEL_PROCESS_LIMIT")
        rss = parent.memory_info().rss
        for pid, child in list(self.children.items()):
            try:
                rss += child.memory_info().rss
            except psutil.NoSuchProcess:
                del self.children[pid]
        return rss

    async def _read(self, timeout):
        """逐次监控独立工作器RSS与期限；超限终止，不接受晚到结果或自动重试。"""
        pending = asyncio.create_task(self.process.stdout.readline())
        start = asyncio.get_running_loop().time()
        try:
            while not pending.done():
                if asyncio.get_running_loop().time() - start > timeout:
                    raise EmbeddingError("MODEL_TIMEOUT")
                try:
                    rss = self._memory()
                except psutil.NoSuchProcess:
                    raise EmbeddingError("MODEL_WORKER_FAILED") from None
                except psutil.AccessDenied:
                    raise EmbeddingError("MODEL_RESOURCE_UNAVAILABLE") from None
                self.peak_bytes = max(self.peak_bytes, rss)
                if rss > 6 * 1024**3:
                    raise EmbeddingError("MODEL_MEMORY_LIMIT")
                await asyncio.sleep(.1)
            data = await pending
            if not data or len(data) > 256 * 1024:
                raise EmbeddingError("MODEL_WORKER_FAILED")
            value = json.loads(data)
            if value.get("error"):
                raise EmbeddingError(value["error"])
            return value
        except BaseException:
            # 调用方超时/取消同样终止工作器，不能把晚到响应配给下一次查询。
            pending.cancel()
            await self.close()
            raise

    async def prepare(self, path: str | None = None):
        """准备总期限包含排队、两次父进程核验与工作器预加载，不叠加阶段期限。"""
        try:
            return await asyncio.wait_for(self._prepare(path), PREPARE_SECONDS)
        except asyncio.TimeoutError:
            self.reason = "MODEL_TIMEOUT"
            await self.close()
            return self.status()

    async def _prepare(self, path: str | None = None):
        async with self.lock:
            await self.close()
            try:
                directory = Path(path) if path else self.directory
                await asyncio.wait_for(asyncio.to_thread(verify, directory), 60)
                # 子进程不继承模型Key、代理或用户Python配置；全部HF入口强制离线。
                env = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "TEMP", "TMP") if key in os.environ}
                env.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1",
                            "TOKENIZERS_PARALLELISM": "false", "OMP_NUM_THREADS": "4", "MKL_NUM_THREADS": "4"})
                self.process = await asyncio.create_subprocess_exec(sys.executable, "-I", "-u", "-X", "utf8", "-m",
                    "orvia_backend.retrieval.worker", str(directory), env=env,
                    stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL, limit=256 * 1024,
                    **({"creationflags": 0x08000000} if os.name == "nt" else {}))
                value = await self._read(120)
                if value != {"ready": True, "signature": SIGNATURE}:
                    raise EmbeddingError("MODEL_WORKER_FAILED")
                # ready不是事实核验：加载后再次校验工件，拒绝加载期间替换的版本。
                await asyncio.wait_for(asyncio.to_thread(verify, directory), 60)
                self.config.parent.mkdir(parents=True, exist_ok=True)
                ordinary(self.config.parent, True)
                if os.path.lexists(self.config):
                    ordinary(self.config)
                temporary = self.config.parent / (uuid4().hex + ".model-config")
                try:
                    with temporary.open("x", encoding="utf-8") as stream:
                        json.dump({"path": str(directory), "signature": SIGNATURE}, stream)
                    ordinary(self.config.parent, True)
                    if os.path.lexists(self.config):
                        ordinary(self.config)
                    temporary.replace(self.config)
                finally:
                    if temporary.exists():
                        temporary.unlink()
                self.reason = None
            except asyncio.CancelledError:
                self.reason = "MODEL_INTERRUPTED"
                await self.close()
                raise
            except (OSError, ValueError, asyncio.TimeoutError) as error:
                self.reason = error.code if isinstance(error, EmbeddingError) else "MODEL_UNAVAILABLE"
                await self.close()
            return self.status()

    async def restore(self):
        if os.path.lexists(self.config):
            try:
                ordinary(self.config)
                if self.config.stat().st_size > 4096:
                    raise EmbeddingError("MODEL_CONFIG_INVALID")
                value = json.loads(self.config.read_text(encoding="utf-8"))
                if set(value) == {"path", "signature"} and value["signature"] == SIGNATURE:
                    return await self.prepare(value["path"])
            except (OSError, ValueError):
                self.reason = "MODEL_CHECKSUM_FAILED"
        return self.status()

    async def embed(self, texts: list[str], query: bool = False):
        if not texts or len(texts) > 8 or any(not isinstance(t, str) or not t.strip() or len(t) > 600 for t in texts):
            raise EmbeddingError("MODEL_INPUT_LIMIT")
        async with self.lock:
            if not self.status()["ready"]:
                raise EmbeddingError(self.reason or "MODEL_UNAVAILABLE")
            try:
                self.process.stdin.write((json.dumps({"texts": texts, "query": query}, ensure_ascii=False) + "\n").encode("utf-8"))
                await self.process.stdin.drain()
                value = await self._read(30)
                if set(value) != {"vectors"}:
                    raise EmbeddingError("MODEL_WORKER_FAILED")
                return value["vectors"]
            except (OSError, ValueError) as error:
                self.reason = error.code if isinstance(error, EmbeddingError) else "MODEL_WORKER_FAILED"
                await self.close()
                raise EmbeddingError(self.reason) from None

    async def download(self):
        """只从主进程原生确认后的固定方法调用；不会在embed/search中触发。"""
        if self.directory.exists():
            # 已有私有文件不能覆盖；有效工件可直接准备，损坏工件明确失败。
            return await self.prepare()
        # 先检查已存在祖先再逐层创建，不沿用户替换的联接写入其它目录。
        missing, ancestor = [], self.directory.parent
        while not ancestor.exists():
            missing.append(ancestor)
            ancestor = ancestor.parent
        ordinary(ancestor, True)
        for parent in reversed(missing):
            parent.mkdir()
            ordinary(parent, True)
        staging = self.directory.parent / ("download-" + uuid4().hex)
        staging.mkdir()
        ordinary(staging, True)
        try:
            async def https_only(response):
                if response.url.scheme != "https" or (response.is_redirect and response.url.join(response.headers["location"]).scheme != "https"):
                    raise EmbeddingError("MODEL_DOWNLOAD_SCHEME")
            # 仅下载沿用既有HTTPS证书/代理配置，始终校验证书；不改系统或Git配置。
            # 推理工作器仍剥除代理、强制离线，不发送资料或模型Key。
            async with asyncio.timeout(900), httpx.AsyncClient(follow_redirects=True, timeout=30, trust_env=True,
                                                             event_hooks={"response": [https_only]}) as client:
                for name, (size, _, _) in FILES.items():
                    temporary = staging / (uuid4().hex + ".part")
                    try:
                        count = 0
                        async with client.stream("GET", f"https://huggingface.co/{MODEL}/resolve/{REVISION}/{name}") as response:
                            response.raise_for_status()
                            with temporary.open("xb") as stream:
                                async for block in response.aiter_bytes(1024 * 1024):
                                    count += len(block)
                                    if count > size:
                                        raise EmbeddingError("MODEL_DOWNLOAD_LIMIT")
                                    stream.write(block)
                        if count != size:
                            raise EmbeddingError("MODEL_CHECKSUM_FAILED")
                        ordinary(staging, True)
                        temporary.rename(staging / name)
                    finally:
                        if temporary.exists():
                            temporary.unlink()
            await asyncio.to_thread(verify, staging)
            ordinary(self.directory.parent, True)
            staging.rename(self.directory)
        except (httpx.HTTPError, OSError, ValueError, TimeoutError):
            # 已加载其它目录的同版本工作器不能掩盖本次下载失败；用户可显式重新加载。
            await self.close()
            self.reason = "MODEL_DOWNLOAD_FAILED"
            return self.status()
        finally:
            # 仅清理由本次创建的已知普通文件，不递归删除、不触碰已有模型。
            if staging.exists():
                ordinary(staging, True)
                for name in FILES:
                    file = staging / name
                    if file.exists():
                        ordinary(file)
                        file.unlink()
                staging.rmdir()
        return await self.prepare()
