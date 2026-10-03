"""M20真实SQLite模型前缀持久化；合成增量不调用供应商或读取凭据。"""

import asyncio
import json
from uuid import uuid4

import pytest

from orvia_backend.computer.paths import ToolError
from test_chat import call, create, setup


@pytest.mark.parametrize("stop", ["before_sink", "after_sink", "failed", "cancelled", "paused"])
def test_model_prefix_is_durable_before_output_and_restores_once(tmp_path, stop):
    async def run():
        app = await setup(tmp_path)
        cid = (await create(app))["id"]
        rid = str(uuid4())
        await app.chat.repository.claim(cid, rid, "natural:合成中断回答")
        delivered = []
        prefix = "尚未核验的合成文字："
        async def sink(event):
            if event["kind"] == "model_delta":
                async with app.store._lock:
                    async with app.store._db().execute("SELECT model_text,last_seq FROM m20_streams WHERE conversation_id=? AND request_id=?", (cid, rid)) as cursor:
                        durable = await cursor.fetchone()
                assert durable[0] == prefix and durable[1] == event["seq"]
                if stop == "before_sink":
                    raise ToolError("STREAM_DISCONNECTED", "合成sink在输出前断开")
                delivered.append(event)
        app.chat.set_event_sink(sink)
        await app.chat.streams.start(cid, rid)
        if stop == "before_sink":
            with pytest.raises(ToolError, match="合成sink"):
                await app.chat.streams.emit(cid, rid, "model_delta", {"text": prefix, "provisional": True})
        else:
            await app.chat.streams.emit(cid, rid, "model_delta", {"text": prefix, "provisional": True})
        if stop in {"failed", "cancelled", "paused"}:
            payload = {"code": "MODEL_UNAVAILABLE", "message": "合成断流"} if stop == "failed" else {"action": "stream_fallback", "question": "需另行确认"} if stop == "paused" else {"label": "已取消"}
            await app.chat.streams.emit(cid, rid, stop, payload)
            initial = (await call(app, "chat.get", {"id": cid}))["result"]
            partial = [item for item in initial["messages"] if item["kind"] == "model_partial"]
            assert len(partial) == 1 and partial[0]["data"]["state"] == stop
        sequence = (await app.chat.streams.get(cid, rid))["last_seq"]
        await app.close()
        app = await setup(tmp_path)
        try:
            async def forbidden(*args, **kwargs):
                raise AssertionError("重启历史不得调用模型或重放事件")
            app.chat.client.stream = app.chat.client.complete = forbidden
            app.chat.set_event_sink(forbidden)
            first, second = await asyncio.gather(call(app, "chat.get", {"id": cid}), call(app, "chat.get", {"id": cid}))
            snapshot = first["result"]
            partial = [item for item in snapshot["messages"] if item["kind"] == "model_partial"]
            assert len(partial) == 1
            data = partial[0]["data"]
            assert data["request_id"] == rid and data["text"] == prefix and data["provisional"] is True
            assert data["last_seq"] == sequence and data["state"] == ("interrupted" if stop in {"before_sink", "after_sink", "paused"} else stop)
            assert snapshot["stream"]["last_seq"] == sequence and "model_text" not in snapshot["stream"]
            assert snapshot["grant"] is None and snapshot["operation"] is None
            assert not any(item["kind"] in {"synthesis", "natural_answer", "publication"} for item in snapshot["messages"])
            assert [item["id"] for item in second["result"]["messages"] if item["kind"] == "model_partial"] == [partial[0]["id"]]
            original_id = partial[0]["id"]
        finally:
            await app.close()
        app = await setup(tmp_path)
        try:
            third = (await call(app, "chat.get", {"id": cid}))["result"]
            assert [item["id"] for item in third["messages"] if item["kind"] == "model_partial"] == [original_id]
            denied = await call(app, "chat.publication.preview", {"id": cid, "message_id": original_id, "format": "docx"})
            assert not denied["ok"]
        finally:
            await app.close()
    asyncio.run(run())


def test_model_display_limit_preserves_exact_emitted_prefix_and_one_partial(tmp_path):
    async def run():
        app = await setup(tmp_path)
        try:
            cid = (await create(app))["id"]
            rid = str(uuid4())
            delivered = []
            async def sink(event):
                if event["kind"] == "model_delta":
                    delivered.append(event["payload"]["text"])
            app.chat.set_event_sink(sink)
            await app.chat.streams.start(cid, rid)
            with pytest.raises(ToolError) as error:
                await app.chat.streams.emit(cid, rid, "model_delta", {"text": "\n" * 13000, "provisional": True})
            assert error.value.code == "OUTPUT_LIMIT"
            await app.chat.streams.emit(cid, rid, "paused", {"action": "stream_fallback", "question": "合成暂停"})
            snapshot = (await call(app, "chat.get", {"id": cid}))["result"]
            partial = next(item for item in snapshot["messages"] if item["kind"] == "model_partial")
            assert partial["data"]["text"] == "".join(delivered)
            assert len(json.dumps(partial["data"]["text"]).encode()) <= 24 * 1024
            await app.chat.streams.emit(cid, rid, "failed", {"code": "OUTPUT_LIMIT", "message": "合成超过预算"})
            after = (await call(app, "chat.get", {"id": cid}))["result"]
            records = [item for item in after["messages"] if item["kind"] == "model_partial"]
            assert len(records) == 1 and records[0]["id"] == partial["id"] and records[0]["data"]["state"] == "failed"
            assert records[0]["data"]["text"] == "".join(delivered)
        finally:
            await app.close()
    asyncio.run(run())


