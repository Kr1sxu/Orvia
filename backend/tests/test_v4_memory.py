"""V4-003真实SQLite、本地精确来源及固定Main mock；不读取Key、不调用云。"""

import asyncio
import json
from uuid import uuid4

import pytest

from orvia_backend.configuration.client import Completion, ModelUnavailable
from orvia_backend.memory import MemoryService, MemoryError
from orvia_backend.memory.service import encoded, size
from test_chat import setup, create


async def prepare(tmp_path):
    app = await setup(tmp_path)
    memory = MemoryService(app.chat)
    await memory.open()
    cid = (await create(app))["id"]
    return app, memory, cid


async def round_(app, cid, text, status="completed", assistant="合成回答", explicit=True):
    rid = str(uuid4())
    await app.chat.repository.claim(cid, rid, text if explicit else "natural:" + text)
    data = {"request_id": rid} if explicit else None
    await app.chat.repository.append(cid, "user", text, data=data)
    await app.chat.repository.append(cid, "system", "合成工具状态", "tool", data)
    if assistant is not None:
        await app.chat.repository.append(cid, "assistant", assistant, data=data)
    await app.chat.repository.finish(cid, rid, status)
    return rid


class ApprovedModel:
    def __init__(self, change=None):
        self.calls = 0
        self.change = change
        self.sent = []

    async def complete(self, profile, messages, **kwargs):
        self.calls += 1
        self.sent = messages
        assert profile.model == "deepseek-flash" and kwargs == {"max_tokens": 1024}
        value = json.loads(messages[-1]["content"])
        sources = {source["source_id"]: source for source in value["sources"]}
        summary = []
        for row in value["rounds"]:
            source_id = next(message["source_id"] for message in row["messages"] if message["role"] == "user" and message["source_id"] in sources)
            summary.append({"text": sources[source_id]["quote"], "source_ids": [source_id]})
        result = {"summary": summary, "memories": [{"kind": item["kind"], "key": item["key"], "value": item["value"],
                  "source_ids": [source["source_id"] for source in item["sources"]]} for item in value["candidates"]]}
        if self.change:
            changed = self.change(result, value)
            if hasattr(changed, "__await__"):
                await changed
        return Completion(json.dumps(result, ensure_ascii=False), (), "stop", {})


@pytest.mark.parametrize("cache_loss", ["pruned", "restart", "interrupted"])
def test_attempt_fact_survives_preview_cache_loss(tmp_path, cache_loss):
    """真实失败后的预览淘汰，以及断电running事实均不能重新授予同批调用。"""
    async def run():
        app, memory, cid = await prepare(tmp_path)
        try:
            await round_(app, cid, "我的偏好是简洁回答")
            packet = await memory.preview(cid)
            model = ApprovedModel(lambda result, _: result.update(arbitrary="invalid"))
            app.chat.client = model
            with pytest.raises(MemoryError, match="INVALID_MEMORY"):
                await memory.generate(cid, packet["revision"])
            async with app.store._lock:
                db = app.store._db()
                if cache_loss == "pruned":
                    for index in range(20):
                        await db.execute("INSERT INTO memory_batches VALUES(?,?,?,'prepared')", (cid, f"old-{index}", '{}'))
                else:
                    await db.execute("DELETE FROM memory_batches WHERE cid=?", (cid,))
                if cache_loss == "interrupted":
                    await db.execute("UPDATE memory_attempts SET state='running' WHERE cid=?", (cid,))
            if cache_loss != "pruned":
                memory = MemoryService(app.chat)
                await memory.open()
            rebuilt = await memory.preview(cid)
            assert rebuilt["revision"] == packet["revision"]
            if cache_loss == "pruned":
                async with app.store._lock:
                    assert not await memory._rows(app.store._db(), "SELECT 1 FROM memory_batches WHERE cid=? AND revision=?", (cid, packet["revision"]))
                await memory.preview(cid)
            with pytest.raises(MemoryError, match="ALREADY_ATTEMPTED"):
                await memory.generate(cid, rebuilt["revision"])
            assert model.calls == 1
            async with app.store._lock:
                state = (await memory._rows(app.store._db(), "SELECT state FROM memory_attempts WHERE cid=?", (cid,)))[0][0]
            assert state == ("interrupted" if cache_loss == "interrupted" else "failed")
        finally:
            await app.close()
    asyncio.run(run())


