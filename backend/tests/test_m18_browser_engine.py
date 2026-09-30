"""真实Chromium + 合成页面/HTTP/DNS；外发替身计数证明未经审批零写入。"""

import asyncio
import json
import os
from pathlib import Path

import httpx
import pytest

from orvia_backend.automation.browser import BrowserAdapter
from orvia_backend.browser.write_network import WriteNetwork
from orvia_backend.computer.paths import ToolError

from test_browser import dns, response


pytestmark = pytest.mark.skipif(os.environ.get("ORVIA_BROWSER_TEST") != "1", reason="真实Chromium合成测试须显式启用")


MARKUP = """<!doctype html><html><head><meta charset=utf-8><title>M18 synthetic</title></head><body>
<label>正文<input id=text name=text></label><label>选项<select id=choice><option value=a>A</option><option value=b>B</option></select></label>
<label>启用<input id=flag type=checkbox></label><label>上传<input id=file type=file></label>
<button id=form>提交表单</button><button id=message>发送消息</button><button id=upload>提交上传</button><button id=delete>删除记录</button><button id=transaction>确认交易</button><button id=read>读取业务</button><button id=fail>失败提交</button><button id=local>本地提示</button>
<output id=result></output><script>
for(const kind of ['form','message','upload','delete','transaction'])document.getElementById(kind).onclick=async()=>{
  let body=JSON.stringify({kind,text:document.getElementById('text').value});
  let headers={'content-type':'application/json'};
  if(kind==='upload'){body=new FormData();body.append('file',document.getElementById('file').files[0]);headers={};}
  const r=await fetch('/'+kind,{method:kind==='delete'?'DELETE':'POST',body,headers});document.getElementById('result').innerText=await r.text();
};
document.getElementById('read').onclick=()=>fetch('/business').then(r=>r.text()).then(t=>document.getElementById('result').innerText=t);
document.getElementById('fail').onclick=()=>fetch('/failure',{method:'POST',body:'synthetic'}).catch(()=>{});
document.getElementById('local').onclick=()=>document.getElementById('result').innerText='纯本地提示';
</script></body></html>"""


async def wait_pending(adapter, cid, sid):
    for _ in range(200):
        result = await adapter.pending(cid, sid)
        if result["pending_request"]:
            return result
        await asyncio.sleep(0.02)
    pytest.fail("did not pause outgoing request")


async def wait_result(adapter, cid, sid, status="response_received"):
    for _ in range(200):
        result = await adapter.pending(cid, sid)
        if result["result"] and result["result"]["status"] == status:
            return result
        await asyncio.sleep(0.02)
    pytest.fail("did not finish request")


async def click(adapter, cid, sid, name, category):
    observation = await adapter.observe(cid, sid)
    target = next(item for item in observation["controls"] if item["name"] == name)
    return await adapter.start_action(cid, sid, target["control_id"], "click", None, observation["state_hash"], category=category)


