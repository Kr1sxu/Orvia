"""M05 LangGraph 编排：规划、审批暂停、执行、核验和完成判断。"""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Any, Literal, TypedDict

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

from ..computer.actions import Action, ActionPlanRequest, ActionService
from ..computer.paths import ToolError
from ..storage import Store
from .roles import AgentRole, can


class MissionState(TypedDict, total=False):
    """图状态只保存合成任务数据、计划引用和证据，不保存模型 Key。"""

    mission_id: str
    goal: str
    root: str
    actions: list[dict[str, Any]]
    operation_id: str
    approved: bool
    phase: Literal["planning", "awaiting_approval", "executing", "verifying", "completed", "failed"]
    evidence: list[dict[str, Any]]
    error: str | None
    completed: bool


class MissionGraph(AbstractAsyncContextManager):
    """绑定一个 Store 和 SQLite checkpoint；同一 thread_id 可在审批后恢复。"""

    def __init__(self, store: Store, checkpoint_path: Path):
        self.store = store
        self.checkpoint_path = checkpoint_path
        self._checkpointer: AsyncSqliteSaver | None = None
        self._checkpoint_context = None
        self._graph = None

    async def __aenter__(self) -> "MissionGraph":
        self._checkpoint_context = AsyncSqliteSaver.from_conn_string(str(self.checkpoint_path))
        self._checkpointer = await self._checkpoint_context.__aenter__()
        # langgraph-checkpoint-sqlite 2.x 仍调用旧版 aiosqlite 的 is_alive；0.22 已移除该方法。
        # 绑定等价的线程状态检查，避免降级为内存 checkpoint。
        if not hasattr(self._checkpointer.conn, "is_alive"):
            self._checkpointer.conn.is_alive = self._checkpointer.conn._thread.is_alive
        await self._checkpointer.setup()
        self._graph = self._build().compile(checkpointer=self._checkpointer)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._checkpointer is not None:
            await self._checkpoint_context.__aexit__(exc_type, exc, tb)
            self._checkpointer = None
            self._checkpoint_context = None
            self._graph = None

    def _build(self) -> StateGraph:
        graph = StateGraph(MissionState)
        graph.add_node("route", self._route)
        graph.add_node("main_plan", self._main_plan)
        graph.add_node("computer_plan", self._computer_plan)
        graph.add_node("approval_gate", self._approval_gate)
        graph.add_node("computer_execute", self._computer_execute)
        graph.add_node("verify", self._verify)
        graph.add_node("main_complete", self._main_complete)
        graph.add_edge(START, "route")
        graph.add_conditional_edges("route", self._route_next, {"main_plan": "main_plan", "approval_gate": "approval_gate"})
        graph.add_conditional_edges("main_plan", lambda state: "computer_plan" if state.get("phase") != "failed" else "failed",
                                    {"computer_plan": "computer_plan", "failed": END})
        graph.add_edge("computer_plan", "approval_gate")
        graph.add_conditional_edges("approval_gate", self._approval_next, {"computer_execute": "computer_execute", "awaiting": END})
        graph.add_edge("computer_execute", "verify")
        graph.add_conditional_edges("verify", lambda state: "complete" if state.get("completed") else "failed",
                                    {"complete": "main_complete", "failed": END})
        graph.add_edge("main_complete", END)
        return graph

    async def _route(self, state: MissionState) -> dict:
        return {}

    def _route_next(self, state: MissionState) -> str:
        if state.get("phase") == "awaiting_approval" and state.get("approved"):
            return "approval_gate"
        return "main_plan"

    async def _main_plan(self, state: MissionState) -> dict:
        if not can(AgentRole.MAIN, "plan"):
            raise ToolError("ROLE_DENIED", "Main 不具备该规划能力")
        actions = state.get("actions", [])
        if not actions:
            return {"phase": "failed", "error": "没有可执行的合成动作计划"}
        # M05 的日常闭环使用程序生成的合成动作；真实模型规划适配在后续能力中显式开启。
        return {"phase": "planning", "evidence": [{"agent": "main", "kind": "plan", "count": len(actions)}]}

    async def _computer_plan(self, state: MissionState) -> dict:
        if not can(AgentRole.COMPUTER, "prepare_action"):
            raise ToolError("ROLE_DENIED", "Computer 不具备计划能力")
        service = ActionService(self.store)
        plan = await service.create_plan(ActionPlanRequest(mission_id=state["mission_id"], root=state["root"], actions=[Action.model_validate(x) for x in state["actions"]]))
        return {"operation_id": plan["operation_id"], "phase": "awaiting_approval",
                "evidence": state.get("evidence", []) + [{"agent": "computer", "kind": "plan", "operation_id": plan["operation_id"]}]}

    async def _approval_gate(self, state: MissionState) -> dict:
        if state.get("approved"):
            await ActionService(self.store).approve(state["operation_id"])
            return {"phase": "executing"}
        return {"phase": "awaiting_approval"}

    def _approval_next(self, state: MissionState) -> str:
        return "computer_execute" if state.get("approved") else "awaiting"

    async def _computer_execute(self, state: MissionState) -> dict:
        if not can(AgentRole.COMPUTER, "execute_approved"):
            raise ToolError("ROLE_DENIED", "Computer 不具备执行能力")
        result = await ActionService(self.store).execute(state["operation_id"])
        if result["status"] != "completed":
            return {"phase": "failed", "error": result.get("error", "动作执行失败"),
                    "evidence": state.get("evidence", []) + [{"agent": "computer", "kind": "execution", "status": result["status"]}]}
        return {"phase": "verifying", "evidence": state.get("evidence", []) + [{"agent": "computer", "kind": "execution", "status": "completed"}]}

    async def _verify(self, state: MissionState) -> dict:
        result = await ActionService(self.store).verify(state["operation_id"])
        return {"completed": bool(result["complete"]), "phase": "completed" if result["complete"] else "failed",
                "error": None if result["complete"] else "执行核验未通过",
                "evidence": state.get("evidence", []) + [{"agent": "main", "kind": "verification", "result": result}]}

    async def _main_complete(self, state: MissionState) -> dict:
        if not can(AgentRole.MAIN, "judge"):
            raise ToolError("ROLE_DENIED", "Main 不具备完成判断能力")
        return {"completed": True, "phase": "completed"}

    async def start(self, state: MissionState, thread_id: str) -> MissionState:
        """启动或恢复图；未审批时安全停在 awaiting_approval。"""
        if self._graph is None:
            raise RuntimeError("MissionGraph 未打开")
        config = {"configurable": {"thread_id": thread_id}}
        result = await self._graph.ainvoke(state, config)
        return result

    async def approve_and_resume(self, thread_id: str) -> MissionState:
        """审批由外部 UI 完成后只更新 checkpoint 状态，不伪造工具调用。"""
        if self._graph is None:
            raise RuntimeError("MissionGraph 未打开")
        config = {"configurable": {"thread_id": thread_id}}
        return await self._graph.ainvoke({"approved": True}, config)