def test_attempt_budget_refuses_without_network_or_pruning_facts(tmp_path):
    async def run():
        app, memory, cid = await prepare(tmp_path)
        try:
            await round_(app, cid, "我的项目是合成预算项目")
            packet = await memory.preview(cid)
            model = ApprovedModel()
            app.chat.client = model
            async with app.store._lock:
                for index in range(128):
                    await app.store._db().execute("INSERT INTO memory_attempts VALUES(?,?,'interrupted')", (cid, f"attempt-{index}"))
            with pytest.raises(MemoryError, match="MEMORY_BUDGET"):
                await memory.generate(cid, packet["revision"])
            assert model.calls == 0
            async with app.store._lock:
                assert (await memory._rows(app.store._db(), "SELECT count(*) FROM memory_attempts WHERE cid=?", (cid,)))[0][0] == 128
        finally:
            await app.close()
    asyncio.run(run())


def test_large_previous_summary_can_roll_with_actual_packet_budget(tmp_path):
    async def run():
        app, memory, cid = await prepare(tmp_path)
        try:
            for index in range(9):
                await round_(app, cid, f"合成原始轮{index}", assistant="答" * 500)
            app.chat.client = ApprovedModel()
            packet = await memory.preview(cid)
            await memory.generate(cid, packet["revision"])
            previous = (await memory.context(cid))["summary"]
            assert size(previous) > 7000
            await round_(app, cid, "下一短轮")
            next_packet = await memory.preview(cid)
            assert next_packet["rounds"] and next_packet["bytes"] <= 24576 and size(next_packet) <= 32768
            await memory.generate(cid, next_packet["revision"])
            assert app.chat.client.calls == 2
        finally:
            await app.close()
    asyncio.run(run())


def test_five_rounds_legacy_tool_current_and_terminal_facts(tmp_path):
    async def run():
        app, memory, cid = await prepare(tmp_path)
        try:
            ids = [await round_(app, cid, f"合成请求{i}", explicit=False) for i in range(6)]
            failed = await round_(app, cid, "合成失败", "failed", assistant=None)
            current = await round_(app, cid, "合成待审批", "waiting_approval", assistant=None)
            incomplete = await round_(app, cid, "合成缺助手", assistant=None)
            context = await memory.context(cid)
            assert [item["request_id"] for item in context["rounds"]] == [*ids[-4:], failed]
            assert context["rounds"][-1]["status"] == "failed"
            assert context["current"]["request_id"] == incomplete
            assert context["current"]["status"] == "completed_without_pair"
            assert len(context["rounds"][0]["messages"]) == 3
            async with app.store._lock:
                await app.store._db().execute("DELETE FROM chat_requests WHERE request_id=?", (incomplete,))
            assert (await memory.context(cid))["current"]["request_id"] == current
        finally:
            await app.close()
    asyncio.run(run())


@pytest.mark.parametrize("status", ["failed", "cancelled", "interrupted"])
def test_failed_cancelled_interrupted_summary_keeps_status(tmp_path, status):
    async def run():
        app, memory, cid = await prepare(tmp_path)
        try:
            first = await round_(app, cid, "合成较早轮次", status)
            for i in range(5):
                await round_(app, cid, f"后续合成{i}")
            packet = await memory.preview(cid)
            model = ApprovedModel()
            app.chat.client = model
            await memory.generate(cid, packet["revision"])
            summary = (await memory.context(cid))["summary"]
            assert summary["statuses"] == [{"request_id": first, "status": status}]
            assert model.sent == [{"role": "system", "content": packet["instructions"]}, {"role": "user", "content": encoded(packet["input"])}]
            assert packet["bytes"] == len(model.sent[0]["content"].encode()) + len(model.sent[1]["content"].encode())
        finally:
            await app.close()
    asyncio.run(run())


def test_long_context_budget_and_explicit_sensitive_exclusion(tmp_path):
    async def run():
        app, memory, cid = await prepare(tmp_path)
        try:
            for i in range(7):
                await round_(app, cid, "长" * 1800 + str(i), assistant="答" * 1600)
            await round_(app, cid, "我的偏好是密码不要保存；身份证123456789012345678", assistant=None, status="pending")
            context = await memory.context(cid)
            assert size(context) <= 24576 and context["truncated"]
            assert all(size(row) <= 4096 for row in context["rounds"])
            assert "123456789012345678" not in encoded(context)
            listing = await memory.list(cid)
            assert not listing["candidates"] and listing["truncated"]
            packet = await memory.preview(cid)
            assert packet["bytes"] <= 24576 and size(packet) <= 32768
        finally:
            await app.close()
    asyncio.run(run())


