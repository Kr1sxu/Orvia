"""M20 真异步 SSE 字节替身；全为合成资料，不读取 Key 或访问外网。"""

import asyncio
import json

import httpx
import pytest

from orvia_backend.chat.json_stream import AnswerJSONStream, JSONStreamError
from orvia_backend.configuration import Credentials, ModelRegistry
from orvia_backend.configuration.client import ModelClient, ModelUnavailable
from orvia_backend.domain import get_profiles


def event(delta=None, reason=None, *, usage=None, model="deepseek-flash"):
    value = {"model": model, "choices": [{"index": 0, "delta": delta or {}, "finish_reason": reason}]}
    if usage is not None:
        value["usage"] = usage
    return ("data: " + json.dumps(value, ensure_ascii=False) + "\r\n\r\n").encode()


DONE = b"data: [DONE]\n\n"


class AsyncChunks(httpx.AsyncByteStream):
    """真正分次异步提供字节并记已消费位置，验证回调前后与取消关闭。"""
    def __init__(self, chunks):
        self.chunks, self.read, self.closed = chunks, [], False

    async def __aiter__(self):
        for index, chunk in enumerate(self.chunks):
            await asyncio.sleep(0)
            self.read.append(index)
            yield chunk

    async def aclose(self):
        self.closed = True


def client_for(chunks, *, status=200, headers=None, registry=None):
    stream, requests = AsyncChunks(chunks), []
    def handler(request):
        requests.append(request)
        return httpx.Response(status, headers=headers or {"content-type": "text/event-stream"}, stream=stream)
    registry = registry or ModelRegistry(Credentials(main="m20-synthetic-credential"))
    return ModelClient(registry, httpx.MockTransport(handler)), stream, requests


def test_real_incremental_content_fixed_config_usage_and_backpressure():
    async def run():
        chunks = [event({"role": "assistant", "content": "甲"}), event({"content": "乙"}), event(reason="stop"),
                  b'data: {"choices":[],"usage":{"prompt_tokens":4,"completion_tokens":2,"total_tokens":6}}\n\n', DONE]
        client, stream, requests = client_for(chunks)
        entered, release = asyncio.Event(), asyncio.Event()
        received = []
        async def on_delta(value):
            received.append(value)
            if value == "甲":
                entered.set()
                await release.wait()
        task = asyncio.create_task(client.stream(get_profiles()[0], [{"role": "user", "content": "合成问题"}],
                                                max_tokens=32, response_format={"type": "json_object"}, on_delta=on_delta))
        await asyncio.wait_for(entered.wait(), 2)
        assert not task.done() and stream.read == [0] and received == ["甲"]
        release.set()
        result = await asyncio.wait_for(task, 2)
        assert result.text == "甲乙" and result.tool_calls == () and result.finish_reason == "stop"
        assert result.usage == {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6}
        assert received == ["甲", "乙"] and stream.closed and len(requests) == 1
        request = requests[0]
        payload = json.loads(request.content)
        assert str(request.url) == "https://api.deepseek.com/chat/completions"
        assert payload["model"] == "deepseek-flash" and payload["stream"] is True
        assert payload["max_tokens"] == 32 and payload["response_format"] == {"type": "json_object"}
        assert request.extensions["timeout"]["read"] == 20
    asyncio.run(run())


def test_utf8_crlf_sse_fields_and_json_multiline_cross_every_byte():
    async def run():
        first = b': heartbeat\r\nevent: message\r\nid: synthetic\r\nretry: 1000\r\n'
        first += 'data: {"choices": [{"index": 0,\r\ndata: "delta": {"content": "中🙂"}, "finish_reason": null}]}\r\n\r\n'.encode()
        body = first + event(reason="stop") + DONE
        client, _, _ = client_for([bytes([byte]) for byte in body])
        received = []
        async def append(value):
            received.append(value)
        result = await client.stream(get_profiles()[0], [], on_delta=append)
        assert received == ["中🙂"] and result.text == "中🙂"
    asyncio.run(run())


def test_compatible_null_role_and_tools_do_not_hide_real_content():
    async def run():
        client, _, _ = client_for([event({"role": None, "tool_calls": None, "content": "合成"}), event(reason="stop"), DONE])
        result = await client.stream(get_profiles()[0], [])
        assert result.text == "合成" and result.tool_calls == ()
    asyncio.run(run())


@pytest.mark.parametrize("reason", ["aborted", "insufficient_system_resource"])
def test_supplier_explicit_abort_is_failure(reason):
    async def run():
        client, _, _ = client_for([event({"content": "部分"}), event(reason=reason), DONE])
        with pytest.raises(ModelUnavailable, match="^MODEL_STREAM_ABORTED$"):
            await client.stream(get_profiles()[0], [])
    asyncio.run(run())


