"""M18写出口合成验证：公共IP替身HTTP，绝不访问第三方网站或开发凭据。"""

import asyncio
import json

import httpx
import pytest

from orvia_backend.automation.browser import _preview_fields, _public_url, _request_preview
from orvia_backend.browser.network import BrowserError
from orvia_backend.browser.write_network import WriteNetwork, write_url

from test_browser import dns, response


@pytest.mark.parametrize("url", ["http://example.com/", "https://127.0.0.1/", "https://example.com:444/", "https://u:p@example.com/", "https://example.com/#secret"])
def test_write_url_rejects_unsafe_before_network(url):
    with pytest.raises(BrowserError):
        write_url(url)


def test_write_network_pins_ip_and_keeps_session_secrets_only_in_request():
    calls = []
    def handler(request):
        calls.append(request)
        assert request.url.host == "93.184.216.34"
        assert request.headers["host"] == "m18.example"
        assert request.extensions["sni_hostname"] == "m18.example"
        assert request.headers["cookie"] == "synthetic=private"
        assert request.headers["authorization"] == "Bearer synthetic"
        assert "x-unknown-secret" not in request.headers
        assert request.method == "POST" and request.content == b"name=synthetic"
        return response("accepted", **{"set-cookie": "session=synthetic;Secure;HttpOnly"})
    network = WriteNetwork(transport=httpx.MockTransport(handler), resolver=dns)
    async def run():
        status, headers, content = await network.fetch("https://m18.example/submit", method="POST", body=b"name=synthetic",
            headers={"cookie": "synthetic=private", "authorization": "Bearer synthetic", "x-unknown-secret": "never-forward"})
        assert status == 200 and content == b"accepted" and "set-cookie" in headers
    asyncio.run(run())
    assert len(calls) == 1


@pytest.mark.parametrize("addresses", [["127.0.0.1"], ["93.184.216.34", "10.0.0.1"], []])
def test_write_network_blocks_private_or_mixed_dns(addresses):
    async def resolver(host, port):
        return addresses
    network = WriteNetwork(transport=httpx.MockTransport(lambda request: pytest.fail("must not send")), resolver=resolver)
    with pytest.raises(BrowserError, match="DNS"):
        asyncio.run(network.fetch("https://m18.example/submit", method="DELETE"))


def test_write_network_limits_and_does_not_follow_redirect_or_retry():
    calls = []
    def handler(request):
        calls.append(request)
        return response(status=302, location="https://outside.example/")
    network = WriteNetwork(transport=httpx.MockTransport(handler), resolver=dns)
    assert asyncio.run(network.fetch("https://m18.example/submit", method="POST"))[0] == 302
    assert len(calls) == 1
    with pytest.raises(BrowserError):
        asyncio.run(network.fetch("https://m18.example/submit", method="TRACE"))
    with pytest.raises(BrowserError):
        asyncio.run(network.fetch("https://m18.example/submit", method="POST", body=b"x" * (3 * 1024 * 1024 + 1)))
    assert len(calls) == 1


def test_request_preview_redacts_credentials_payment_and_query():
    body = json.dumps({"title": "合成消息", "password": "never-show", "csrf_token": "never-show", "card_number": "never-show", "nested": {"secret": "never-show"}}).encode()
    fields, redacted = _preview_fields(body, "application/json", "https://m18.example/")
    assert redacted and "never-show" not in json.dumps(fields)
    assert fields[0]["value"] == "合成消息"
    assert "never-show" not in _public_url("https://m18.example/?access_token=never-show&title=synthetic")
    fields, redacted = _preview_fields(b"raw-sensitive", "text/plain", "https://m18.example/")
    assert redacted and "raw-sensitive" not in json.dumps(fields)


def test_request_preview_checks_secret_marker_before_field_name_truncation():
    name = "synthetic" * 21 + "_password"
    body = (name + "=never-show").encode()
    fields, redacted, metadata = _request_preview(body, "application/x-www-form-urlencoded", "https://m18.example/")
    assert redacted and metadata["fields_truncated"] and not metadata["body_preview_complete"]
    assert "never-show" not in json.dumps(fields)
    multipart = b'--test\r\nContent-Disposition: form-data; name="' + name.encode() + b'"\r\n\r\nnever-show\r\n--test--\r\n'
    fields, redacted, metadata = _request_preview(multipart, "multipart/form-data; boundary=test", "https://m18.example/")
    assert redacted and metadata["fields_truncated"] and "never-show" not in json.dumps(fields)


def test_pending_never_returns_over_budget_protocol_dto():
    from types import SimpleNamespace
    from orvia_backend.automation.browser import BrowserAdapter
    from orvia_backend.computer.paths import ToolError
    adapter = BrowserAdapter()
    session = SimpleNamespace(cid="one", closed=False, pending={"preview": {"untrusted": "x" * (48 * 1024)}}, status="awaiting_approval", result=None)
    adapter._sessions["synthetic"] = session
    async def observation(cid, sid):
        return {"session_id": sid, "controls": []}
    adapter.observe = observation
    with pytest.raises(ToolError, match="协议预算"):
        asyncio.run(adapter.pending("one", "synthetic"))


