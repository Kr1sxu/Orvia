"""V4-003真实Application/SQLite接入；云端只用合成异步模型替身。"""

import asyncio
import json
from uuid import uuid4

from orvia_backend.configuration.client import Completion
from test_chat import call, create, setup


def send(cid, text):
    return {"id": cid, "request_id": str(uuid4()), "text": text}


class Model:
    def __init__(self):
        self.calls = []

    async def stream(self, profile, messages, **options):
        assert profile.model == "deepseek-flash"
        self.calls.append(messages)
        value = {"steps": [{"kind": "answer", "query": "合成普通解释"}]} if "意图理解器" in messages[0]["content"] else {"answer": "合成解释，不代表执行事实。"}
        text = json.dumps(value, ensure_ascii=False)
        if options.get("on_delta"):
            await options["on_delta"](text)
        return Completion(text, (), "stop", {})


def test_five_rounds_local_greetings_and_fixed_main_receives_structured_window(tmp_path):
    async def run():
        app = await setup(tmp_path)
        try:
            cid = (await create(app))["id"]
            model = Model()
            app.chat.client = model
            ids = []
            for _ in range(8):
                request = send(cid, "你好")
                ids.append(request["request_id"])
                assert (await call(app, "chat.natural", request))["ok"]
            assert not model.calls
            window = (await call(app, "memory.context", {"id": cid}))["result"]
            assert [row["request_id"] for row in window["rounds"]] == ids[-5:]
            assert window["current"] is None
            assert all(len(row["messages"]) == 2 for row in window["rounds"])
            answer = await call(app, "chat.natural", send(cid, "解释普通概念"))
            assert answer["ok"] and model.calls
            context = json.loads(model.calls[-1][1]["content"].split("：", 1)[1])
            assert [row["request_id"] for row in context["rounds"]] == ids[-5:]
            assert context["current"]["status"] == "pending"
            assert "memories" not in context  # 跨会话本地命中不构成正文外发许可。
        finally:
            await app.close()
    asyncio.run(run())


def test_memory_protocol_rejects_renderer_grants_and_unknown_fields(tmp_path):
    async def run():
        app = await setup(tmp_path)
        try:
            cid = (await create(app))["id"]
            for method, params in (
                ("memory.list", {"id": cid, "path": "private"}),
                ("memory.preview", {"id": cid, "sources": ["other"]}),
                ("memory.generate", {"id": cid, "revision": "0" * 64, "approved": True}),
                ("memory.search", {"query": "项目", "model": "other"}),
                ("memory.correct", {"id": cid, "memory_id": "0" * 64, "value": "合成", "approval": True}),
            ):
                result = await call(app, method, params)
                assert not result["ok"] and result["error"]["code"] == "INVALID_PARAMS"
        finally:
            await app.close()
    asyncio.run(run())


def test_chat_delete_cleans_all_memory_tables_and_keeps_no_derived_body(tmp_path):
    async def run():
        app = await setup(tmp_path)
        try:
            cid = (await create(app))["id"]
            assert (await call(app, "chat.natural", send(cid, "你好")))["ok"]
            preview = await call(app, "memory.list", {"id": cid})
            assert preview["ok"]
            async with app.store._lock:
                db = app.store._db()
                await db.execute("INSERT INTO memory_candidates VALUES(?,?,?)", (cid, "synthetic", '{}'))
                await db.execute("INSERT INTO memory_records VALUES(?,?,?)", (cid, "synthetic", '{}'))
                await db.execute("INSERT INTO memory_summaries VALUES(?,?)", (cid, '{}'))
                await db.execute("INSERT INTO memory_batches VALUES(?,?,?,'prepared')", (cid, "synthetic", '{}'))
                await db.execute("INSERT INTO memory_attempts VALUES(?,?,'interrupted')", (cid, "synthetic"))
                await db.execute("INSERT INTO memory_revocations VALUES(?,?)", (cid, "synthetic"))
                await db.execute("INSERT INTO memory_fts VALUES(?,?,?)", ("synthetic", cid, "synthetic"))
            deleted = await call(app, "chat.delete", {"id": cid})
            assert deleted["ok"]
            async with app.store._lock:
                for table in ("memory_candidates", "memory_records", "memory_summaries", "memory_batches", "memory_attempts", "memory_revocations", "memory_fts"):
                    async with app.store._db().execute(f"SELECT count(*) FROM {table} WHERE cid=?", (cid,)) as cursor:
                        assert (await cursor.fetchone())[0] == 0
            assert not (await call(app, "memory.context", {"id": cid}))["ok"]
        finally:
            await app.close()
    asyncio.run(run())
