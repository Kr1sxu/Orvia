"""固定地址的兼容 Chat Completions 适配器，M02 仅做显式合成能力测试。"""

import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import httpx

from orvia_backend.domain import ModelProfile
from . import ModelRegistry


class ModelUnavailable(RuntimeError):
    """只携带固定错误码，不带请求、凭据或供应商响应正文。"""


@dataclass(frozen=True)
class Completion:
    text: str | None
    tool_calls: tuple[dict[str, Any], ...]
    finish_reason: str
    usage: dict[str, int]


class ModelClient:
    """无重试、无重定向、固定超时，供应商/模型/URL 来自不可变配置快照。"""

    def __init__(self, registry: ModelRegistry, transport: httpx.AsyncBaseTransport | None = None):
        self.registry = registry
        self.transport = transport

    async def stream(self, profile: ModelProfile, messages: list[dict], *, max_tokens: int = 256,
                     tools: list[dict] | None = None, response_format: dict | None = None,
                     on_delta: Callable[[str], Awaitable[None]] | None = None) -> Completion:
        """固定供应商真实 SSE；回调等待形成背压，结束帧与完成原因缺一均拒绝成功。

        增量仅来自 content；工具参数先有界拼接再校验，绝不会在这里执行。
        回调中的文字尚不是最终业务结果，调用方须完成结构、引用和持久化核验。
        """
        if not 1 <= max_tokens <= 4096:
            raise ValueError("输出预算必须介于 1 和 4096 token")
        if response_format is not None and response_format != {"type": "json_object"}:
            raise ValueError("仅允许固定 JSON Object 输出格式")
        try:
            key = self.registry.key_for(profile)
        except ValueError:
            raise ModelUnavailable("MISSING_CREDENTIAL") from None
        payload: dict[str, Any] = {"model": profile.model, "messages": messages, "max_tokens": max_tokens,
                                   "stream": True, "stream_options": {"include_usage": True}}
        if tools:
            payload.update(tools=tools, tool_choice="auto")
        if response_format is not None:
            payload["response_format"] = response_format
        text_parts, calls, usage = [], {}, {}
        content_size = tool_size = 0
        finish_reason = None
        done = False
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=False, trust_env=False,
                                         transport=self.transport or httpx.AsyncHTTPTransport(retries=0)) as client:
                async with client.stream("POST", profile.base_url + "/chat/completions", json=payload,
                                         headers={"Authorization": "Bearer " + key}) as response:
                    if response.status_code != 200:
                        raise ModelUnavailable(f"HTTP_{response.status_code}")
                    if response.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "text/event-stream":
                        raise ModelUnavailable("STREAM_UNSUPPORTED")
                    async for event in _sse_events(response):
                        if done:
                            raise ModelUnavailable("INVALID_STREAM")
                        if event == "[DONE]":
                            if finish_reason is None:
                                raise ModelUnavailable("STREAM_INCOMPLETE")
                            done = True
                            continue
                        data = _stream_json(event)
                        if (not isinstance(data, dict) or data.get("model", profile.model) != profile.model
                                or not isinstance(data.get("choices"), list)):
                            raise ModelUnavailable("INVALID_STREAM")
                        if "usage" in data and data["usage"] is not None:
                            if not isinstance(data["usage"], dict):
                                raise ModelUnavailable("INVALID_STREAM")
                            for name, value in data["usage"].items():
                                if name in {"prompt_tokens", "completion_tokens", "total_tokens"}:
                                    if type(value) is not int or not 0 <= value <= 2**53 - 1:
                                        raise ModelUnavailable("INVALID_STREAM")
                                    usage[name] = value
                        choices = data["choices"]
                        if not choices:
                            if finish_reason is None or not isinstance(data.get("usage"), dict):
                                raise ModelUnavailable("INVALID_STREAM")
                            continue
                        if len(choices) != 1 or finish_reason is not None:
                            raise ModelUnavailable("INVALID_STREAM")
                        choice = choices[0]
                        if (not isinstance(choice, dict) or type(choice.get("index")) is not int or choice["index"] != 0
                                or not isinstance(choice.get("delta"), dict)):
                            raise ModelUnavailable("INVALID_STREAM")
                        delta = choice["delta"]
                        if set(delta) - {"role", "content", "tool_calls", "reasoning_content", "refusal"}:
                            raise ModelUnavailable("INVALID_STREAM")
                        if "role" in delta and delta["role"] is not None and delta["role"] != "assistant":
                            raise ModelUnavailable("INVALID_STREAM")
                        for name in ("content", "reasoning_content", "refusal"):
                            if delta.get(name) is not None and not isinstance(delta[name], str):
                                raise ModelUnavailable("INVALID_STREAM")
                        if delta.get("refusal"):
                            raise ModelUnavailable("MODEL_REFUSAL")
                        piece = delta.get("content") or ""
                        content_size += len(piece.encode("utf-8"))
                        if content_size > 65536:
                            raise ModelUnavailable("RESPONSE_TOO_LARGE")
                        if piece:
                            text_parts.append(piece)
                            if on_delta is not None:
                                # 不创建脱离生命周期的回调任务：UI/stdio 慢时暂停继续消费供应商流。
                                await on_delta(piece)
                        tool_deltas = delta.get("tool_calls") or []
                        if "tool_calls" in delta and delta["tool_calls"] is not None and not isinstance(delta["tool_calls"], list):
                            raise ModelUnavailable("INVALID_STREAM")
                        if not isinstance(tool_deltas, list) or tool_deltas and not tools:
                            raise ModelUnavailable("INVALID_STREAM")
                        for fragment in tool_deltas:
                            tool_size += _collect_tool_delta(calls, fragment)
                            if tool_size > 65536:
                                raise ModelUnavailable("RESPONSE_TOO_LARGE")
                        reason = choice.get("finish_reason")
                        if reason is not None:
                            if not isinstance(reason, str):
                                raise ModelUnavailable("INVALID_STREAM")
                            if reason in {"aborted", "insufficient_system_resource"}:
                                raise ModelUnavailable("MODEL_STREAM_ABORTED")
                            if reason not in {"stop", "length", "tool_calls", "content_filter"}:
                                raise ModelUnavailable("INVALID_STREAM")
                            finish_reason = reason
                    if not done or finish_reason is None:
                        raise ModelUnavailable("STREAM_INCOMPLETE")
            assembled = _finish_tool_calls(calls)
            if not text_parts and not assembled:
                raise ModelUnavailable("EMPTY_COMPLETION")
            if bool(assembled) != (finish_reason == "tool_calls") and finish_reason not in {"length", "content_filter"}:
                raise ModelUnavailable("INVALID_STREAM")
            return Completion("".join(text_parts) or None, assembled, finish_reason, usage)
        except httpx.HTTPError:
            raise ModelUnavailable("NETWORK_OR_TIMEOUT") from None
        except UnicodeError:
            raise ModelUnavailable("INVALID_STREAM") from None

    async def complete(self, profile: ModelProfile, messages: list[dict], *, max_tokens: int = 256,
                       tools: list[dict] | None = None) -> Completion:
        if not 1 <= max_tokens <= 4096:
            raise ValueError("输出预算必须介于 1 和 4096 token")
        try:
            key = self.registry.key_for(profile)
        except ValueError:
            raise ModelUnavailable("MISSING_CREDENTIAL") from None
        payload: dict[str, Any] = {"model": profile.model, "messages": messages, "max_tokens": max_tokens, "stream": False}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        try:
            # 不把环境代理或追踪配置隐式带进模型客户端，凭据只在本次请求头中存在。
            async with httpx.AsyncClient(timeout=20, follow_redirects=False, trust_env=False,
                                         transport=self.transport or httpx.AsyncHTTPTransport(retries=0)) as client:
                async with client.stream("POST", profile.base_url + "/chat/completions", json=payload,
                                         headers={"Authorization": "Bearer " + key}) as response:
                    if response.status_code != 200:
                        raise ModelUnavailable(f"HTTP_{response.status_code}")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > 65536:
                            raise ModelUnavailable("RESPONSE_TOO_LARGE")
            data = json.loads(body)
            choice = data["choices"][0]
            message = choice["message"]
            text = message.get("content")
            calls = message.get("tool_calls", [])
            if text is not None and not isinstance(text, str) or not isinstance(calls, list):
                raise ModelUnavailable("INVALID_RESPONSE")
            for call in calls:
                # 这里只验证工具调用信封，不执行工具；参数业务权限由调用方另行判断。
                if (not isinstance(call, dict) or not isinstance(call.get("id"), str)
                        or not call["id"].strip() or call.get("type") != "function"):
                    raise ModelUnavailable("INVALID_RESPONSE")
                function = call.get("function")
                if (not isinstance(function, dict) or not isinstance(function.get("name"), str)
                        or not function["name"].strip() or not isinstance(function.get("arguments"), str)):
                    raise ModelUnavailable("INVALID_RESPONSE")
                if not isinstance(json.loads(function["arguments"]), dict):
                    raise ModelUnavailable("INVALID_RESPONSE")
            if not text and not calls:
                raise ModelUnavailable("EMPTY_COMPLETION")
            usage = {key: value for key, value in data.get("usage", {}).items()
                     if key in ("prompt_tokens", "completion_tokens", "total_tokens") and type(value) is int}
            return Completion(text, tuple(calls), choice.get("finish_reason", "unknown"), usage)
        except httpx.HTTPError:
            raise ModelUnavailable("NETWORK_OR_TIMEOUT") from None
        except (ValueError, KeyError, TypeError, IndexError, AttributeError, RecursionError):
            raise ModelUnavailable("INVALID_RESPONSE") from None


