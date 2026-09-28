import asyncio
import json
from uuid import uuid4

from orvia_backend.application import Application


async def call(app, method, params=None):
    return await app.handle(json.dumps({"v": 1, "id": str(uuid4()), "method": method, "params": params or {}}).encode())


def test_context_protocol(tmp_path):
    async def scenario():
        app = Application()
        try:
            await call(app, "hello")
            await call(app, "initialize", {"data_directory": str(tmp_path), "credentials": {}})
            indexed = await call(app, "context.index", {"mission_id": "m1", "source": "synthetic.md", "text": "审批后移动文件。"})
            assert indexed["ok"]
            found = await call(app, "context.search", {"mission_id": "m1", "query": "移动"})
            assert found["result"]["evidence"][0]["source"] == "synthetic.md"
        finally:
            await app.close()
    asyncio.run(scenario())