def test_actual_engine_all_five_categories_approve_once_and_verify(tmp_path: Path):
    calls = []
    def handler(request):
        calls.append((request.method, request.url.path, request.content))
        if request.url.path == "/":
            assert "cookie" not in request.headers
            return response(MARKUP, **{"content-type": "text/html", "set-cookie": "synthetic=private;Secure;HttpOnly"})
        assert request.headers["cookie"] == "synthetic=private"
        return response("合成业务完成:" + request.url.path[1:])
    async def run():
        adapter = BrowserAdapter(WriteNetwork(transport=httpx.MockTransport(handler), resolver=dns), headless=True)
        try:
            opened = await adapter.open("one", "https://m18.example/", allowed_actions=["form", "message", "upload", "delete", "transaction"])
            sid = opened["session_id"]
            with pytest.raises(ToolError):
                await adapter.observe("different", sid)
            text = next(item for item in opened["controls"] if item["name"] == "正文")
            await adapter.start_action("one", sid, text["control_id"], "fill", "合成内容", opened["state_hash"], category="form")
            await asyncio.sleep(0.1)
            fresh = await adapter.observe("one", sid)
            with pytest.raises(ToolError, match="页面状态"):
                await adapter.start_action("one", sid, text["control_id"], "fill", "x", opened["state_hash"], category="form")
            choice = next(item for item in fresh["controls"] if item["name"] == "选项")
            await adapter.start_action("one", sid, choice["control_id"], "select", "b", fresh["state_hash"], category="form")
            await asyncio.sleep(0.1)
            fresh = await adapter.observe("one", sid)
            checkbox = next(item for item in fresh["controls"] if item["name"] == "启用")
            await adapter.start_action("one", sid, checkbox["control_id"], "check", True, fresh["state_hash"], category="form")
            await asyncio.sleep(0.1)
            upload_path = tmp_path / "synthetic.txt"
            upload_path.write_text("synthetic upload", encoding="utf-8")
            fresh = await adapter.observe("one", sid)
            upload_control = next(item for item in fresh["controls"] if item["name"] == "上传")
            await adapter.start_action("one", sid, upload_control["control_id"], "upload", None, fresh["state_hash"], str(upload_path), category="upload")
            await asyncio.sleep(0.1)
            for kind, name in [("form", "提交表单"), ("message", "发送消息"), ("upload", "提交上传"), ("delete", "删除记录"), ("transaction", "确认交易")]:
                previous = len(calls)
                await click(adapter, "one", sid, name, kind)
                paused = await wait_pending(adapter, "one", sid)
                request = paused["pending_request"]
                assert len(calls) == previous and request["category"] == kind
                assert request["url"] == "https://m18.example/" + kind
                if kind == "upload":
                    assert request["files"][0]["name"] == "synthetic.txt" and request["files"][0]["bytes"] == 16
                    assert not request["body_preview_complete"]
                else:
                    assert request["body_preview_complete"] and not request["fields_truncated"]
                assert "private" not in json.dumps(paused, ensure_ascii=False)
                await adapter.approve_request("one", sid, request["request_id"], request["revision"], True)
                with pytest.raises(ToolError):
                    await adapter.approve_request("one", sid, request["request_id"], request["revision"], True)
                done = await wait_result(adapter, "one", sid)
                assert not done["result"]["verified"]
                assert done["result"]["evidence"]["http_status"] == 200 and len(calls) == previous + 1
                if kind == "form":
                    unmatched = await adapter.verify_result("one", sid, "此文字不会出现")
                    assert unmatched["status"] == "awaiting_verification" and not unmatched["verified"]
                verified = await adapter.verify_result("one", sid, "合成业务完成:" + kind)
                assert verified["verified"] and verified["evidence"]["matched"]
                await asyncio.sleep(0.1)
            assert [path for method, path, body in calls if method != "GET"] == ["/form", "/message", "/upload", "/delete", "/transaction"]
            assert b"synthetic upload" in next(body for method, path, body in calls if path == "/upload")
        finally:
            await adapter.close_all()
    asyncio.run(run())


def test_actual_engine_get_business_pause_reject_cancel_and_no_replay():
    calls = []
    def handler(request):
        calls.append(request.url.path)
        return response(MARKUP if request.url.path == "/" else "synthetic", **{"content-type": "text/html"})
    async def run():
        adapter = BrowserAdapter(WriteNetwork(transport=httpx.MockTransport(handler), resolver=dns), headless=True)
        try:
            sid = (await adapter.open("one", "https://m18.example/", allowed_actions=["form"]))["session_id"]
            await click(adapter, "one", sid, "读取业务", "form")
            request = (await wait_pending(adapter, "one", sid))["pending_request"]
            assert request["method"] == "GET" and "/business" not in calls
            await adapter.approve_request("one", sid, request["request_id"], request["revision"], False)
            await asyncio.sleep(0.1)
            assert "/business" not in calls
            await click(adapter, "one", sid, "提交表单", "form")
            await wait_pending(adapter, "one", sid)
            result = await adapter.cancel("one", sid)
            assert result["status"] == "cancelled" and calls == ["/"]
            sid2 = (await adapter.open("one", "https://m18.example/", allowed_actions=["form"]))["session_id"]
            assert (await adapter.pending("one", sid2))["pending_request"] is None
            assert calls == ["/", "/"]
            with pytest.raises(ToolError):
                await click(adapter, "one", sid2, "发送消息", "message")
        finally:
            await adapter.close_all()
    asyncio.run(run())


