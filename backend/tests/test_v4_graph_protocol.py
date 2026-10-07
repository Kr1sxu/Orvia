"""V4-005固定Application/真实SQLite；默认不读取凭据或调用模型。"""

import asyncio
import json
import pytest

from test_chat import call, create, setup
from orvia_backend.configuration.client import Completion


@pytest.mark.parametrize("mode", ["missing", "timeout"])
def test_graph_model_failure_has_stable_protocol_and_no_second_attempt(tmp_path, mode):
    class TimeoutModel:
        calls = 0

        async def complete(self, *_args, **_options):
            self.calls += 1
            raise TimeoutError()

    async def run():
        app = await setup(tmp_path)
        try:
            cid = (await create(app))["id"]
            await app.chat.repository.append(cid, "user", "项目合成航线")
            model = TimeoutModel()
            if mode == "timeout":
                app.chat.client = model
            preview = await call(app, "graph.preview", {"id": cid})
            assert preview["ok"]
            packet = {"id": cid, "revision": preview["result"]["revision"]}
            first = await call(app, "graph.generate", packet)
            assert not first["ok"] and first["error"]["code"] == ("MISSING_CREDENTIAL" if mode == "missing" else "MODEL_TIMEOUT")
            second = await call(app, "graph.generate", packet)
            assert not second["ok"] and second["error"]["code"] == "GRAPH_ALREADY_ATTEMPTED"
            assert model.calls == (0 if mode == "missing" else 1)
            assert (await call(app, "graph.list", {"id": cid}))["result"]["relations"] == []
        finally:
            await app.close()
    asyncio.run(run())


def test_graph_methods_reject_arbitrary_scope_sql_and_grants(tmp_path):
    async def run():
        app = await setup(tmp_path)
        try:
            cid = (await create(app))["id"]
            for method, params in (
                ("graph.list", {"id": cid, "sql": "SELECT private"}),
                ("graph.preview", {"id": cid, "sources": ["other"]}),
                ("graph.generate", {"id": cid, "revision": "0" * 64, "approved": True}),
                ("graph.query", {"query": "合成", "hops": 3}),
                ("graph.query", {"query": "合成", "hops": True}),
                ("graph.query", {"query": "合成", "path": "private"}),
                ("graph.query", {"query": "合成", "entity_id": "unknown"}),
            ):
                result = await call(app, method, params)
                assert not result["ok"] and result["error"]["code"] == "INVALID_PARAMS"
            empty = await call(app, "graph.query", {"query": "合成"})
            assert empty["ok"] and not empty["result"]["entities"] and not empty["result"]["paths"]
        finally:
            await app.close()
    asyncio.run(run())


def test_graph_chat_delete_removes_body_attempts_and_rejects_late_preview(tmp_path):
    async def run():
        app = await setup(tmp_path)
        try:
            cid = (await create(app))["id"]
            assert (await call(app, "graph.list", {"id": cid}))["ok"]
            async with app.store._lock:
                db = app.store._db()
                for table in ("graph_entities", "graph_relations"):
                    await db.execute(f"INSERT INTO {table} VALUES(?,?,?)", (cid, "0" * 64, json.dumps({"synthetic": True})))
                await db.execute("INSERT INTO graph_batches VALUES(?,?,?,'prepared')", (cid, "0" * 64, '{}'))
                await db.execute("INSERT INTO graph_attempts VALUES(?,?,'interrupted')", (cid, "0" * 64))
                await db.execute("INSERT INTO graph_processed VALUES(?,?,?)", (cid, "synthetic", "0" * 64))
                await db.execute("INSERT INTO graph_revocations VALUES(?,?)", (cid, "synthetic"))
            assert (await call(app, "chat.delete", {"id": cid}))["ok"]
            async with app.store._lock:
                for table in ("graph_entities", "graph_relations", "graph_batches", "graph_attempts", "graph_processed", "graph_revocations"):
                    async with app.store._db().execute(f"SELECT count(*) FROM {table} WHERE cid=?", (cid,)) as cursor:
                        assert (await cursor.fetchone())[0] == 0
            assert not (await call(app, "graph.preview", {"id": cid}))["ok"]
        finally:
            await app.close()
    asyncio.run(run())


def test_graph_application_approved_document_then_material_remove_revokes_support(tmp_path):
    class Model:
        def __init__(self):
            self.calls = []

        async def complete(self, profile, messages, **options):
            assert profile.model == "deepseek-flash" and options == {"max_tokens": 1536}
            self.calls.append(messages)
            source = json.loads(messages[1]["content"])["sources"][0]
            result = {"entities": [
                {"key": "a", "name": "合成人甲", "kind": "person", "source_ids": [source["source_id"]]},
                {"key": "b", "name": "合成航线", "kind": "project", "source_ids": [source["source_id"]]},
            ], "relations": [{"from_key": "a", "to_key": "b", "kind": "responsible_for", "source_id": source["source_id"], "quote": "合成人甲负责项目合成航线"}]}
            return Completion(json.dumps(result, ensure_ascii=False), (), "stop", {})

    async def run():
        app = await setup(tmp_path)
        try:
            cid = (await create(app))["id"]
            model = Model()
            app.chat.client = model
            saved = await app.chat.documents.save(cid, "synthetic.docx", b"synthetic", {"units": [{"number": 1, "text": "合成人甲负责项目合成航线", "locator": "段落1"}], "error": None})
            await app.chat.natural.material_added(cid, "document", saved["evidence_id"])
            preview = await call(app, "graph.preview", {"id": cid})
            assert preview["ok"] and not model.calls
            packet = preview["result"]
            generated = await call(app, "graph.generate", {"id": cid, "revision": packet["revision"]})
            assert generated["ok"] and len(generated["result"]["relations"]) == 1 and len(model.calls) == 1
            assert model.calls[0][0]["content"] == packet["instructions"]
            query = await call(app, "graph.query", {"query": "合成人甲"})
            assert query["ok"] and len(query["result"]["paths"]) == 1
            removed = await call(app, "chat.material.remove", {"id": cid, "kind": "document", "evidence_id": saved["evidence_id"]})
            assert removed["ok"]
            query = await call(app, "graph.query", {"query": "合成人甲"})
            assert query["ok"] and not query["result"]["entities"] and not query["result"]["paths"]
            assert len(model.calls) == 1
            assert (await app.chat.documents.get(cid, saved["evidence_id"]))["units"][0]["text"] == "合成人甲负责项目合成航线"
        finally:
            await app.close()
    asyncio.run(run())
