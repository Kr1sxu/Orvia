"""旧 .tmp/.log 逐项计划、隔离和受限恢复；永不把移动量称为释放空间。"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from ..computer.paths import PathPolicy, ToolError, _reparse, sensitive


AGE_SECONDS = 30 * 24 * 3600
RESTORE_SECONDS = AGE_SECONDS
MAX_SCAN = 500
MAX_ITEMS = 50
MAX_BYTES = 100 * 1024 * 1024
MAX_FILE = 10 * 1024 * 1024


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _identity(path: Path) -> dict:
    info = path.stat()
    return {"dev": info.st_dev, "ino": info.st_ino, "size": info.st_size,
            "mtime_ns": info.st_mtime_ns, "sha256": _hash(path)}


def _revision(plan: dict) -> str:
    return hashlib.sha256(json.dumps(plan, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _not_busy(path: Path) -> bool:
    """Windows 上尝试独占打开，已被其他程序占用或不可读的文件不进入执行。"""
    if os.name != "nt":
        return True
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                   wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    handle = kernel.CreateFileW(str(path), 0x80000000, 0, None, 3, 0x80, None)
    if handle == wintypes.HANDLE(-1).value:
        return False
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle(handle)
    return True


def _current_local_app_data() -> Path:
    """从 Windows 当前账户已知文件夹取得固定白名单根，不信任清理请求中的路径。"""
    if os.name != "nt":
        raise ToolError("CLEANUP_UNAVAILABLE", "首批清理仅支持 Windows 当前账户")
    import ctypes
    from ctypes import wintypes
    buffer = ctypes.create_unicode_buffer(32768)
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    shell.SHGetFolderPathW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR]
    if shell.SHGetFolderPathW(None, 0x001C, None, 0, buffer) != 0:
        raise ToolError("CLEANUP_UNAVAILABLE", "无法确定当前用户临时目录")
    return Path(buffer.value)


class CleanupService:
    """仅使用当前用户 LOCALAPPDATA/Temp；测试可注入同结构合成目录。"""

    def __init__(self, store, local_base: Path | None = None):
        self.store = store
        self.local_base = local_base if local_base is not None else _current_local_app_data()

    async def open(self):
        async with self.store._lock:
            db = self.store._db()
            await db.execute("""CREATE TABLE IF NOT EXISTS m17_cleanup (
                id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, status TEXT NOT NULL,
                plan_json TEXT NOT NULL CHECK(json_valid(plan_json)), created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL)""")
            # 中断后不自动继续移动；moving 项可能已经变更，需要人工核对。
            await db.execute("UPDATE m17_cleanup SET status='interrupted',updated_at=? WHERE status='running'", (_utc(),))

    def _paths(self) -> tuple[PathPolicy, Path]:
        base = self.local_base
        if not base.is_absolute() or base.anchor.startswith("\\\\") or _reparse(base):
            raise ToolError("CLEANUP_UNAVAILABLE", "当前用户临时目录不可用")
        base_policy = PathPolicy(str(base))
        temp = base_policy.resolve("Temp", "directory")
        temp_policy = PathPolicy(str(temp))
        quarantine_parent = base / "Orvia"
        if quarantine_parent.exists() and (_reparse(quarantine_parent) or not quarantine_parent.is_dir()):
            raise ToolError("CLEANUP_UNAVAILABLE", "隔离区父目录不安全")
        if temp.stat().st_dev != base.stat().st_dev:
            raise ToolError("CLEANUP_UNAVAILABLE", "临时目录与隔离区不在同一卷")
        return temp_policy, quarantine_parent / "cleanup-quarantine"

    def _candidate(self, policy: PathPolicy, name: str, *, cutoff: float) -> dict:
        if not name or name.startswith(".") or sensitive(name) or Path(name).suffix.lower() not in {".tmp", ".log"}:
            raise ToolError("CLEANUP_DENIED", "不在清理白名单")
        target = policy.resolve(name, "file")
        info = target.stat()
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mtime > cutoff
                or info.st_size > MAX_FILE or not _not_busy(target)):
            raise ToolError("CLEANUP_DENIED", "文件过新、过大、占用或不是独立普通文件")
        return {"name": name, "size": info.st_size, "mtime": datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat(),
                "risk": "medium" if target.suffix.lower() == ".log" else "low", "identity": _identity(target),
                "status": "pending", "quarantine_name": None, "quarantine_identity": None, "error": None}

    async def scan(self, cid: str) -> dict:
        """只扫描 Temp 顶层 500 项；不递归、不读取非白名单文件正文。"""
        policy, _ = self._paths()
        cutoff = time.time() - AGE_SECONDS
        entries, inspected, total, limited = [], 0, 0, False
        # scandir 按需迭代，最多观察 501 项；不能先枚举/排序整个用户 Temp。
        with os.scandir(policy.root) as iterator:
            for target in iterator:
                inspected += 1
                if inspected > MAX_SCAN:
                    limited = True
                    break
                try:
                    item = self._candidate(policy, target.name, cutoff=cutoff)
                except (ToolError, OSError):
                    continue
                if len(entries) >= MAX_ITEMS or total + item["size"] > MAX_BYTES:
                    limited = True
                    break
                total += item["size"]
                entries.append(item)
        info = policy.root.stat()
        plan = {"root": str(policy.root), "root_dev": info.st_dev, "root_ino": info.st_ino,
                "cutoff": cutoff, "entries": entries, "truncated": limited,
                "logical_bytes": total}
        plan["revision"] = _revision(plan)
        plan_id = str(uuid4())
        stamp = _utc()
        async with self.store._lock:
            await self.store._db().execute("INSERT INTO m17_cleanup VALUES (?,?,?,?,?,?)",
                (plan_id, cid, "planned", json.dumps(plan, ensure_ascii=False), stamp, stamp))
        return await self.get(cid, plan_id)

    async def _row(self, cid: str, plan_id: str):
        async with self.store._lock:
            async with self.store._db().execute("SELECT * FROM m17_cleanup WHERE id=? AND conversation_id=?", (plan_id, cid)) as cursor:
                row = await cursor.fetchone()
        if row is None:
            raise ToolError("NOT_FOUND", "当前会话没有此清理计划")
        return dict(row)

    async def _save(self, cid: str, plan_id: str, status: str, plan: dict):
        async with self.store._lock:
            await self.store._db().execute("UPDATE m17_cleanup SET status=?,plan_json=?,updated_at=? WHERE id=? AND conversation_id=?",
                (status, json.dumps(plan, ensure_ascii=False), _utc(), plan_id, cid))

    async def get(self, cid: str, plan_id: str) -> dict:
        row = await self._row(cid, plan_id)
        plan = json.loads(row["plan_json"])
        entries = [{key: item[key] for key in ("name", "size", "mtime", "risk", "status", "error")} | {"index": index}
                   for index, item in enumerate(plan["entries"])]
        moved = sum(item["size"] for item in plan["entries"] if item["status"] == "moved")
        return {"plan_id": plan_id, "revision": plan["revision"], "status": row["status"], "entries": entries,
                "truncated": plan["truncated"], "logical_bytes": plan["logical_bytes"], "quarantined_bytes": moved,
                "released_bytes": 0, "restore_until": (datetime.fromisoformat(row["created_at"]) + timedelta(seconds=RESTORE_SECONDS)).isoformat()}

    def _policy_for(self, plan: dict) -> tuple[PathPolicy, Path]:
        policy, quarantine = self._paths()
        info = policy.root.stat()
        if (str(policy.root), info.st_dev, info.st_ino) != (plan["root"], plan["root_dev"], plan["root_ino"]):
            raise ToolError("ROOT_CHANGED", "当前用户临时目录身份已变化，请重新扫描")
        stable = {key: value for key, value in plan.items() if key not in {"revision", "entries"}}
        stable["entries"] = [{**entry, "status": "pending", "quarantine_name": None, "quarantine_identity": None, "error": None}
                             for entry in plan["entries"]]
        if _revision(stable) != plan["revision"]:
            raise ToolError("STALE_APPROVAL", "清理计划版本已损坏")
        return policy, quarantine

    async def execute(self, cid: str, plan_id: str, revision: str, indices: list[int]) -> dict:
        """主进程原生确认后一次执行选定项目；每项先记 moving，失败逐项保留事实。"""
        row = await self._row(cid, plan_id)
        plan = json.loads(row["plan_json"])
        if row["status"] != "planned" or plan["revision"] != revision or not indices or len(set(indices)) != len(indices) or any(not 0 <= i < len(plan["entries"]) for i in indices):
            raise ToolError("STALE_APPROVAL", "清理计划、版本或逐项选择已变化")
        policy, quarantine = self._policy_for(plan)
        parent = quarantine.parent
        if not parent.exists():
            parent.mkdir(mode=0o700)
        if _reparse(parent) or not parent.is_dir():
            raise ToolError("CLEANUP_UNAVAILABLE", "隔离区父目录不安全")
        if not quarantine.exists():
            quarantine.mkdir(mode=0o700)
        if _reparse(quarantine) or not quarantine.is_dir() or quarantine.stat().st_dev != policy.root.stat().st_dev:
            raise ToolError("CLEANUP_UNAVAILABLE", "隔离区必须是同卷普通目录")
        await self._save(cid, plan_id, "running", plan)
        for index in indices:
            entry = plan["entries"][index]
            try:
                current = self._candidate(policy, entry["name"], cutoff=plan["cutoff"])
                if current["identity"] != entry["identity"]:
                    raise ToolError("CLEANUP_CHANGED", "文件在扫描后变化，已跳过")
                destination = quarantine / (str(uuid4()) + entry["name"][-4:].lower())
                entry["quarantine_name"] = destination.name
                entry["status"] = "moving"
                await self._save(cid, plan_id, "running", plan)
                if destination.exists():
                    raise ToolError("CLEANUP_CONFLICT", "隔离目标已存在")
                os.rename(policy.resolve(entry["name"], "file"), destination)
                entry["quarantine_identity"] = _identity(destination)
                if entry["quarantine_identity"]["sha256"] != entry["identity"]["sha256"]:
                    raise ToolError("CLEANUP_VERIFY_FAILED", "隔离后内容核验失败，需人工检查")
                entry["status"] = "moved"
                entry["error"] = None
            except (OSError, ToolError) as exc:
                entry["error"] = exc.code if isinstance(exc, ToolError) else "CLEANUP_IO"
                entry["status"] = "uncertain" if entry["status"] == "moving" else "skipped"
            await self._save(cid, plan_id, "running", plan)
        status = "completed" if all(plan["entries"][i]["status"] == "moved" for i in indices) else "partial"
        await self._save(cid, plan_id, status, plan)
        return await self.get(cid, plan_id)

    async def restore(self, cid: str, plan_id: str, index: int) -> dict:
        """30 天内仅将本计划的已核验隔离文件移回原路径；有冲突就停止。"""
        row = await self._row(cid, plan_id)
        plan = json.loads(row["plan_json"])
        if datetime.now(timezone.utc) > datetime.fromisoformat(row["created_at"]) + timedelta(seconds=RESTORE_SECONDS):
            raise ToolError("RESTORE_EXPIRED", "受限恢复期限已过；隔离文件未自动删除")
        if not 0 <= index < len(plan["entries"]):
            raise ToolError("INVALID_PARAMS", "恢复项目无效")
        policy, quarantine = self._policy_for(plan)
        entry = plan["entries"][index]
        if entry["status"] != "moved" or not entry["quarantine_name"]:
            raise ToolError("RESTORE_DENIED", "仅可恢复本计划中已核验的隔离文件")
        if not quarantine.is_dir() or _reparse(quarantine):
            raise ToolError("RESTORE_DENIED", "隔离区已变化")
        name = entry["quarantine_name"]
        if (Path(name).name != name or len(name) != 40 or not name[:36].replace("-", "").isalnum()
                or Path(name).suffix.lower() not in {".tmp", ".log"}):
            raise ToolError("RESTORE_DENIED", "隔离账本路径无效")
        source = quarantine / name
        if _reparse(source) or not source.is_file() or _identity(source) != entry["quarantine_identity"]:
            raise ToolError("RESTORE_CHANGED", "隔离文件已变化，拒绝恢复")
        target = policy.root / entry["name"]
        if target.exists() or target.is_symlink():
            raise ToolError("RESTORE_CONFLICT", "原位置已有文件，不覆盖")
        os.rename(source, target)
        if _identity(target)["sha256"] != entry["identity"]["sha256"]:
            entry["status"] = "uncertain"
            await self._save(cid, plan_id, row["status"], plan)
            raise ToolError("RESTORE_VERIFY_FAILED", "恢复后核验失败，请人工检查")
        entry["status"] = "restored"
        await self._save(cid, plan_id, row["status"], plan)
        return await self.get(cid, plan_id)