def test_actual_engine_autosave_cross_origin_unknown_workers_and_send_failure():
    calls = []
    markup = MARKUP.replace("</script>", """document.getElementById('text').oninput=()=>fetch('/autosave',{method:'POST',body:'synthetic'}).catch(()=>{});
        fetch('https://outside.example/secret',{method:'POST',body:'never'}).catch(()=>{});
        new WebSocket('wss://m18.example/socket');
        try{new Worker('/worker.js')}catch(e){};</script>""")
    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/":
            return response(markup, **{"content-type": "text/html"})
        if request.url.path == "/failure":
            raise httpx.ReadTimeout("private sensitive network marker")
        return response("synthetic")
    async def run():
        adapter = BrowserAdapter(WriteNetwork(transport=httpx.MockTransport(handler), resolver=dns), headless=True)
        try:
            opened = await adapter.open("one", "https://m18.example/", allowed_actions=["form"])
            sid = opened["session_id"]
            text = next(item for item in opened["controls"] if item["name"] == "正文")
            await adapter.start_action("one", sid, text["control_id"], "fill", "synthetic", opened["state_hash"], category="form")
            request = (await wait_pending(adapter, "one", sid))["pending_request"]
            assert request["url"].endswith("/autosave") and calls == ["/"]
            await adapter.approve_request("one", sid, request["request_id"], request["revision"], False)
            await asyncio.sleep(0.1)
            await click(adapter, "one", sid, "失败提交", "form")
            request = (await wait_pending(adapter, "one", sid))["pending_request"]
            await adapter.approve_request("one", sid, request["request_id"], request["revision"], True)
            failed = await wait_result(adapter, "one", sid, "uncertain")
            assert calls == ["/", "/failure"] and "private sensitive" not in json.dumps(failed)
            await asyncio.sleep(0.1)
            assert calls.count("/failure") == 1
        finally:
            await adapter.close_all()
    asyncio.run(run())


def test_actual_engine_cancel_during_outbound_is_uncertain_and_never_replayed():
    async def run():
        calls = []
        entered = asyncio.Event()
        waiting = asyncio.Event()
        async def handler(request):
            calls.append(request.url.path)
            if request.url.path == "/":
                return response(MARKUP, **{"content-type": "text/html"})
            entered.set()
            await waiting.wait()
            return response("synthetic late reply")
        adapter = BrowserAdapter(WriteNetwork(transport=httpx.MockTransport(handler), resolver=dns), headless=True)
        try:
            sid = (await adapter.open("one", "https://m18.example/", allowed_actions=["form"]))["session_id"]
            await click(adapter, "one", sid, "提交表单", "form")
            request = (await wait_pending(adapter, "one", sid))["pending_request"]
            await adapter.approve_request("one", sid, request["request_id"], request["revision"], True)
            await asyncio.wait_for(entered.wait(), 3)
            result = await adapter.cancel("one", sid)
            assert result["status"] == "uncertain" and calls == ["/", "/form"]
            sid2 = (await adapter.open("one", "https://m18.example/", allowed_actions=["form"]))["session_id"]
            assert (await adapter.pending("one", sid2))["pending_request"] is None
            assert calls == ["/", "/form", "/"]
        finally:
            waiting.set()
            await adapter.close_all()
    asyncio.run(run())


def test_actual_engine_no_http_click_repeated_verification_has_no_completion_or_keyerror():
    calls = []
    def handler(request):
        calls.append(request.url.path)
        markup = MARKUP.replace("<output", '<label>普通标签<input name="api_token" value="synthetic-sensitive"></label><textarea name="secret">synthetic-textarea-secret</textarea><output')
        return response(markup, **{"content-type": "text/html"})
    async def run():
        adapter = BrowserAdapter(WriteNetwork(transport=httpx.MockTransport(handler), resolver=dns), headless=True)
        try:
            opened = await adapter.open("one", "https://m18.example/", allowed_actions=["form"])
            sid = opened["session_id"]
            assert "synthetic-sensitive" not in json.dumps(opened) and "synthetic-textarea-secret" not in json.dumps(opened)
            await click(adapter, "one", sid, "本地提示", "form")
            await asyncio.sleep(0.1)
            for _ in range(2):
                result = await adapter.verify_result("one", sid, "纯本地提示")
                assert result["status"] == "awaiting_verification" and not result["verified"] and result["evidence"] == {}
            assert calls == ["/"]
        finally:
            await adapter.close_all()
    asyncio.run(run())