@pytest.mark.parametrize("kind", ["synthesis", "natural_answer"])
@pytest.mark.parametrize("finished", [True, False])
def test_saved_valid_answer_before_terminal_event_is_not_unverified_partial(tmp_path, kind, finished):
    async def run():
        app = await setup(tmp_path)
        cid = (await create(app))["id"]
        rid = str(uuid4())
        await app.chat.repository.claim(cid, rid, "合成已验证答案保存窗口")
        await app.chat.streams.start(cid, rid)
        prefix = "已经完整校验并保存的合成答案"
        await app.chat.streams.emit(cid, rid, "model_delta", {"text": prefix, "provisional": True})
        data = {"request_id": rid, "stream_prefix_chars": await app.chat.streams.prefix_size(cid, rid), "answer": prefix}
        await app.chat.repository.append(cid, "assistant", prefix, kind, data)
        if finished:
            await app.chat.repository.finish(cid, rid)
        last_seq = (await app.chat.streams.get(cid, rid))["last_seq"]
        # 终态事件没有emit；保存事实与流metadata是独立事务窗口。
        await app.close()
        app = await setup(tmp_path)
        try:
            async def forbidden(*args, **kwargs):
                raise AssertionError("成功事实恢复不能重放模型或事件")
            app.chat.client.stream = app.chat.client.complete = forbidden
            app.chat.set_event_sink(forbidden)
            restored = (await call(app, "chat.get", {"id": cid}))["result"]
            assert len([item for item in restored["messages"] if item["kind"] == kind]) == 1
            assert not any(item["kind"] == "model_partial" for item in restored["messages"])
            assert restored["stream"]["last_seq"] == last_seq
            assert restored["stream"]["state"] == ("completed" if finished else "interrupted")
            assert restored["workflow"] is None and restored["grant"] is None
        finally:
            await app.close()
    asyncio.run(run())


def test_compound_later_failed_prefix_keeps_only_unverified_tail(tmp_path):
    async def run():
        app = await setup(tmp_path)
        cid = (await create(app))["id"]
        rid = str(uuid4())
        await app.chat.repository.claim(cid, rid, "合成复合模型窗口")
        await app.chat.streams.start(cid, rid)
        await app.chat.streams.emit(cid, rid, "model_delta", {"text": "第一段已保存回答", "provisional": True})
        await app.chat.repository.append(cid, "assistant", "第一段已保存回答", "natural_answer", {
            "request_id": rid, "stream_prefix_chars": await app.chat.streams.prefix_size(cid, rid)})
        await app.chat.streams.emit(cid, rid, "model_delta", {"text": "第二段未完成", "provisional": True})
        await app.close()
        app = await setup(tmp_path)
        try:
            restored = (await call(app, "chat.get", {"id": cid}))["result"]
            records = [item for item in restored["messages"] if item["kind"] == "model_partial"]
            assert len(records) == 1 and records[0]["data"]["text"] == "第二段未完成"
            assert records[0]["data"]["state"] == "interrupted"
            assert restored["stream"]["state"] == "interrupted" and restored["grant"] is None
        finally:
            await app.close()
    asyncio.run(run())


def test_validated_prefix_counts_legal_nul_and_unicode_with_python_boundaries(tmp_path):
    async def run():
        app = await setup(tmp_path)
        cid = (await create(app))["id"]
        rid = str(uuid4())
        await app.chat.repository.claim(cid, rid, "合法JSON字符串边界")
        await app.chat.streams.start(cid, rid)
        prefix = "合法\0Unicode：折帆🚀已核验"
        await app.chat.streams.emit(cid, rid, "model_delta", {"text": prefix, "provisional": True})
        size = await app.chat.streams.prefix_size(cid, rid)
        assert size == len(prefix)
        await app.chat.repository.append(cid, "assistant", prefix, "natural_answer", {"request_id": rid, "stream_prefix_chars": size})
        await app.close()
        app = await setup(tmp_path)
        try:
            restored = (await call(app, "chat.get", {"id": cid}))["result"]
            assert not any(item["kind"] == "model_partial" for item in restored["messages"])
            assert next(item for item in restored["messages"] if item["kind"] == "natural_answer")["text"] == prefix
            assert restored["stream"]["state"] == "interrupted"
        finally:
            await app.close()
    asyncio.run(run())