def _stream_json(value: str) -> Any:
    """SSE JSON 错误只给固定码，禁止携带供应商正文或原始异常。"""
    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError("duplicate")
            result[key] = item
        return result
    try:
        return json.loads(value, object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("constant")))
    except (ValueError, TypeError, RecursionError):
        raise ModelUnavailable("INVALID_STREAM") from None


async def _sse_events(response: httpx.Response):
    """按真实字节组装事件；注释/心跳也消耗总预算，CR/LF 和 UTF-8 均可跨块。

    接受 SSE data 与注释，以及有限 event/id/retry 元字段；不会用半个事件或 EOF
    猜测完成。512 KiB 是整次流预算，单事件（含心跳）16 KiB。
    """
    pending = bytearray()
    fields = []
    total = event_size = 0
    previous_cr = False
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        if total > 512 * 1024:
            raise ModelUnavailable("STREAM_TOO_LARGE")
        for byte in chunk:
            if previous_cr:
                previous_cr = False
                if byte == 10:
                    continue
            if byte not in {10, 13}:
                pending.append(byte)
                if len(pending) + event_size > 16 * 1024:
                    raise ModelUnavailable("STREAM_EVENT_TOO_LARGE")
                continue
            previous_cr = byte == 13
            line = bytes(pending)
            pending.clear()
            event_size += len(line) + 1
            if event_size > 16 * 1024:
                raise ModelUnavailable("STREAM_EVENT_TOO_LARGE")
            decoded = line.decode("utf-8", errors="strict")
            if not decoded:
                if fields:
                    yield "\n".join(fields)
                fields = []
                event_size = 0
            elif decoded.startswith(":"):
                continue
            else:
                name, _, value = decoded.partition(":")
                if name not in {"data", "event", "id", "retry"}:
                    raise ModelUnavailable("INVALID_STREAM")
                if value.startswith(" "):
                    value = value[1:]
                if name == "data":
                    fields.append(value)
    if pending or fields or event_size:
        raise ModelUnavailable("STREAM_INCOMPLETE")


