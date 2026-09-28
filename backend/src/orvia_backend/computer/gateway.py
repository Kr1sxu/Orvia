"""只读工具权限网关：权限来自主进程授权记录，不信任模型自述的角色或范围。"""

import json
from dataclasses import dataclass
from uuid import uuid4

from .contracts import GrantRequest, ToolRequest
from .files import FileTools
from .paths import PathPolicy, ToolError
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
