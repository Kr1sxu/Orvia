"""合法异步SSE终态与JSON完成校验分开；模型输出仅合成字节。"""

import asyncio
import json
from uuid import uuid4

import pytest

from test_chat import call, create, setup
from test_m20_model_stream import client_for, event, DONE
from test_m20_natural import material, send


@pytest.mark.parametrize("finish,code,notice", [("length", "GENERATION_TRUNCATED", "输出token预算"),
                                               ("stop", "INVALID_GENERATION", "JSON不完整或结构非法")])
def test_sse_length_and_unclosed_json_keep_prefix_without_success_or_fallback(tmp_path, finish, code, notice):
    async def run():
        app = await setup(tmp_path)
        try:
            cid = (await create(app))["id"]
            await material(app, cid)
            waiting = (await call(app, "chat.natural", send(cid, "总结这份附件")))["result"]["workflow"]
            preview = (await call(app, "chat.synthesis.preview", {"id": cid, **waiting["input"]}))["result"]
            client, stream, requests = client_for([event({"content": '{"answer":"实际合成部分正文'}),
                                                    event(reason=finish), DONE])
            app.chat.client = client
            rid = str(uuid4())
            request = {"id": cid, "request_id": rid, **waiting["input"], "revision": preview["revision"], "stream_mode": "stream"}
            generated = (await call(app, "chat.synthesis.generate", request))["result"]
            error = next(item for item in reversed(generated["messages"]) if item["kind"] == "error")
            assert error["data"]["code"] == code and notice in error["text"]
            assert "超时或不可用" not in error["text"]
            partial = [item for item in generated["messages"] if item["kind"] == "model_partial"]
            assert len(partial) == 1 and partial[0]["data"]["text"] == "实际合成部分正文"
            assert partial[0]["data"]["request_id"] == rid and partial[0]["data"]["provisional"] is True
            assert partial[0]["data"]["state"] == "failed"
            assert not any(item["kind"] in {"synthesis", "natural_answer", "publication"} for item in generated["messages"])
            assert generated["workflow"]["action"] == "synthesis" and generated["stream"]["state"] == "failed"
            assert len(requests) == 1 and json.loads(requests[0].content)["max_tokens"] == 4096 and stream.closed
            if finish == "length":
                assert "4096" in error["text"] and "1024" not in error["text"]
            await call(app, "chat.synthesis.generate", request)
            assert len(requests) == 1
        finally:
            await app.close()
    asyncio.run(run())