def test_local_candidates_cancel_zero_calls_then_generate_persist(tmp_path):
    async def run():
        app, memory, cid = await prepare(tmp_path)
        try:
            await round_(app, cid, "我的偏好是简洁回答。我的项目是合成航线。合成人甲的角色是负责人。")
            model = ApprovedModel()
            app.chat.client = model
            listing = await memory.list(cid)
            assert {item["kind"] for item in listing["candidates"]} == {"preference", "project", "person"}
            packet = await memory.preview(cid)
            assert model.calls == 0
            result = await memory.generate(cid, packet["revision"])
            assert len(result["memories"]) == 3 and all(item["status"] == "verified" for item in result["memories"])
            assert (await memory.search("合成航线"))["memories"]
            with pytest.raises(MemoryError, match="ALREADY_ATTEMPTED"):
                await memory.generate(cid, packet["revision"])
            assert model.calls == 1
        finally:
            await app.close()
        app = await setup(tmp_path)
        try:
            memory = MemoryService(app.chat)
            await memory.open()
            assert len((await memory.list(cid))["memories"]) == 3
            assert (await memory.search("合成航线"))["memories"]
            with pytest.raises(MemoryError, match="ALREADY_ATTEMPTED"):
                await memory.generate(cid, packet["revision"])
        finally:
            await app.close()
    asyncio.run(run())


@pytest.mark.parametrize("attack", ["foreign", "invention", "key", "empty_summary", "wrong_coverage", "extra"])
def test_malicious_model_rejects_without_partial_fact_write(tmp_path, attack):
    async def run():
        app, memory, cid = await prepare(tmp_path)
        try:
            await round_(app, cid, "我的偏好是简洁回答")
            for i in range(5):
                await round_(app, cid, f"合成后续{i}")
            packet = await memory.preview(cid)
            def change(result, input_value):
                if attack == "foreign": result["memories"][0]["source_ids"] = ["message:" + str(uuid4())]
                if attack == "invention": result["memories"][0]["value"] = "无依据的虚构值"
                if attack == "key": result["memories"][0]["key"] = "password"
                if attack == "empty_summary": result["summary"] = []
                if attack == "wrong_coverage":
                    source = next(item for item in input_value["sources"] if item["status"] == "message")
                    result["summary"] = [{"text": source["quote"], "source_ids": [source["source_id"]]}]
                if attack == "extra": result["arbitrary"] = "invalid"
            app.chat.client = ApprovedModel(change)
            with pytest.raises(MemoryError, match="INVALID_MEMORY"):
                await memory.generate(cid, packet["revision"])
            assert not (await memory.list(cid))["memories"]
            assert (await memory.context(cid))["summary"] is None
            with pytest.raises(MemoryError, match="ALREADY_ATTEMPTED"):
                await memory.generate(cid, packet["revision"])
            assert app.chat.client.calls == 1
        finally:
            await app.close()
    asyncio.run(run())


def test_preview_stale_before_and_after_call(tmp_path):
    async def run():
        app, memory, cid = await prepare(tmp_path)
        try:
            await round_(app, cid, "我的偏好是简洁")
            old = await memory.preview(cid)
            await round_(app, cid, "我的项目是新合成项目")
            app.chat.client = ApprovedModel()
            with pytest.raises(MemoryError, match="STALE_MEMORY"):
                await memory.generate(cid, old["revision"])
            assert app.chat.client.calls == 0
            packet = await memory.preview(cid)
            async def change(result, input_value):
                await app.chat.repository.append(cid, "user", "我的项目是生成期间的新项目", "memory_correction", {"request_id": None})
            app.chat.client = ApprovedModel(change)
            with pytest.raises(MemoryError, match="STALE_MEMORY"):
                await memory.generate(cid, packet["revision"])
            assert not (await memory.list(cid))["memories"]
        finally:
            await app.close()
    asyncio.run(run())


def test_missing_credentials_no_retry_and_local_still_works(tmp_path):
    async def run():
        app, memory, cid = await prepare(tmp_path)
        try:
            await round_(app, cid, "我的项目是合成本地项目")
            packet = await memory.preview(cid)
            with pytest.raises(ModelUnavailable, match="MISSING_CREDENTIAL"):
                await memory.generate(cid, packet["revision"])
            assert (await memory.list(cid))["candidates"]
            assert not (await memory.list(cid))["memories"]
            with pytest.raises(MemoryError, match="ALREADY_ATTEMPTED"):
                await memory.generate(cid, packet["revision"])
        finally:
            await app.close()
    asyncio.run(run())


