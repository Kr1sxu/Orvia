"""M07 合成数据测试；DNS/HTTP 均为 mock，不访问互联网或模型。"""
import asyncio
import json
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from orvia_backend.browser.network import BrowserError, SafeHTTP, validate_url
from orvia_backend.browser.service import BrowserService, MAX_BODY
from orvia_backend.application import Application


class Body(httpx.AsyncByteStream):
    def __init__(self, content):
        self.content = content.encode() if isinstance(content, str) else content

    async def __aiter__(self):
        for start in range(0, len(self.content), 4096):
            yield self.content[start:start + 4096]


def response(content="synthetic", status=200, **headers):
    return httpx.Response(status, headers={"content-type": "text/plain", **headers}, stream=Body(content))


async def dns(host, port):
    return ["93.184.216.34"]


def service(handler, key=None, resolver=dns):
    return BrowserService(key, network=SafeHTTP(transport=httpx.MockTransport(handler), resolver=resolver))


@pytest.mark.parametrize("url", ["file:///C:/secret", "http://localhost/", "http://127.0.0.1/", "http://169.254.169.254/", "http://10.0.0.1/", "http://[::1]/", "http://[::ffff:127.0.0.1]/", "https://user:pass@example.com/", "https://example.com:444/", "https://example.com/#x", "https://example.com\\@evil.com", "https://example.com/\n"])
def test_url_rejects_before_network(url):
    with pytest.raises(BrowserError):
        validate_url(url)


def test_dns_pinning_headers_cookie_and_no_secondary_resolution():
    calls = []
    def handler(request):
        calls.append(request)
        assert request.url.host == "93.184.216.34"
        assert request.headers["host"] == "example.com"
        assert request.extensions["sni_hostname"] == "example.com"
        assert "cookie" not in request.headers and "authorization" not in request.headers
        if len(calls) == 1:
            return response(status=302, location="/next", **{"set-cookie": "synthetic=must-not-reuse"})
        return response("合成公开正文")
    result = asyncio.run(service(handler).read("https://example.com/"))
    assert result["content"] == "合成公开正文"
    assert result["source_url"] == "https://example.com/next"
    assert result["accessed_at"] and result["error"] is None
    assert len(calls) == 2


@pytest.mark.parametrize("addresses", [["127.0.0.1"], ["93.184.216.34", "10.0.0.1"], ["224.0.0.1"], []])
def test_dns_private_or_mixed_blocked(addresses):
    async def resolver(host, port):
        return addresses
    result = asyncio.run(service(lambda r: pytest.fail("network must not run"), resolver=resolver).read("https://example.com/"))
    assert result["error"]["code"] == "ADDRESS_BLOCKED"


@pytest.mark.parametrize("target", ["http://127.0.0.1/", "https://other.example/", "file:///test"])
def test_redirect_cannot_escape_scope(target):
    calls = []
    def handler(request):
        calls.append(request)
        return response(status=302, location=target)
    result = asyncio.run(service(handler).read("https://example.com/"))
    assert result["error"] and len(calls) == 1


@pytest.mark.parametrize("kind,code", [("large", "RESPONSE_TOO_LARGE"), ("binary", "RESOURCE_BLOCKED"), ("gzip", "ENCODING_BLOCKED"), ("loop", "REDIRECT_LIMIT"), ("attachment", "RESOURCE_BLOCKED"), ("timeout", "READ_FAILED"), ("403", "HTTP_FAILED")])
def test_http_errors_are_bounded_and_sanitized(kind, code):
    def handler(request):
        if kind == "large": return response(b"x" * (MAX_BODY + 1))
        if kind == "binary": return response(**{"content-type": "application/pdf"})
        if kind == "gzip": return response(**{"content-encoding": "gzip"})
        if kind == "loop": return response(status=302, location="/")
        if kind == "attachment": return response(**{"content-disposition": "attachment"})
        if kind == "timeout": raise httpx.ReadTimeout("private-marker")
        return response("private-marker", status=403)
    result = asyncio.run(service(handler).read("https://example.com/"))
    assert result["error"]["code"] == code
    assert "private-marker" not in json.dumps(result)


