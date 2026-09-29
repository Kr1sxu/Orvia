"""固定地址的兼容 Chat Completions 适配器，M02 仅做显式合成能力测试。"""

import json
from dataclasses import dataclass
from typing import Any

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