def test_outbound_approval_returns_only_safe_audit_metadata():
    from types import SimpleNamespace
    from orvia_backend.automation.browser import BrowserAdapter
    async def run():
        adapter = BrowserAdapter()
        fields, redacted, metadata = _request_preview(b"", "", "https://m18.example/message?text=synthetic-private-message&token=synthetic-private-token")
        preview = {"request_id": "synthetic", "revision": "same", "method": "GET",
                   "url": "https://m18.example/message?text=synthetic-private-message&token=[hidden]",
                   "bytes": 0, "sha256": "bodyhash", "url_sha256": "urlhash", "category": "message",
                   "fields": fields, **metadata}
        decision = asyncio.get_running_loop().create_future()
        session = SimpleNamespace(cid="one", closed=False, pending={"preview": preview, "decision": decision})
        adapter._sessions["session"] = session
        result = await adapter.approve_request("one", "session", "synthetic", "same", True)
        assert decision.result() is True and result["request_meta"]["method"] == "GET"
        assert result["request_meta"]["url"].startswith("https://m18.example/message?")
        assert result["request_meta"]["url_sha256"] == "urlhash" and result["request_meta"]["file_count"] == 0
        encoded = json.dumps(result)
        assert "synthetic-private" not in encoded and "fields" not in result["request_meta"]
        assert set(result["request_meta"]) == {"method", "url", "body_bytes", "body_sha256", "url_sha256", "category", "body_preview_complete", "fields_truncated", "file_count"}
    asyncio.run(run())


@pytest.mark.parametrize("method", ["HEAD", "OPTIONS"])
def test_non_get_resource_requests_require_actual_approval_and_rejection_never_sends(method):
    from types import SimpleNamespace
    from orvia_backend.automation.browser import BrowserAdapter, _Session
    from orvia_backend.browser.network import origin
    calls = []
    def handler(request):
        calls.append(request)
        pytest.fail("rejected request must not reach HTTP transport")
    async def run():
        adapter = BrowserAdapter(WriteNetwork(transport=httpx.MockTransport(handler), resolver=dns))
        page = SimpleNamespace(main_frame=object())
        async def all_headers():
            return {}
        request = SimpleNamespace(url="https://m18.example/resource", method=method, resource_type="other",
                                  frame=page.main_frame, post_data_buffer=b"", all_headers=all_headers)
        aborted = []
        async def abort():
            aborted.append(True)
        route = SimpleNamespace(request=request, abort=abort)
        session = _Session("one", "session", None, None, page, {origin(request.url)}, {"form"}, set())
        adapter._sessions[session.sid] = session
        task = asyncio.create_task(adapter._route(session, route))
        try:
            for _ in range(50):
                if session.pending:
                    break
                await asyncio.sleep(0.01)
            assert session.pending and calls == [] and session.sent == 0
            preview = session.pending["preview"]
            assert preview["method"] == method
            await adapter.approve_request("one", "session", preview["request_id"], preview["revision"], False)
            await asyncio.wait_for(task, 1)
            assert aborted == [True] and calls == []
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    asyncio.run(run())


def test_request_preview_marks_limits_and_fully_shows_budgeted_ordinary_fields():
    ordinary = "合成" * 300
    fields, redacted, metadata = _request_preview(json.dumps({"text": ordinary, "order": {"amount": 12}}).encode(), "application/json", "https://m18.example/")
    assert not redacted and metadata["body_preview_complete"] and not metadata["fields_truncated"]
    assert fields[0]["value"] == ordinary and fields[1] == {"name": "order.amount", "value": "12"}
    fields, redacted, metadata = _request_preview(json.dumps({f"field{i}": str(i) for i in range(31)}).encode(), "application/json", "https://m18.example/")
    assert len(fields) == 30 and metadata["fields_truncated"] and not metadata["body_preview_complete"]
    fields, redacted, metadata = _request_preview(json.dumps({"text": "x" * 9000}).encode(), "application/json", "https://m18.example/")
    assert metadata["fields_truncated"] and "未展示" in fields[0]["value"] and "不完整" in metadata["preview_notice"]
    fields, redacted, metadata = _request_preview(b"password=private&title=synthetic", "application/x-www-form-urlencoded", "https://m18.example/")
    assert redacted and not metadata["body_preview_complete"] and "private" not in json.dumps(fields)


def test_multipart_preview_actual_filename_bytes_hash_and_rejects_multiple_files():
    import hashlib
    body = (b'--synthetic\r\nContent-Disposition: form-data; name="title"\r\n\r\nexample\r\n'
            b'--synthetic\r\nContent-Disposition: form-data; name="file"; filename="synthetic.txt"\r\n'
            b'Content-Type: text/plain\r\n\r\nsynthetic upload\r\n--synthetic--\r\n')
    fields, redacted, metadata = _request_preview(body, "multipart/form-data; boundary=synthetic", "https://m18.example/upload")
    assert metadata["files"] == [{"field": "file", "name": "synthetic.txt", "bytes": 16, "sha256": hashlib.sha256(b"synthetic upload").hexdigest()}]
    assert not metadata["body_preview_complete"] and not metadata["fields_truncated"]
    assert fields[0] == {"name": "title", "value": "example"}
    double = body.replace(b"--synthetic--\r\n", body[body.find(b'--synthetic\r\nContent-Disposition: form-data; name="file"'):])
    with pytest.raises(BrowserError, match="一个"):
        _request_preview(double, "multipart/form-data; boundary=synthetic", "https://m18.example/upload")
