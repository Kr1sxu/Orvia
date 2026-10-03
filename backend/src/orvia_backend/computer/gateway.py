"""只读工具权限网关：权限来自主进程授权记录，不信任模型自述的角色或范围。"""

import json
import os
from pathlib import Path
from dataclasses import dataclass
from uuid import uuid4

from .contracts import GrantRequest, ToolRequest
from .files import FileTools
from .paths import PathPolicy, ToolError, sensitive
from .system import SystemTools


@dataclass
class Grant:
    id: str
    mission_id: str
    root: PathPolicy | None
    allow_text: bool
    allow_system: bool
    calls_used: int = 0


class ComputerGateway:
    """会话内授权重启失效；重新授权不会重置本连接该任务的调用预算。"""

    def __init__(self):
        self._grants: dict[str, Grant] = {}
        self._budgets: dict[str, int] = {}
        self.system = SystemTools()

    def grant(self, request: GrantRequest) -> dict:
        mission = str(request.mission_id)
        policy = PathPolicy(request.root) if request.root is not None else None
        if policy is None and request.allow_text:
            raise ToolError("PERMISSION_DENIED", "文本权限需要先选择目录")
        if policy is None and not request.allow_system:
            raise ToolError("PERMISSION_DENIED", "未选择任何只读能力")
        if mission not in self._budgets and len(self._budgets) >= 100:
            raise ToolError("BUDGET_EXCEEDED", "本连接授权任务数量已达上限，请重启后重新确认")
        # 每次授权都使用新 token，旧 UI/工具请求不能借用新授权扩大范围。
        self._grants[mission] = Grant(str(uuid4()), mission, policy, request.allow_text, request.allow_system)
        self._budgets.setdefault(mission, 0)
        return self.status(mission)

    def status(self, mission_id: str) -> dict:
        grant = self._grants.get(mission_id)
        return {"mission_id": mission_id, "grant_id": grant.id if grant else None,
                "root_label": grant.root.root.name if grant and grant.root else None,
                "allow_files": bool(grant and grant.root), "allow_text": bool(grant and grant.allow_text),
                "allow_system": bool(grant and grant.allow_system),
                "calls_remaining": max(0, 200 - self._budgets.get(mission_id, 0))}

    def revoke(self, mission_id: str) -> dict:
        """立即撤销后续调用；已经返回给用户的观察不构成新权限。"""
        self._grants.pop(mission_id, None)
        return self.status(mission_id)

    def authorized_root(self, mission_id: str):
        """会话写动作入口复核当前授权；历史数据库中的路径不构成授权。"""
        grant = self._grants.get(mission_id)
        if grant is None or grant.root is None:
            raise ToolError("PERMISSION_DENIED", "请重新选择并授权本地目录")
        return grant.root.resolve(".", "directory")

    def check_scan(self, role: str, mission_id: str, grant_id: str) -> PathPolicy:
        """批次扫描持续复核同一内存授权；撤销/替换不继承旧批次权限。"""
        if role != "computer":
            raise ToolError("ROLE_DENIED", "此角色不能扫描本地目录")
        grant = self._grants.get(mission_id)
        if grant is None or grant.id != grant_id or grant.root is None:
            raise ToolError("PERMISSION_DENIED", "目录授权已撤销或变化，请重新确认")
        grant.root.resolve(".", "directory")
        return grant.root

    def begin_scan(self, role: str, mission_id: str, grant_id: str) -> PathPolicy:
        """M20 一次完整有界扫描扣一次既有工具预算，分页读取不会重新访问文件。"""
        policy = self.check_scan(role, mission_id, grant_id)
        if self._budgets.get(mission_id, 0) >= 200:
            raise ToolError("BUDGET_EXCEEDED", "本任务的只读调用预算已用完")
        self._budgets[mission_id] += 1
        return policy

    @staticmethod
    def selected_file(role: str, path: str) -> tuple[PathPolicy, str]:
        """仅可信主进程原生选择器调用，授权只覆盖该文件，不修改目录 grant。"""
        if role != "computer":
            raise ToolError("ROLE_DENIED", "此角色不能访问本地附件或导出")
        selected = Path(path)
        if not selected.is_absolute() or any(sensitive(part) for part in selected.parts):
            raise ToolError("path_denied", "所选文件不允许访问")
        return PathPolicy(str(selected.parent)), selected.name

    def read_attachment(self, role: str, path: str) -> tuple[bytes, str]:
        """限定单次读取、大小与句柄身份；不扫描父目录，不保留访问 token。"""
        policy, name = self.selected_file(role, path)
        target = policy.resolve(name, "file")
        if target.suffix.lower() not in {".pdf", ".docx", ".pptx", ".png", ".jpg", ".jpeg"}:
            raise ToolError("DOCUMENT_FORMAT", "仅支持 PDF、DOCX、PPTX、PNG 和 JPEG")
        with target.open("rb") as stream:
            before = policy.validate_open_file(stream.fileno(), target)
            if before.st_size > 10 * 1024 * 1024:
                raise ToolError("DOCUMENT_LIMIT", "附件超过 10 MiB 上限")
            data = stream.read(10 * 1024 * 1024 + 1)
            policy.resolve(name, "file")
            after = policy.validate_open_file(stream.fileno(), target)
            if len(data) > 10 * 1024 * 1024 or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ToolError("file_changed", "读取期间附件已变化，请重新选择")
        return data, name

    def export_document(self, role: str, path: str, data: bytes, format: str) -> str:
        """选择保存位置即对预览版本的一次写授权；O_EXCL 拒绝竞态覆盖。"""
        policy, name = self.selected_file(role, path)
        limits = {"md": (".md", 60 * 1024), "json": (".json", 60 * 1024),
                  "docx": (".docx", 2 * 1024 * 1024), "pptx": (".pptx", 2 * 1024 * 1024),
                  "pdf": (".pdf", 2 * 1024 * 1024)}
        extension, max_bytes = limits[format]
        if Path(name).suffix.lower() != extension or not data or len(data) > max_bytes:
            raise ToolError("EXPORT_INVALID", "导出扩展名或内容预算不符合要求")
        target = policy.new_file(name)
        try:
            with target.open("x+b") as stream:
                policy.resolve(name, "file")
                policy.validate_open_file(stream.fileno(), target)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
                policy.resolve(name, "file")
                info = policy.validate_open_file(stream.fileno(), target)
                stream.seek(0)
                if info.st_size != len(data) or stream.read(len(data) + 1) != data:
                    raise ToolError("EXPORT_FAILED", "导出文件核验失败，请检查目标")
        except FileExistsError as exc:
            raise ToolError("EXPORT_EXISTS", "目标已存在，请选择新的文件名") from exc
        return name

    def execute(self, role: str, request: ToolRequest) -> dict:
        """role 由内部调度代码传入，不在工具参数中接收，Main/Browser 无本地权限。"""
        if role != "computer":
            raise ToolError("ROLE_DENIED", "此角色不能调用本地 Computer 工具")
        mission = str(request.mission_id)
        grant = self._grants.get(mission)
        if grant is None or grant.id != str(request.grant_id):
            raise ToolError("PERMISSION_DENIED", "目录授权不存在、已变更或已撤销，请重新确认")
        if self._budgets[mission] >= 200:
            raise ToolError("BUDGET_EXCEEDED", "本任务的只读调用预算已用完")
        tool = request.call.tool
        args = request.call.arguments.model_dump()
        system_methods = {"detect_runtimes": self.system.detect_runtimes, "list_processes": self.system.list_processes,
                          "run_readonly_template": self.system.run_template}
        if tool in system_methods:
            if not grant.allow_system:
                raise ToolError("PERMISSION_DENIED", "未授权系统环境和进程只读观察")
            function = system_methods[tool]
        else:
            if grant.root is None or tool == "read_text_file" and not grant.allow_text:
                raise ToolError("PERMISSION_DENIED", "未授权此目录或文本读取")
            files = FileTools(grant.root)
            function = getattr(files, tool)
        self._budgets[mission] += 1
        result = function(**args)
        # 二次限制跨语言输出，拒绝超大结果，不放任断开协议后默默重放。
        if len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > 48 * 1024:
            raise ToolError("OUTPUT_LIMIT", "工具结果超过通信预算，请缩小范围")
        return {**result, "tool": tool, "mission_id": mission, "grant_id": grant.id,
                "calls_remaining": 200 - self._budgets[mission]}
