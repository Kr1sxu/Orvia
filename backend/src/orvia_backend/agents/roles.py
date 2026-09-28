"""三 Agent 的固定职责和委派边界。"""

from enum import StrEnum


class AgentRole(StrEnum):
    MAIN = "main"
    COMPUTER = "computer"
    BROWSER = "browser"


ROLE_CAPABILITIES = {
    AgentRole.MAIN: frozenset({"plan", "replan", "summarize", "judge"}),
    AgentRole.COMPUTER: frozenset({"observe", "prepare_action", "execute_approved"}),
    AgentRole.BROWSER: frozenset({"read_web"}),
}


def can(role: AgentRole, capability: str) -> bool:
    """能力表是程序边界；模型输出不能动态增加角色权限。"""
    return capability in ROLE_CAPABILITIES[role]


class BrowserAgent:
    """Browser 仅持有窄服务，不提供脚本、点击或 Computer 工具。"""

    def __init__(self, service=None):
        from ..browser import BrowserService
        self.service = service or BrowserService()

    async def web_search(self, query: str) -> dict:
        return await self.service.web_search(query)

    async def read_web(self, url: str, *, mode: str = "auto") -> dict:
        return await self.service.read(url, mode=mode)
