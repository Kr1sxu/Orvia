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
    """M05 仅注册 Browser 逻辑角色；Tavily 未配置时明确不可用，不伪造搜索结果。"""

    def __init__(self, tavily_available: bool = False):
        self.tavily_available = tavily_available

    async def web_search(self, query: str) -> dict:
        if not self.tavily_available:
            return {"available": False, "error": {"code": "SEARCH_UNAVAILABLE", "message": "未配置搜索凭据"}}
        raise NotImplementedError("M07 才实现 Browser 搜索")