def test_cross_chat_conflict_correct_forget_and_delete(tmp_path):
    async def run():
        app, memory, cid = await prepare(tmp_path)
        try:
            other = (await create(app))["id"]
            app.chat.client = ApprovedModel()
            for conversation, text in ((cid, "我的偏好是简洁回答"), (other, "我的偏好是详细回答")):
                await round_(app, conversation, text)
                packet = await memory.preview(conversation)
                await memory.generate(conversation, packet["revision"])
            first = (await memory.list(cid))["memories"][0]
            assert first["status"] == "conflict"
            assert not (await memory.search("回答"))["memories"]
            with pytest.raises(MemoryError, match="NOT_FOUND"):
                await memory.correct(other, first["id"], "详细回答")
            corrected = await memory.correct(cid, first["id"], "详细回答")
            assert any(item["value"] == "详细回答" and item["status"] == "verified" for item in corrected["memories"])
            assert all(item["value"] != "简洁回答" for item in corrected["candidates"])
            current = next(item for item in corrected["memories"] if item["status"] == "verified")
            await memory.forget(cid, current["id"])
            async with app.store._lock:
                assert (await memory._rows(app.store._db(), "SELECT count(*) FROM memory_attempts WHERE cid=?", (cid,)))[0][0] == 1
            assert all(item["id"] != current["id"] for item in (await memory.list(cid))["memories"])
            assert all(item["value"] != "详细回答" for item in (await memory.list(cid))["candidates"])
            await memory.delete_conversation(cid)
            async with app.store._lock:
                for table in ("memory_candidates", "memory_records", "memory_summaries", "memory_batches", "memory_attempts", "memory_revocations", "memory_fts"):
                    async with app.store._db().execute(f"SELECT count(*) FROM {table} WHERE cid=?", (cid,)) as cursor:
                        assert (await cursor.fetchone())[0] == 0
            assert (await app.chat.repository.messages(cid))[1] > 0
        finally:
            await app.close()
    asyncio.run(run())


def test_document_and_browser_precise_candidate_revocation(tmp_path):
    async def run():
        app, memory, cid = await prepare(tmp_path)
        try:
            doc = await app.chat.documents.save(cid, "synthetic.docx", b"synthetic", {"units": [{"number": 1, "text": "我的项目是合成文档项目", "locator": "段落1"}], "error": None})
            web = await app.chat.evidence.save(cid, {"content": "合成人乙的角色是研究员", "title": "合成网页", "source_url": "https://example.org/synthetic"})
            await app.chat.natural.material_added(cid, "document", doc["evidence_id"])
            await app.chat.natural.material_added(cid, "browser", web["evidence_id"])
            packet = await memory.preview(cid)
            assert {source["origin"].split(":")[0] for source in packet["input"]["sources"]} == {"document", "browser"}
            app.chat.client = ApprovedModel()
            result = await memory.generate(cid, packet["revision"])
            assert len(result["memories"]) == 2
            await memory.revoke_source(cid, "document:" + doc["evidence_id"])
            assert all(record["kind"] != "project" for record in (await memory.search("合成文档项目"))["memories"])
            assert (await memory.search("研究员"))["memories"]
            assert (await app.chat.documents.get(cid, doc["evidence_id"]))["units"][0]["text"]
        finally:
            await app.close()
    asyncio.run(run())


def test_long_term_sources_survive_raw_message_window(tmp_path):
    async def run():
        app, memory, cid = await prepare(tmp_path)
        try:
            await round_(app, cid, "我的项目是合成长存项目")
            packet = await memory.preview(cid)
            app.chat.client = ApprovedModel()
            await memory.generate(cid, packet["revision"])
            async with app.store._lock:
                db = app.store._db()
                for i in range(1005):
                    message = app.chat.repository._message("system", f"合成工具{i}", "tool", {})
                    await db.execute("INSERT INTO chat_messages(conversation_id,message_json) VALUES(?,?)", (cid, encoded(message)))
            found = (await memory.search("合成长存项目"))["memories"]
            assert found and found[0]["status"] == "verified"
            context = await memory.context(cid)
            assert context["truncated"] and len(context["rounds"]) == 1
            assert context["rounds"][0]["status"] == "completed"
        finally:
            await app.close()
    asyncio.run(run())


