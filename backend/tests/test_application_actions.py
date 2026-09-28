import asyncio
import json
from uuid import uuid4

from orvia_backend.application import Application


async def call(app, method, params=None):
    return await app.handle(json.dumps({"v": 1, "id": str(uuid4()), "method": method, "params": params or {}}).encode())


def test_application_action_approval_boundary(tmp_path):
    async def scenario():
        root = tmp_path / "workspace"
        root.mkdir()
        (root / "draft.txt").write_text("synthetic", encoding="utf-8")
        app = Application()
        try:
            assert (await call(app, "hello"))["ok"]
            assert (await call(app, "initialize", {"data_directory": str(tmp_path), "credentials": {}}))["ok"]
            plan = await call(app, "computer.plan", {"mission_id": str(uuid4()), "root": str(root),
                "actions": [{"kind": "rename", "source": "draft.txt", "destination": "final.txt"}]})
            assert plan["result"]["requires_approval"]
            operation_id = plan["result"]["operation_id"]
            denied = await call(app, "computer.execute_action", {"operation_id": operation_id})
            assert denied["error"]["code"] == "APPROVAL_REQUIRED"
            assert (await call(app, "computer.approve", {"operation_id": operation_id}))["ok"]
            assert (await call(app, "computer.execute_action", {"operation_id": operation_id}))["result"]["status"] == "completed"
            assert (root / "final.txt").exists()
        finally:
            await app.close()
    asyncio.run(scenario())
