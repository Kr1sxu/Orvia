import asyncio

from orvia_backend.agents.roles import AgentRole, BrowserAgent, can


def test_roles_are_fixed_and_browser_without_key_is_explicitly_unavailable():
    assert can(AgentRole.MAIN, "plan")
    assert not can(AgentRole.MAIN, "execute_approved")
    result = asyncio.run(BrowserAgent().web_search("合成查询"))
    assert result["available"] is False
    assert result["error"]["code"] == "SEARCH_UNAVAILABLE"