def test_multi_source_support_withdraws_only_removed_origin(tmp_path):
    async def run():
        app, memory, cid = await prepare(tmp_path)
        try:
            await round_(app, cid, "我的项目是合成双源项目")
            app.chat.client = ApprovedModel()
            first = await memory.preview(cid)
            await memory.generate(cid, first["revision"])
            doc = await app.chat.documents.save(cid, "double.docx", b"double", {"units": [{"number": 1, "text": "我的项目是合成双源项目", "locator": "段落1"}], "error": None})
            await app.chat.natural.material_added(cid, "document", doc["evidence_id"])
            second = await memory.preview(cid)
            await memory.generate(cid, second["revision"])
            assert len((await memory.list(cid))["memories"][0]["sources"]) == 2
            await memory.revoke_source(cid, "document:" + doc["evidence_id"])
            found = (await memory.search("双源"))["memories"]
            assert found and found[0]["status"] == "verified" and len(found[0]["sources"]) == 1
        finally:
            await app.close()
    asyncio.run(run())


def test_rolling_summary_preserves_previous_original_items_and_version(tmp_path):
    async def run():
        app, memory, cid = await prepare(tmp_path)
        try:
            first = await round_(app, cid, "合成旧轮原文")
            for i in range(5):
                await round_(app, cid, f"合成后来{i}")
            app.chat.client = ApprovedModel()
            preview = await memory.preview(cid)
            await memory.generate(cid, preview["revision"])
            old = (await memory.context(cid))["summary"]
            await round_(app, cid, "合成新轮")
            second = await memory.preview(cid)
            assert second["input"]["previous_summary"] == old
            await memory.generate(cid, second["revision"])
            new = (await memory.context(cid))["summary"]
            assert new["revision"] != old["revision"]
            assert old["items"][0] in new["items"]
            assert new["statuses"][0]["request_id"] == first and len(new["statuses"]) == 2
            old_source = old["sources"][0]["source_id"].split(":", 1)[1]
            async with app.store._lock:
                await app.store._db().execute("DELETE FROM chat_messages WHERE conversation_id=? AND json_extract(message_json,'$.id')=?", (cid, old_source))
            assert (await memory.context(cid))["summary"] is None
        finally:
            await app.close()
    asyncio.run(run())


def test_synchronize_mutation_before_transaction_rejects_candidates(tmp_path):
    async def run():
        app, memory, cid = await prepare(tmp_path)
        try:
            await round_(app, cid, "我的项目是合成并发来源")
            original = memory._snapshot
            async def racing(conversation):
                snapshot = await original(conversation)
                user = next(source for source in snapshot["sources"].values() if source["status"] == "user_statement")
                async with app.store._lock:
                    await app.store._db().execute("DELETE FROM chat_messages WHERE conversation_id=? AND json_extract(message_json,'$.id')=?", (cid, user["source_id"].split(":", 1)[1]))
                return snapshot
            memory._snapshot = racing
            with pytest.raises(MemoryError, match="SOURCE_CHANGED"):
                await memory.synchronize(cid)
            memory._snapshot = original
            assert not (await memory.list(cid))["candidates"]
        finally:
            await app.close()
    asyncio.run(run())


def test_forget_one_value_does_not_revoke_other_fact_same_message(tmp_path):
    async def run():
        app, memory, cid = await prepare(tmp_path)
        try:
            await round_(app, cid, "我的项目是合成共享来源。我的偏好是简洁。")
            app.chat.client = ApprovedModel()
            packet = await memory.preview(cid)
            result = await memory.generate(cid, packet["revision"])
            forgotten = next(record for record in result["memories"] if record["kind"] == "project")
            await memory.forget(cid, forgotten["id"])
            assert (await memory.search("简洁"))["memories"]
            assert all(record["kind"] != "project" for record in (await memory.list(cid))["memories"])
            assert all(candidate["kind"] != "project" for candidate in (await memory.list(cid))["candidates"])
            assert (await app.chat.repository.messages(cid))[1] == 3
        finally:
            await app.close()
    asyncio.run(run())


def test_full_listing_and_context_transport_budgets(tmp_path):
    async def run():
        app, memory, cid = await prepare(tmp_path)
        try:
            for i in range(20):
                await round_(app, cid, f"项目合成{i}的目标是" + "长" * 90 + "。" + "余" * 500)
            listing = await memory.list(cid)
            assert size(listing) <= 32768 and listing["truncated"]
            packet = await memory.preview(cid)
            assert packet["bytes"] <= 24576 and size(packet) <= 32768
            assert size(await memory.context(cid, "合成")) <= 24576
            assert not (await memory.search("！！！"))["memories"]
        finally:
            await app.close()
    asyncio.run(run())
