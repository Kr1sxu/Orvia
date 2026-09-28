import asyncio
from pathlib import Path
from uuid import uuid4

import pytest

from orvia_backend.computer.actions import ActionPlanRequest, ActionService
from orvia_backend.computer.paths import ToolError
from orvia_backend.storage import Store


def test_plan_requires_approval_executes_verifies_and_undoes(tmp_path: Path):
    async def scenario():
        root = tmp_path / "workspace"
        root.mkdir()
        (root / "draft.txt").write_text("合成内容", encoding="utf-8")
        store = Store(tmp_path / "app.sqlite")
        await store.open()
        try:
            service = ActionService(store)
            mission = uuid4()
            plan = await service.create_plan(ActionPlanRequest(mission_id=mission, root=str(root), actions=[
                {"kind": "mkdir", "destination": "archive"},
                {"kind": "rename", "source": "draft.txt", "destination": "archive/final.txt"},
            ]))
            with pytest.raises(ToolError) as exc:
                await service.execute(plan["operation_id"])
            assert exc.value.code == "APPROVAL_REQUIRED"
            await service.approve(plan["operation_id"])
            result = await service.execute(plan["operation_id"])
            assert result["status"] == "completed" and (root / "archive/final.txt").exists()
            assert (await service.verify(plan["operation_id"]))["complete"]
            undone = await service.undo_latest(str(mission))
            assert undone["status"] == "undone"
            assert (root / "draft.txt").exists() and not (root / "archive").exists()
        finally:
            await store.close()
    asyncio.run(scenario())


def test_plan_rejects_overwrite_and_delete(tmp_path: Path):
    async def scenario():
        root = tmp_path / "workspace"
        root.mkdir()
        (root / "a.txt").write_text("a", encoding="utf-8")
        (root / "b.txt").write_text("b", encoding="utf-8")
        store = Store(tmp_path / "app.sqlite")
        await store.open()
        try:
            service = ActionService(store)
            with pytest.raises(ToolError) as exc:
                await service.create_plan(ActionPlanRequest(mission_id=uuid4(), root=str(root), actions=[
                    {"kind": "move", "source": "a.txt", "destination": "b.txt"},
                ]))
            assert exc.value.code == "CONFLICT"
        finally:
            await store.close()
    asyncio.run(scenario())


def test_approved_plan_is_interrupted_and_can_be_resumed(tmp_path: Path):
    async def scenario():
        root = tmp_path / "workspace"
        root.mkdir()
        (root / "draft.txt").write_text("resume", encoding="utf-8")
        db_path = tmp_path / "app.sqlite"
        store = Store(db_path)
        await store.open()
        service = ActionService(store)
        mission = str(uuid4())
        plan = await service.create_plan(ActionPlanRequest(mission_id=mission, root=str(root), actions=[
            {"kind": "rename", "source": "draft.txt", "destination": "restored.txt"},
        ]))
        await service.approve(plan["operation_id"])
        await store.close()
        reopened = Store(db_path)
        await reopened.open()
        try:
            assert (await reopened.recover_operations()) == [plan["operation_id"]]
            resumed = await ActionService(reopened).resume(plan["operation_id"])
            assert resumed["status"] == "completed" and (root / "restored.txt").exists()
        finally:
            await reopened.close()
    asyncio.run(scenario())