def test_tool_fragments_only_aggregate_after_real_finish():
    async def run():
        fragments = [
            {"tool_calls": [{"index": 0, "id": "synthetic-", "type": "function", "function": {"name": "pro", "arguments": '{"kind":'}}]},
            {"tool_calls": [{"index": 0, "id": "call", "function": {"name": "pose", "arguments": '"answer",'}}]},
            {"tool_calls": [{"index": 0, "function": {"arguments": '"text":"合成"}'}}]},
        ]
        client, _, requests = client_for([*(event(fragment) for fragment in fragments), event(reason="tool_calls"), DONE])
        received = []
        async def append(value):
            received.append(value)
        tools = [{"type": "function", "function": {"name": "propose", "parameters": {"type": "object"}}}]
        result = await client.stream(get_profiles()[0], [], tools=tools, on_delta=append)
        assert received == [] and result.text is None
        assert result.tool_calls == ({"id": "synthetic-call", "type": "function", "function": {
            "name": "propose", "arguments": '{"kind":"answer","text":"合成"}'}},)
        assert json.loads(requests[0].content)["tool_choice"] == "auto"
    asyncio.run(run())


@pytest.mark.parametrize("fragment", [
    {"index": True}, {"index": 16}, {"index": 0, "type": "invalid"},
    {"index": 0, "function": "not-object"}, {"index": 0, "id": 1},
    {"index": 0, "function": {"name": 1}}, {"index": 0, "function": {"arguments": {}}},
    {"index": 0, "function": {"unexpected": "x"}},
])
def test_bad_tool_fragment_rejected_without_data_leak(fragment):
    async def run():
        client, stream, requests = client_for([event({"tool_calls": [fragment]}), event(reason="tool_calls"), DONE])
        with pytest.raises(ModelUnavailable, match="^INVALID_STREAM$"):
            await client.stream(get_profiles()[0], [], tools=[{"synthetic": True}])
        assert len(requests) == 1 and stream.closed
    asyncio.run(run())


@pytest.mark.parametrize("arguments", ["[]", "not-json", '{"x":1,"x":2}', "[" * 2000 + "0" + "]" * 2000])
def test_tool_arguments_are_final_strict_json_object(arguments):
    async def run():
        tool = {"index": 0, "id": "call", "function": {"name": "propose", "arguments": arguments}}
        client, _, _ = client_for([event({"tool_calls": [tool]}), event(reason="tool_calls"), DONE])
        with pytest.raises(ModelUnavailable, match="^INVALID_STREAM$"):
            await client.stream(get_profiles()[0], [], tools=[{"synthetic": True}])
    asyncio.run(run())


@pytest.mark.parametrize("chunks,code", [
    ([event({"content": "暂态"})], "STREAM_INCOMPLETE"),
    ([event({"content": "暂态"}), event(reason="stop")], "STREAM_INCOMPLETE"),
    ([event({"content": "暂态"}), DONE], "STREAM_INCOMPLETE"),
    ([event({"content": "暂态"}), event(reason="stop"), DONE, event({"content": "晚到"})], "INVALID_STREAM"),
    ([b'data: {"choices":[]}\n\n'], "INVALID_STREAM"),
    ([b'data: {"choices":[],"usage":{"total_tokens":3}}\n\n'], "INVALID_STREAM"),
    ([event({"content": "暂态"}, model="other-model")], "INVALID_STREAM"),
    ([b'data: {"choices":[{"index":0,"delta":{"content":"\xff"}}]}\n\n'], "INVALID_STREAM"),
    ([b'data: {"choices":[],"choices":[]}\n\n'], "INVALID_STREAM"),
    ([b": " + b"x" * 17000 + b"\n\n"], "STREAM_EVENT_TOO_LARGE"),
    ([b": " + b"x" * 1000 + b"\n\n"] * 530, "STREAM_TOO_LARGE"),
    ([event({"content": "暂态"}), b'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"usage":{"total_tokens":true}}\n\n'], "INVALID_STREAM"),
    ([event({"tool_calls": [{"index": 0}]})], "INVALID_STREAM"),
])
def test_incomplete_corrupt_oversized_streams_do_not_return_success(chunks, code):
    async def run():
        client, stream, requests = client_for(chunks)
        with pytest.raises(ModelUnavailable) as error:
            await client.stream(get_profiles()[0], [])
        assert str(error.value) == code and "暂态" not in str(error.value)
        assert stream.closed and len(requests) == 1
    asyncio.run(run())


