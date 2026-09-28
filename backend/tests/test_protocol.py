"""协议与会话状态的目标测试；不使用模型或真实用户文件。"""

import json

import pytest

from orvia_backend.protocol import Session


def request(method: str, **overrides: object) -> bytes:
    payload = {"v": 1, "id": "测试-1", "method": method, "params": {}}
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def test_handshake_and_health() -> None:
    session = Session()
    assert session.handle(request("health"))["error"]["code"] == "NOT_READY"
    hello = session.handle(request("hello"))
    assert hello["ok"] is True
    assert hello["id"] == "测试-1"
    assert hello["result"]["protocol"] == 1
    assert hello["result"]["service"] == "orvia-backend"
    assert hello["result"]["python"].startswith("3.12.")
    assert session.handle(request("hello"))["ok"] is True
    assert session.handle(request("health"))["result"] == {"status": "ok", "service": "orvia-backend"}
    assert Session().handle(request("health"))["error"]["code"] == "NOT_READY"


@pytest.mark.parametrize("line,code", [
    (b"{", "INVALID_REQUEST"),
    (b"\xff", "INVALID_REQUEST"),
    (b"[]", "INVALID_REQUEST"),
    (b'{"value":' + b"9" * 5000 + b"}", "INVALID_REQUEST"),
    (request("hello", id=""), "INVALID_REQUEST"),
    (request("hello", id=1), "INVALID_REQUEST"),
    (request("hello", params=[]), "INVALID_REQUEST"),
    (request("hello", params={"extra": 1}), "INVALID_REQUEST"),
    (request("hello", v=2), "UNSUPPORTED_VERSION"),
    (request("hello", v=True), "UNSUPPORTED_VERSION"),
    (request("unknown"), "METHOD_NOT_FOUND"),
])
def test_invalid_request_does_not_unlock_session(line: bytes, code: str) -> None:
    session = Session()
    result = session.handle(line)
    assert result["ok"] is False
    assert result["error"]["code"] == code
    assert session.ready is False
