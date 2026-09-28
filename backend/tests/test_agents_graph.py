import asyncio
from pathlib import Path
from uuid import uuid4

from orvia_backend.agents import MissionGraph
from orvia_backend.storage import Store


def test_langgraph_pauses_for_approval_and_resumes(tmp_path: Path):
    async def scenario():
        root = tmp_path / "workspace"
        root.mkdir()
        (root / "draft.txt").write_text("synthetic", encoding="utf-8")
        store = Store(tmp_path / "app.sqlite")
        await store.open()
        try:
            async with MissionGraph(store, tmp_path / "checkpoints.sqlite") as graph:
                thread_id = "mission-thread"
                initial = await graph.start({
                    "mission_id": str(uuid4()), "goal": "整理合成目录", "root": str(root),
                    "actions": [{"kind": "rename", "source": "draft.txt", "destination": "final.txt"}],
                }, thread_id)
                assert initial["phase"] == "awaiting_approval"
                assert not (root / "final.txt").exists()
                completed = await graph.approve_and_resume(thread_id)
                assert completed["phase"] == "completed" and completed["completed"]
                assert (root / "final.txt").exists()
                assert any(item["kind"] == "verification" for item in completed["evidence"])
        finally:
            await store.close()
    asyncio.run(scenario())


def test_graph_rejects_empty_plan(tmp_path: Path):
    async def scenario():
        store = Store(tmp_path / "app.sqlite")
        await store.open()
        try:
            async with MissionGraph(store, tmp_path / "checkpoints.sqlite") as graph:
                result = await graph.start({"mission_id": str(uuid4()), "goal": "空任务", "root": str(tmp_path), "actions": []}, "empty")
                assert result["phase"] == "failed"
        finally:
            await store.close()
    asyncio.run(scenario())