def test_actual_engine_cancel_http_receipt_without_business_verification_is_uncertain():
    calls = []
    def handler(request):
        calls.append(request.url.path)
        return response(MARKUP if request.url.path == "/" else "unverified synthetic receipt", **{"content-type": "text/html"})
    async def run():
        adapter = BrowserAdapter(WriteNetwork(transport=httpx.MockTransport(handler), resolver=dns), headless=True)
        try:
            sid = (await adapter.open("one", "https://m18.example/", allowed_actions=["form"]))["session_id"]
            await click(adapter, "one", sid, "提交表单", "form")
            request = (await wait_pending(adapter, "one", sid))["pending_request"]
            await adapter.approve_request("one", sid, request["request_id"], request["revision"], True)
            receipt = await wait_result(adapter, "one", sid)
            assert not receipt["result"]["verified"] and receipt["result"]["evidence"]["http_status"] == 200
            result = await adapter.cancel("one", sid)
            assert result["status"] == "uncertain" and not result["verified"] and calls == ["/", "/form"]
            sid2 = (await adapter.open("one", "https://m18.example/", allowed_actions=["form"]))["session_id"]
            assert (await adapter.pending("one", sid2))["pending_request"] is None and calls == ["/", "/form", "/"]
        finally:
            await adapter.close_all()
    asyncio.run(run())


def test_actual_engine_long_history_url_and_combined_observation_budget_fail_closed():
    calls = []
    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/large":
            markup = "<!doctype html><meta charset=utf-8><body>" + "合" * 4000 + "".join('<input value="' + "成" * 200 + '">' for _ in range(30))
        else:
            markup = MARKUP
        return response(markup, **{"content-type": "text/html"})
    async def run():
        adapter = BrowserAdapter(WriteNetwork(transport=httpx.MockTransport(handler), resolver=dns), headless=True)
        try:
            sid = (await adapter.open("one", "https://m18.example/", allowed_actions=["form"]))["session_id"]
            session = adapter._sessions[sid]
            await session.page.evaluate("() => history.replaceState({},'', '?x='+'A'.repeat(100000))")
            with pytest.raises(ToolError, match="页面地址超过"):
                await adapter.pending("one", sid)
            assert calls == ["/"]
            await adapter.close("one", sid)
            with pytest.raises(ToolError, match="页面观察超过"):
                await adapter.open("one", "https://m18.example/large", allowed_actions=["form"])
            assert adapter._sessions == {} and calls == ["/", "/large"]
        finally:
            await adapter.close_all()
    asyncio.run(run())


def test_actual_engine_manual_non_https_page_cannot_be_observed_or_operated():
    calls = []
    def handler(request):
        calls.append(request.url.path)
        return response(MARKUP, **{"content-type": "text/html"})
    async def run():
        adapter = BrowserAdapter(WriteNetwork(transport=httpx.MockTransport(handler), resolver=dns), headless=True)
        try:
            opened = await adapter.open("one", "https://m18.example/", allowed_actions=["form"])
            sid = opened["session_id"]
            session = adapter._sessions[sid]
            await session.page.goto("data:text/html,<button>synthetic unsafe page</button>")
            with pytest.raises(ToolError, match="公开"):
                await adapter.observe("one", sid)
            target = next(item for item in opened["controls"] if item["name"] == "正文")
            with pytest.raises(ToolError, match="公开"):
                await adapter.start_action("one", sid, target["control_id"], "fill", "synthetic", opened["state_hash"], category="form")
            assert calls == ["/"]
        finally:
            await adapter.close_all()
    asyncio.run(run())


