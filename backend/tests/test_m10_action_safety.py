"""M10 合成目录安全回归：审批身份、恢复不确定性和撤销事实状态。"""

import asyncio
import json
import os
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from orvia_backend.agents.graph import MissionGraph
from orvia_backend.computer.actions import ActionPlanRequest, ActionService
from orvia_backend.computer.paths import PathPolicy, ToolError
from orvia_backend.storage import Store


async def setup(tmp_path, actions=None):
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "a.txt").write_text("synthetic a", encoding="utf-8")
    (root / "b.txt").write_text("synthetic b", encoding="utf-8")
    store = Store(tmp_path / "app.sqlite")
    await store.open()
    service = ActionService(store)
    mission = str(uuid4())
    plan = await service.create_plan(ActionPlanRequest(
        mission_id=mission, root=str(root),
        actions=actions or [{"kind": "rename", "source": "a.txt", "destination": "final.txt"}],
    ))
    return root, store, service, mission, plan


@pytest.mark.parametrize("actions", [
    [{"kind": "rename", "source": "a.txt", "destination": "one.txt"},
     {"kind": "rename", "source": "a.txt", "destination": "two.txt"}],
    [{"kind": "rename", "source": "a.txt", "destination": "one.txt"},
     {"kind": "rename", "source": "b.txt", "destination": "one.txt"}],
    [{"kind": "mkdir", "destination": "parent/child"}, {"kind": "mkdir", "destination": "parent"}],
])
def test_plan_conflicts_rejected_before_approval(tmp_path, actions):
    async def scenario():
        root, store, service, mission, old = await setup(tmp_path)
        try:
            with pytest.raises(ToolError):
                await service.create_plan(ActionPlanRequest(mission_id=mission, root=str(root), actions=actions))
            assert (await store.get_latest_operation(mission))["id"] == old["operation_id"]
            assert not (root / "one.txt").exists() and not (root / "parent").exists()
        finally:
            await store.close()
    asyncio.run(scenario())


def test_approval_rejects_old_revision_and_modified_plan(tmp_path):
    async def scenario():
        root, store, service, _, plan = await setup(tmp_path)
        try:
            with pytest.raises(ToolError, match="STALE_PLAN"):
                await service.approve(plan["operation_id"], "old-version")
            operation = await store.get_operation(plan["operation_id"])
            operation["plan"]["actions"][0]["destination"] = "changed.txt"
            # 模拟磁盘计划变化；旧摘要不能授权修改后的动作。
            await store._db().execute("UPDATE operation_tasks SET plan_json = ? WHERE id = ?",
                                      (json.dumps(operation["plan"]), plan["operation_id"]))
            with pytest.raises(ToolError, match="STALE_PLAN"):
                await service.approve(plan["operation_id"], plan["revision"])
            assert (root / "a.txt").exists() and not (root / "changed.txt").exists()
        finally:
            await store.close()
    asyncio.run(scenario())


@pytest.mark.parametrize("change", ["source", "root"])
def test_execution_rejects_changed_identity(tmp_path, change):
    async def scenario():
        root, store, service, _, plan = await setup(tmp_path)
        try:
            await service.approve(plan["operation_id"], plan["revision"])
            if change == "source":
                (root / "a.txt").write_text("changed synthetic content", encoding="utf-8")
                result = await service.execute(plan["operation_id"])
                assert result["status"] == "failed"
            else:
                root.rename(tmp_path / "old-workspace")
                root.mkdir()
                (root / "a.txt").write_text("replacement", encoding="utf-8")
                with pytest.raises(ToolError, match="ROOT_CHANGED"):
                    await service.execute(plan["operation_id"])
            assert (root / "a.txt").exists() and not (root / "final.txt").exists()
        finally:
            await store.close()
    asyncio.run(scenario())


def test_verify_rejects_same_name_replacement(tmp_path):
    async def scenario():
        root, store, service, _, plan = await setup(tmp_path)
        try:
            await service.approve(plan["operation_id"])
            assert (await service.execute(plan["operation_id"]))["status"] == "completed"
            (root / "final.txt").write_text("external replacement content", encoding="utf-8")
            assert not (await service.verify(plan["operation_id"]))["complete"]
        finally:
            await store.close()
    asyncio.run(scenario())


def test_resume_refuses_filesystem_change_without_ledger(tmp_path):
    async def scenario():
        root, store, service, _, plan = await setup(tmp_path)
        try:
            await service.approve(plan["operation_id"])
            os.rename(root / "a.txt", root / "final.txt")
            await store.recover_operations()
            with pytest.raises(ToolError, match="RECOVERY_CONFLICT"):
                await service.resume(plan["operation_id"])
            assert (await store.get_operation(plan["operation_id"]))["status"] == "interrupted"
            assert (root / "final.txt").read_text(encoding="utf-8") == "synthetic a"
        finally:
            await store.close()
    asyncio.run(scenario())


def test_partial_undo_conflict_is_persisted(tmp_path):
    async def scenario():
        root, store, service, mission, plan = await setup(tmp_path, [
            {"kind": "rename", "source": "a.txt", "destination": "a-new.txt"},
            {"kind": "rename", "source": "b.txt", "destination": "b-new.txt"},
        ])
        try:
            await service.approve(plan["operation_id"])
            await service.execute(plan["operation_id"])
            (root / "a.txt").write_text("external conflict", encoding="utf-8")
            with pytest.raises(ToolError, match="UNDO_CONFLICT"):
                await service.undo_latest(mission)
            operation = await store.get_operation(plan["operation_id"])
            assert operation["status"] == "partially_undone"
            assert operation["entries"][1]["status"] == "undone"
            assert (root / "b.txt").exists() and (root / "a-new.txt").exists()
            assert (root / "a.txt").read_text(encoding="utf-8") == "external conflict"
        finally:
            await store.close()
    asyncio.run(scenario())


def test_graph_rejects_repeat_approval_and_thread_reuse(tmp_path):
    async def scenario():
        root, store, _, mission, _ = await setup(tmp_path)
        try:
            async with MissionGraph(store, tmp_path / "checkpoints.sqlite") as graph:
                state = {"mission_id": mission, "goal": "合成任务", "root": str(root),
                         "actions": [{"kind": "rename", "source": "a.txt", "destination": "final.txt"}]}
                await graph.start(state, "thread")
                await graph.approve_and_resume("thread")
                with pytest.raises(ToolError, match="INVALID_STATE"):
                    await graph.approve_and_resume("thread")
                with pytest.raises(ToolError, match="INVALID_STATE"):
                    await graph.start(state, "thread")
                assert (root / "final.txt").exists()
        finally:
            await store.close()
    asyncio.run(scenario())


def test_original_path_chain_rejects_internal_link(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "real").mkdir()
    (root / "real/a.txt").write_text("synthetic", encoding="utf-8")
    try:
        (root / "link").symlink_to(root / "real", target_is_directory=True)
    except OSError:
        if os.name != "nt":
            pytest.skip("系统未授予创建符号链接权限")
        # Windows 目录联接无需开发者模式；与 symlink 一样必须拒绝重解析路径。
        completed = subprocess.run(["cmd", "/c", "mklink", "/J", str(root / "link"), str(root / "real")],
                                   capture_output=True, check=False)
        assert completed.returncode == 0
    policy = PathPolicy(str(root))
    with pytest.raises(ToolError, match="path_denied"):
        policy.resolve("link/a.txt")
    with pytest.raises(ToolError, match="PATH_DENIED"):
        ActionService._relative(policy, "link/new.txt", allow_missing=True)