def _collect_tool_delta(calls: dict, fragment: Any) -> int:
    if (not isinstance(fragment, dict) or set(fragment) - {"index", "id", "type", "function"}
            or type(fragment.get("index")) is not int or not 0 <= fragment["index"] < 16):
        raise ModelUnavailable("INVALID_STREAM")
    index = fragment["index"]
    call = calls.setdefault(index, {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
    if fragment.get("type", "function") != "function":
        raise ModelUnavailable("INVALID_STREAM")
    function = fragment.get("function", {})
    if not isinstance(function, dict) or set(function) - {"name", "arguments"}:
        raise ModelUnavailable("INVALID_STREAM")
    size = 0
    for target, name, limit in ((call, "id", 256), (call["function"], "name", 128),
                                 (call["function"], "arguments", 65536)):
        source = fragment if name == "id" else function
        if name in source:
            value = source[name]
            if not isinstance(value, str):
                raise ModelUnavailable("INVALID_STREAM")
            target[name] += value
            size += len(value.encode("utf-8"))
            if len(target[name].encode("utf-8")) > limit:
                raise ModelUnavailable("RESPONSE_TOO_LARGE")
    return size


def _finish_tool_calls(calls: dict) -> tuple[dict, ...]:
    if calls and set(calls) != set(range(len(calls))):
        raise ModelUnavailable("INVALID_STREAM")
    result = []
    for index in sorted(calls):
        call = calls[index]
        if not call["id"].strip() or not call["function"]["name"].strip():
            raise ModelUnavailable("INVALID_STREAM")
        if not isinstance(_stream_json(call["function"]["arguments"]), dict):
            raise ModelUnavailable("INVALID_STREAM")
        result.append(call)
    if len({call["id"] for call in result}) != len(result):
        raise ModelUnavailable("INVALID_STREAM")
    return tuple(result)