def test_output_limit_and_length_finish_remain_explicit():
    async def run():
        chunks = [event({"content": "x" * 4000})] * 17 + [event(reason="stop"), DONE]
        client, _, _ = client_for(chunks)
        with pytest.raises(ModelUnavailable, match="^RESPONSE_TOO_LARGE$"):
            await client.stream(get_profiles()[0], [])
        client, _, _ = client_for([event({"content": "部分"}), event(reason="length"), DONE])
        result = await client.stream(get_profiles()[0], [])
        assert result.text == "部分" and result.finish_reason == "length"
    asyncio.run(run())


def test_cancellation_closes_stream_and_never_consumes_second_delta():
    async def run():
        client, stream, requests = client_for([event({"content": "部分"}), event({"content": "继续"}), event(reason="stop"), DONE])
        entered = asyncio.Event()
        async def held(value):
            entered.set()
            await asyncio.Event().wait()
        task = asyncio.create_task(client.stream(get_profiles()[0], [], on_delta=held))
        await asyncio.wait_for(entered.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert stream.closed and stream.read == [0] and len(requests) == 1
    asyncio.run(run())


@pytest.mark.parametrize("failure,code", [(401, "HTTP_401"), (302, "HTTP_302"), ("content-type", "STREAM_UNSUPPORTED"), ("timeout", "NETWORK_OR_TIMEOUT")])
def test_failure_does_not_retry_or_follow_redirect(failure, code):
    async def run():
        calls = []
        def handler(request):
            calls.append(request)
            if failure == "timeout":
                raise httpx.ReadTimeout("synthetic-sensitive-error", request=request)
            if failure == "content-type":
                return httpx.Response(200, content=b"synthetic-sensitive-error")
            return httpx.Response(failure, headers={"Location": "https://example.invalid"}, content=b"synthetic-sensitive-error")
        client = ModelClient(ModelRegistry(Credentials(main="synthetic-only")), httpx.MockTransport(handler))
        with pytest.raises(ModelUnavailable) as error:
            await client.stream(get_profiles()[0], [])
        assert str(error.value) == code and "synthetic-sensitive-error" not in str(error.value)
        assert len(calls) == 1
    asyncio.run(run())


def test_missing_key_or_invalid_output_settings_never_reaches_transport():
    async def run():
        def handler(request):
            pytest.fail("no network allowed")
        client = ModelClient(ModelRegistry(), httpx.MockTransport(handler))
        with pytest.raises(ModelUnavailable, match="^MISSING_CREDENTIAL$"):
            await client.stream(get_profiles()[0], [])
        with pytest.raises(ValueError):
            await client.stream(get_profiles()[0], [], max_tokens=4097)
        with pytest.raises(ValueError):
            await client.stream(get_profiles()[0], [], response_format={"type": "arbitrary"})
    asyncio.run(run())


def test_json_answer_unicode_escaped_key_and_claims_never_emit():
    text = '{"claims":[{"text":"不要显示","kind":"unknown","citations":[]}],"answ\\u0065r":"中文\\n\\\"引号\\\"\\\\路径\\uD83D\\uDE42"}'
    expected = '中文\n"引号"\\路径🙂'
    for size in (1, 2, 3, 7, len(text)):
        parser = AnswerJSONStream()
        increments = [parser.feed(text[index:index + size]) for index in range(0, len(text), size)]
        assert "".join(increments) == expected and parser.answer == expected
        assert parser.finish()["answer"] == expected and parser.raw == text
        assert "不要显示" not in "".join(increments)


@pytest.mark.parametrize("text", [
    '{"answer":"a","answer":"b"}', '{"answer":"a","claims":[{"x":1,"x":2}]}',
    '{"answer":"a",}', '{"answer":"a"} trailing', '{"answer":[]}',
    '{"claims":[],"nested":{"answer":"a"}}', '{"answer":"a","claims":NaN}',
    '{"answer":"\\uD800"}', '{"answer":"\\uDC00"}', '{"answer":"\\uD800x"}',
    '{"answer":"\\uD800\\u0061"}', '{"answer":"\\uZZZZ"}', '{"answer":"\\q"}',
    '{"answer":"literal\nnewline"}', '{"answer":"unclosed', '[]',
])
def test_bad_or_incomplete_json_never_finalizes(text):
    parser = AnswerJSONStream()
    with pytest.raises(JSONStreamError, match="^INVALID_JSON_STREAM$"):
        for char in text:
            parser.feed(char)
        parser.finish()


def test_json_answer_limits_are_checked_before_success():
    parser = AnswerJSONStream(max_answer_chars=3)
    assert parser.feed('{"answer":"甲乙') == "甲乙"
    with pytest.raises(JSONStreamError):
        parser.feed('丙丁"}')
    with pytest.raises(JSONStreamError):
        parser.finish()
    parser = AnswerJSONStream(max_bytes=10)
    with pytest.raises(JSONStreamError):
        parser.feed('{"answer":"x"}')