def test_text_truncation_fits_stdio_frame_and_http_html_extraction():
    result = asyncio.run(service(lambda r: response("😀" * 9000)).read("https://example.com/"))
    assert result["truncated"] and len(result["content"]) == 8000
    assert len(json.dumps(result).encode()) < 128000  # 服务端使用 ensure_ascii=False，下面检查实际协议大小。
    assert len(json.dumps(result, ensure_ascii=False).encode()) < 64000
    text = "这是用于测试的合成文章段落，包含只读网页证据。" * 30
    result = asyncio.run(service(lambda r: response(f"<html><body><article><p>{text}</p></article><script>secretScript</script></body></html>", **{"content-type": "text/html"})).read("https://example.com/"))
    assert text in result["content"] and "secretScript" not in result["content"]
    assert result["mode"] == "http"


def test_auto_fallback_only_for_empty_html(monkeypatch):
    browser = service(lambda r: response("<html><body><div id='app'></div></body></html>", **{"content-type": "text/html"}))
    calls = []
    async def render(url):
        calls.append(url)
        return {"mode": "playwright"}
    monkeypatch.setattr(browser, "_render", render)
    assert asyncio.run(browser.read("https://example.com/"))["mode"] == "playwright"
    assert len(calls) == 1
    blocked = service(lambda r: response(status=403))
    monkeypatch.setattr(blocked, "_render", render)
    assert asyncio.run(blocked.read("https://example.com/"))["error"]
    assert len(calls) == 1


def test_search_missing_and_valid_mock_response():
    missing = asyncio.run(service(lambda r: pytest.fail("no search without key")).web_search("合成查询"))
    assert missing["available"] is False and missing["error"]["code"] == "SEARCH_UNAVAILABLE"
    def handler(request):
        assert request.headers["host"] == "api.tavily.com" and request.method == "POST"
        assert json.loads(request.content)["query"] == "合成查询"
        return response(json.dumps({"results": [{"url": "https://example.com/page", "title": "合成标题", "content": "摘要"}]}), **{"content-type": "application/json"})
    result = asyncio.run(service(handler, SecretStr("synthetic-key")).web_search("合成查询"))
    assert result["results"][0]["mode"] == "search_snippet"
    assert "synthetic-key" not in json.dumps(result)


@pytest.mark.parametrize("content,status", [("not json", 200), ('{"results": {}}', 200), ('{"results": [null]}', 200), ('[]', 200), ('secret', 401), ('secret', 302)])
def test_search_invalid_response_never_echoes(content, status):
    result = asyncio.run(service(lambda r: response(content, status, **{"content-type": "application/json"}), SecretStr("synthetic-key")).web_search("synthetic"))
    assert result["results"] == [] and result["error"]
    assert "secret" not in json.dumps(result)


def test_browser_application_private_protocol_and_credential_replacement(tmp_path):
    async def scenario():
        app = Application()
        async def call(method, params=None):
            return await app.handle(json.dumps({"v": 1, "id": str(uuid4()), "method": method, "params": params or {}}).encode())
        try:
            await call("hello")
            await call("initialize", {"data_directory": str(tmp_path), "credentials": {}})
            created = await call("missions.create", {"client_request_id": str(uuid4()), "title": "M07 合成任务"})
            mission_id = created["result"]["id"]
            result = await call("browser.search", {"mission_id": mission_id, "query": "合成"})
            assert result["result"]["error"]["code"] == "SEARCH_UNAVAILABLE"
            app.browser = service(lambda r: response("合成正文"))
            result = await call("browser.read", {"mission_id": mission_id, "url": "https://example.com/"})
            assert result["result"]["content"] == "合成正文"
            assert not (await call("browser.read", {"mission_id": mission_id, "url": "https://example.com/", "script": "click()"}))["ok"]
            assert not (await call("browser.read", {"mission_id": "missing", "url": "https://example.com/"}))["ok"]
            await call("credentials.replace", {"credentials": {"tavily": "synthetic-key"}})
            assert (await call("configuration.status"))["result"]["search_available"] is True
            await call("credentials.replace", {"credentials": {}})
            assert app.browser.key is None
        finally:
            await app.close()
    asyncio.run(scenario())
