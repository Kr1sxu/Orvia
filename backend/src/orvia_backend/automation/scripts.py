"""脚本内容只是提案；可信搬运器复制显式输入，原生 LPAC 才负责执行隔离。"""

import asyncio
import hashlib
import json
import os
import stat
import threading
import time
from pathlib import Path

from ..computer.paths import PathPolicy, ToolError, _reparse
from .repository import digest


class ScriptService:
    def __init__(self, root, gateway, repository, runner=None):
        self.root = Path(root)
        self.gateway, self.repository = gateway, repository
        self.runner = runner
        self.live = {}
        self.tasks = {}

    def _input(self, cid, relative):
        policy = PathPolicy(str(self.gateway.authorized_root(cid)))
        target = policy.resolve(relative, "file")
        with target.open("rb") as stream:
            before = policy.validate_open_file(stream.fileno(), target)
            if before.st_nlink != 1 or before.st_size > 2 * 1024 * 1024:
                raise ToolError("M18_INPUT_LIMIT", "输入只支持独立普通文件，单项最多 2 MiB")
            data = stream.read(2 * 1024 * 1024 + 1)
            after = policy.validate_open_file(stream.fileno(), target)
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ToolError("file_changed", "输入读取期间变化，请重新预览")
        return data

    def read_selected_script(self, selected):
        policy, name = self.gateway.selected_file("computer", selected)
        path = policy.resolve(name, "file")
        if path.suffix.lower() != ".py":
            raise ToolError("M18_SCRIPT_FORMAT", "仅可显式选择 Python .py 文件")
        with path.open("rb") as stream:
            before = policy.validate_open_file(stream.fileno(), path)
            if before.st_nlink != 1 or before.st_size > 32768:
                raise ToolError("M18_SCRIPT_LIMIT", "脚本不是独立普通文件或超过 32 KiB")
            data = stream.read(32769)
            after = policy.validate_open_file(stream.fileno(), path)
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ToolError("file_changed", "选择的脚本发生变化")
        try:
            return data.decode("utf-8-sig")
        except UnicodeError:
            raise ToolError("M18_SCRIPT_FORMAT", "脚本须为 UTF-8 文本") from None

    async def preview(self, cid, source, inputs, origin="paste"):
        if not source.strip() or len(source.encode("utf-8")) > 32768 or "\x00" in source:
            raise ToolError("M18_SCRIPT_LIMIT", "Python 源码最多 32 KiB")
        # 只编译语法树，不执行代码；import/表达式仍只是待审批的文本。
        try:
            compile(source, "<approved-script>", "exec", dont_inherit=True)
        except (SyntaxError, ValueError):
            raise ToolError("M18_SCRIPT_FORMAT", "Python 脚本语法无效") from None
        # Windows会将./、重复分隔符解析成同一路径；必须在建账本/复制前规范化判重。
        inputs = [Path(name).as_posix() for name in inputs]
        if len({x.casefold() for x in inputs}) != len(inputs):
            raise ToolError("M18_INPUT_LIMIT", "不能重复选择输入")
        copies = [(name, self._input(cid, name)) for name in inputs]
        input_info = [{"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()} for name, data in copies]
        if sum(item["bytes"] for item in input_info) > 16 * 1024 * 1024:
            raise ToolError("M18_INPUT_LIMIT", "输入总量最多 16 MiB")
        # revision 固化原文、输入字节及有效期；私有任务不把源码写进会话/审计日志。
        expires = time.time() + 300
        plan = {"kind": "script", "source": source, "origin": origin, "inputs": input_info,
                "runtime": "CPython 3.12 private copy", "network": False, "elevation": False,
                "timeout_seconds": 30, "memory_mib": 512, "processes": 4,
                "output_bytes": 16384, "file_output_bytes": 16 * 1024 * 1024, "expires_at": expires}
        if len(json.dumps(plan, ensure_ascii=False).encode("utf-8")) > 48 * 1024:
            raise ToolError("OUTPUT_LIMIT", "完整脚本预览超过协议预算，请缩小脚本")
        revision = digest(plan)
        audit = {key: plan[key] for key in ("origin", "runtime", "network", "elevation", "timeout_seconds", "memory_mib", "processes", "expires_at")}
        audit.update(source_sha256=hashlib.sha256(source.encode()).hexdigest(), input_count=len(inputs), input_bytes=sum(item["bytes"] for item in input_info))
        oid = await self.repository.create(cid, "script", revision, audit)
        root = self.root / oid
        root.mkdir(parents=True, exist_ok=False)
        (root / "input").mkdir()
        (root / "output").mkdir()
        (root / "script.py").write_text(source, encoding="utf-8")
        for name, data in copies:
            target = root / "input" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(data)
        self.live[oid] = {"cid": cid, "plan": plan, "revision": revision, "root": root, "cancel": threading.Event(), "result": None}
        return {"operation_id": oid, "revision": revision, "status": "awaiting_approval", "plan": plan}

    async def get(self, cid, oid):
        audit = await self.repository.get(cid, oid)
        active = self.live.get(oid)
        if active is None or active["cid"] != cid:
            # 可查历史事实，但新进程不能借旧源码任务重新执行。
            return {**audit, "result": None, "outputs": [], "live": False}
        return {**audit, "result": active["result"], "outputs": active.get("outputs", []), "live": True}

    async def execute(self, cid, oid, revision):
        active = self.live.get(oid)
        if active is None or active["cid"] != cid:
            raise ToolError("M18_AUTH_EXPIRED", "脚本授权已失效，请重新预览")
        if revision != active["revision"] or time.time() > active["plan"]["expires_at"]:
            raise ToolError("STALE_APPROVAL", "脚本审批过期或版本不符")
        if (active["root"] / "script.py").read_text(encoding="utf-8") != active["plan"]["source"]:
            raise ToolError("STALE_APPROVAL", "隔离脚本内容已变化")
        for item in active["plan"]["inputs"]:
            copied = active["root"] / "input" / item["path"]
            if _reparse(copied) or hashlib.sha256(copied.read_bytes()).hexdigest() != item["sha256"]:
                raise ToolError("STALE_APPROVAL", "隔离输入内容已变化")
        await self.repository.transition(cid, oid, ["awaiting_approval"], "running")
        self.tasks[oid] = asyncio.create_task(self._run(cid, oid, active))
        return await self.get(cid, oid)

    async def _run(self, cid, oid, active):
        try:
            if self.runner is None:
                from .windows_isolation import prepare_runtime, run_script
                runtime = await asyncio.to_thread(prepare_runtime, self.root.parent / "runtime")
                result = await asyncio.to_thread(run_script, runtime, active["root"], cancel_event=active["cancel"], timeout=30)
            else:
                # 测试只在构造时注入，不接受产品环境变量或请求指定执行器。
                result = await asyncio.to_thread(self.runner, active["root"], cancel_event=active["cancel"], timeout=30)
            active["result"] = result
            if not result.get("token_verified") or not result.get("processes_reaped"):
                raise ToolError("M18_ISOLATION_UNAVAILABLE", "无法确认隔离或进程回收")
            outputs = self._outputs(active["root"])
            active["outputs"] = outputs
            status = result["status"]
            final = "completed" if status == "completed" and result["exit_code"] == 0 else "cancelled" if status == "cancelled" else "failed"
            evidence = {"isolation": "lpac", "token_verified": True, "processes_reaped": True, "exit_code": result["exit_code"],
                        "reason": status, "output_count": len(outputs), "output_bytes": sum(x["bytes"] for x in outputs),
                        "stdout_sha256": hashlib.sha256(result.get("stdout", "").encode()).hexdigest(), "stderr_sha256": hashlib.sha256(result.get("stderr", "").encode()).hexdigest()}
            await self.repository.transition(cid, oid, ["running", "cancel_requested"], final, evidence)
        except ToolError as error:
            active["result"] = {"status": "failed", "error": {"code": error.code, "message": error.message}}
            await self.repository.transition(cid, oid, ["running", "cancel_requested"], "failed", {"code": error.code})
        except OSError:
            active["result"] = {"status": "failed", "error": {"code": "M18_STORAGE", "message": "任务存储无法核验"}}
            await self.repository.transition(cid, oid, ["running", "cancel_requested"], "uncertain", {"code": "M18_STORAGE"})

    def _outputs(self, root):
        directory = root / "output"
        policy = PathPolicy(str(directory))
        # 先有界遍历并拒绝重解析目录，再排序文件；rglob+sorted会在预算检查前展开整棵不可信树。
        directories, paths, visited = [directory], [], 0
        while directories:
            current = directories.pop()
            policy.resolve(current.relative_to(directory).as_posix(), "directory")
            with os.scandir(current) as entries:
                for entry in entries:
                    visited += 1
                    if visited > 512:
                        raise ToolError("M18_OUTPUT_LIMIT", "产物目录项超过 512 项预算")
                    path = Path(entry.path)
                    if _reparse(path):
                        raise ToolError("M18_OUTPUT_DENIED", "脚本产物含链接或重解析点")
                    if entry.is_dir(follow_symlinks=False):
                        directories.append(path)
                    elif entry.is_file(follow_symlinks=False):
                        paths.append(path)
                        if len(paths) > 12:
                            raise ToolError("M18_OUTPUT_LIMIT", "产物文件数量超过限制")
                    else:
                        raise ToolError("M18_OUTPUT_DENIED", "产物包含非普通文件")
        result = []
        for path in sorted(paths):
            relative = path.relative_to(directory).as_posix()
            target = policy.resolve(relative, "file")
            with target.open("rb") as stream:
                before = policy.validate_open_file(stream.fileno(), target)
                if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > 2 * 1024 * 1024:
                    raise ToolError("M18_OUTPUT_DENIED", "产物只支持独立普通文件，每项最多 2 MiB")
                data = stream.read(2 * 1024 * 1024 + 1)
                after = policy.validate_open_file(stream.fileno(), target)
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ToolError("file_changed", "产物读取期间变化")
            result.append({"index": len(result), "path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "exported": False})
            if len(result) > 12 or sum(x["bytes"] for x in result) > 16 * 1024 * 1024:
                raise ToolError("M18_OUTPUT_LIMIT", "产物总量或数量超过限制")
        return result

    async def export(self, cid, oid, revision, index, selected_path):
        active = self.live.get(oid)
        status = await self.repository.get(cid, oid)
        if not active or active["cid"] != cid or revision != active["revision"] or status["status"] not in {"completed", "cancelled", "failed"}:
            raise ToolError("M18_AUTH_EXPIRED", "仅可导出本轮已核验的隔离产物")
        outputs = active.get("outputs", [])
        if not 0 <= index < len(outputs) or outputs[index]["exported"]:
            raise ToolError("INVALID_STATE", "产物不存在或已导出")
        original = outputs[index]
        fresh = self._outputs(active["root"])
        if index >= len(fresh) or any(fresh[index][k] != original[k] for k in ("path", "bytes", "sha256")):
            raise ToolError("STALE_APPROVAL", "隔离产物已变化")
        output_policy = PathPolicy(str(active["root"] / "output"))
        source = output_policy.resolve(original["path"], "file")
        with source.open("rb") as stream:
            before = output_policy.validate_open_file(stream.fileno(), source)
            if before.st_nlink != 1 or before.st_size != original["bytes"]:
                raise ToolError("STALE_APPROVAL", "产物身份或大小变化")
            data = stream.read(2 * 1024 * 1024 + 1)
            after = output_policy.validate_open_file(stream.fileno(), source)
            if ((before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns)
                    or len(data) != original["bytes"] or hashlib.sha256(data).hexdigest() != original["sha256"]):
                raise ToolError("STALE_APPROVAL", "回传读取的产物字节已变化")
        policy, name = self.gateway.selected_file("computer", selected_path)
        target = policy.new_file(name)
        # 回传本身是独立批准的新建，脚本退出不自动修改真实工作区。
        with target.open("x+b") as stream:
            policy.validate_open_file(stream.fileno(), target)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
            policy.validate_open_file(stream.fileno(), target)
            stream.seek(0)
            if stream.read(len(data) + 1) != data:
                raise ToolError("M18_EXPORT_FAILED", "产物回传读回失败，请人工核对新文件")
        original["exported"] = True
        return {"filename": name, "bytes": len(data), "sha256": original["sha256"], "verified": True}

    async def cancel(self, cid, oid, revision):
        active = self.live.get(oid)
        if not active or active["cid"] != cid or active["revision"] != revision:
            raise ToolError("M18_AUTH_EXPIRED", "取消目标不是当前会话的有效步骤")
        current = await self.repository.get(cid, oid)
        if current["status"] == "awaiting_approval":
            await self.repository.transition(cid, oid, ["awaiting_approval"], "cancelled")
        elif current["status"] == "running":
            active["cancel"].set()
            await self.repository.transition(cid, oid, ["running"], "cancel_requested")
        return await self.get(cid, oid)

    async def close(self):
        for active in self.live.values():
            active["cancel"].set()
        if self.tasks:
            await asyncio.gather(*self.tasks.values(), return_exceptions=True)