def test_actual_engine_upload_rejects_hardlink_alias_before_page_reads_file(tmp_path):
    calls = []
    original, alias = tmp_path / "synthetic-original.txt", tmp_path / "synthetic-alias.txt"
    original.write_text("synthetic protected upload", encoding="utf-8")
    os.link(original, alias)
    def handler(request):
        calls.append(request.url.path)
        return response(MARKUP, **{"content-type": "text/html"})
    async def run():
        adapter = BrowserAdapter(WriteNetwork(transport=httpx.MockTransport(handler), resolver=dns), headless=True)
        try:
            opened = await adapter.open("one", "https://m18.example/", allowed_actions=["upload"])
            sid = opened["session_id"]
            control = next(item for item in opened["controls"] if item["name"] == "上传")
            with pytest.raises(ToolError, match="硬链接"):
                await adapter.start_action("one", sid, control["control_id"], "upload", None, opened["state_hash"], str(alias), category="upload")
            assert await adapter._sessions[sid].page.locator("#file").evaluate("el=>el.files.length") == 0
            assert (await adapter.pending("one", sid))["pending_request"] is None and calls == ["/"]
        finally:
            await adapter.close_all()
    asyncio.run(run())


def test_actual_engine_many_controls_use_bounded_handles_before_protocol_transfer():
    def handler(request):
        return response(MARKUP, **{"content-type": "text/html"})
    async def run():
        adapter = BrowserAdapter(WriteNetwork(transport=httpx.MockTransport(handler), resolver=dns), headless=True)
        try:
            sid = (await adapter.open("one", "https://m18.example/", allowed_actions=["form"]))["session_id"]
            session = adapter._sessions[sid]
            await session.page.evaluate("() => {document.body.textContent=''; for(let i=0;i<1000;i++){const input=document.createElement('input');input.name='synthetic'+i;document.body.append(input);}}")
            async def reject_unbounded_query(*args, **kwargs):
                pytest.fail("controller must not materialize all untrusted element handles")
            session.page.query_selector_all = reject_unbounded_query
            observation = await adapter.observe("one", sid)
            assert 0 < len(observation["controls"]) <= 80 and len(session.controls) <= 80
            assert all(item["control_id"] != "c999" for item in observation["controls"])
            assert len(json.dumps(observation, ensure_ascii=False).encode()) <= 24 * 1024
        finally:
            await adapter.close_all()
    asyncio.run(run())


@pytest.mark.parametrize("redirect", [False, True])
def test_actual_engine_initial_get_write_session_and_redirect_fails_closed(redirect):
    calls = []
    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/read":
            return response(status=302, location="https://m18.example/write")
        return response(MARKUP, **{"content-type": "text/html"})
    async def run():
        adapter = BrowserAdapter(WriteNetwork(transport=httpx.MockTransport(handler), resolver=dns), headless=True)
        try:
            if redirect:
                with pytest.raises(ToolError, match="重定向不直接跟随"):
                    await adapter.open("one", "https://m18.example/read", allowed_actions=["form"], get_write_paths=["/write"])
                assert calls == ["/read"] and adapter._sessions == {}
                return
            opened = await adapter.open("one", "https://m18.example/" + ("read" if redirect else "write"), allowed_actions=["form"], get_write_paths=["/write"])
            sid = opened["session_id"]
            assert opened["url"] == "about:blank" and opened["controls"] == [] and "尚未加载" in opened["notice"]
            paused = await adapter.pending("one", sid)
            request = paused["pending_request"]
            assert request["method"] == "GET" and request["url"] == "https://m18.example/write"
            assert calls == (["/read"] if redirect else [])
            await adapter.approve_request("one", sid, request["request_id"], request["revision"], True)
            await wait_result(adapter, "one", sid)
            await asyncio.wait_for(adapter._sessions[sid].active, 3)
            observation = await adapter.observe("one", sid)
            assert observation["url"] == "https://m18.example/write" and observation["controls"]
            assert calls == (["/read", "/write"] if redirect else ["/write"])
        finally:
            await adapter.close_all()
    asyncio.run(run())
