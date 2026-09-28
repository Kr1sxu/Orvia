"""凭据与模型适配目标测试：仅使用合成凭据和 HTTP MockTransport。"""

import asyncio
import json

import httpx
import pytest
from pydantic import ValidationError

from orvia_backend.configuration import Credentials, ModelRegistry
from orvia_backend.configuration.client import ModelClient, ModelUnavailable
from orvia_backend.domain import get_profiles

SYNTHETIC_KEY = "synthetic-only-secret-marker"


def test_registry_profiles_secrets_and_replacement():
    credentials = Credentials(main=SYNTHETIC_KEY)
    registry = ModelRegistry(credentials)
    before = registry.status()
    assert SYNTHETIC_KEY not in repr(credentials) + credentials.model_dump_json() + json.dumps(before)
    assert [profile["configured"] for profile in before["profiles"]] == [True, False, False]
    assert before["search_available"] is False
    snapshot = get_profiles()
    registry.replace_credentials(Credentials(main="synthetic-replacement"))
    assert get_profiles() == snapshot
    assert registry.status() == before
    assert registry.key_for(snapshot[0]) == "synthetic-replacement"
    with pytest.raises(ValueError, match="^MISSING_CREDENTIAL$"):
        registry.key_for(snapshot[1])


@pytest.mark.parametrize("key", ["", " ", "x\ny", "x\ry", "x" * 4097])
def test_credentials_reject_invalid_values_without_echo(key):
    with pytest.raises(ValidationError) as error:
        Credentials(main=key)
    assert "input_value" not in str(error.value)


@pytest.mark.parametrize("use_tools", [False, True])
def test_model_client_synthetic_completion(use_tools):
    calls = []
    tool_call = {"id": "synthetic-call", "type": "function", "function": {"name": "synthetic_probe", "arguments": "{}"}}
    def handler(request):
        calls.append(request)
        assert str(request.url) == "https://api.deepseek.com/chat/completions"
        assert request.headers["authorization"] == "Bearer " + SYNTHETIC_KEY
        payload = json.loads(request.content)
        assert payload["model"] == "deepseek-flash"
        assert payload["max_tokens"] == 32
        assert request.extensions["timeout"]["read"] == 20
        if use_tools:
            assert payload["tool_choice"] == "auto"
        message = {"content": None, "tool_calls": [tool_call]} if use_tools else {"content": "合成结果"}
        return httpx.Response(200, json={"choices": [{"message": message, "finish_reason": "tool_calls" if use_tools else "stop"}], "usage": {"total_tokens": 7, "unexpected": 99}})
    async def scenario():
        client = ModelClient(ModelRegistry(Credentials(main=SYNTHETIC_KEY)), httpx.MockTransport(handler))
        return await client.complete(get_profiles()[0], [{"role": "user", "content": "synthetic"}], max_tokens=32,
                                     tools=[{"type": "function", "function": {"name": "synthetic_probe", "parameters": {"type": "object"}}}] if use_tools else None)
    result = asyncio.run(scenario())
    assert len(calls) == 1
    assert result.tool_calls == ((tool_call,) if use_tools else ())
    assert result.text == (None if use_tools else "合成结果")
    assert result.usage == {"total_tokens": 7}


@pytest.mark.parametrize("failure,code", [(401, "HTTP_401"), (302, "HTTP_302"), ("timeout", "NETWORK_OR_TIMEOUT"), ("large", "RESPONSE_TOO_LARGE"), ("invalid", "INVALID_RESPONSE")])
def test_client_failure_sanitized_without_retry(failure, code):
    count = 0
    def handler(request):
        nonlocal count
        count += 1
        if failure == "timeout":
            raise httpx.ReadTimeout(SYNTHETIC_KEY, request=request)
        if failure == "large":
            return httpx.Response(200, content=(SYNTHETIC_KEY * 3000).encode())
        if failure == "invalid":
            return httpx.Response(200, content=SYNTHETIC_KEY.encode())
        return httpx.Response(failure, headers={"Location": "https://example.invalid"}, text=SYNTHETIC_KEY)
    async def scenario():
        client = ModelClient(ModelRegistry(Credentials(main=SYNTHETIC_KEY)), httpx.MockTransport(handler))
        with pytest.raises(ModelUnavailable) as error:
            await client.complete(get_profiles()[0], [{"role": "user", "content": "synthetic"}])
        assert str(error.value) == code
        assert SYNTHETIC_KEY not in repr(error.value)
    asyncio.run(scenario())
    assert count == 1


def test_missing_credential_does_not_make_request():
    def handler(request):
        pytest.fail("missing credentials must not reach transport")
    async def scenario():
        client = ModelClient(ModelRegistry(), httpx.MockTransport(handler))
        with pytest.raises(ModelUnavailable, match="^MISSING_CREDENTIAL$"):
            await client.complete(get_profiles()[0], [])
    asyncio.run(scenario())


@pytest.mark.parametrize("tool_call", [
    None,
    {},
    {"id": "", "type": "function", "function": {"name": "probe", "arguments": "{}"}},
    {"id": " ", "type": "function", "function": {"name": "probe", "arguments": "{}"}},
    {"id": 1, "type": "function", "function": {"name": "probe", "arguments": "{}"}},
    {"id": "call", "type": "unknown", "function": {"name": "probe", "arguments": "{}"}},
    {"id": "call", "type": "function", "function": None},
    {"id": "call", "type": "function", "function": {"name": "", "arguments": "{}"}},
    {"id": "call", "type": "function", "function": {"name": "probe", "arguments": {}}},
    {"id": "call", "type": "function", "function": {"name": "probe", "arguments": "[]"}},
    {"id": "call", "type": "function", "function": {"name": "probe", "arguments": "not-json"}},
])
def test_malformed_tool_call_is_rejected(tool_call):
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": None, "tool_calls": [tool_call]}, "finish_reason": "tool_calls"}]})
    async def scenario():
        client = ModelClient(ModelRegistry(Credentials(main=SYNTHETIC_KEY)), httpx.MockTransport(handler))
        with pytest.raises(ModelUnavailable, match="^INVALID_RESPONSE$"):
            await client.complete(get_profiles()[0], [])
    asyncio.run(scenario())


@pytest.mark.parametrize("nested_arguments", [False, True])
def test_deep_json_is_sanitized(nested_arguments):
    # 在响应字节上构造嵌套，避免测试自身的 JSON 编码器先触发递归限制。
    deep = "[" * 2000 + "0" + "]" * 2000
    if nested_arguments:
        payload = json.dumps({"choices": [{"message": {"content": None, "tool_calls": [
            {"id": "call", "type": "function", "function": {"name": "probe", "arguments": deep}}
        ]}}]}).encode()
    else:
        payload = deep.encode()
    def handler(request):
        return httpx.Response(200, content=payload)
    async def scenario():
        client = ModelClient(ModelRegistry(Credentials(main=SYNTHETIC_KEY)), httpx.MockTransport(handler))
        with pytest.raises(ModelUnavailable, match="^INVALID_RESPONSE$"):
            await client.complete(get_profiles()[0], [])
    asyncio.run(scenario())
