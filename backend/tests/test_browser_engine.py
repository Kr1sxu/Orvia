"""显式运行的真实 Chromium 引擎验证；网页、DNS、HTTP 全为合成 mock。

默认 pytest 跳过；使用 ORVIA_BROWSER_TEST=1 运行配套 Chromium，或显式指定
ORVIA_BROWSER_TEST_CHANNEL=msedge 使用已安装 Edge，仅测试选择，不改变产品默认值。
"""
import asyncio
import os

import pytest
from playwright.async_api import BrowserType

from test_browser import response, service

pytestmark = pytest.mark.skipif(os.environ.get("ORVIA_BROWSER_TEST") != "1", reason="真实浏览器需显式启用，默认只运行 mock")


@pytest.fixture(autouse=True)
def explicit_browser_channel(monkeypatch):
    channel = os.environ.get("ORVIA_BROWSER_TEST_CHANNEL")
    if channel:
        assert channel in {"msedge", "chrome"}
        launch = BrowserType.launch
        async def selected(self, **kwargs):
            return await launch(self, **kwargs, channel=channel)
        monkeypatch.setattr(BrowserType, "launch", selected)


def test_real_engine_renders_js_and_blocks_writes_and_cross_origin():
    calls = []
    markup = '''<html><head><meta charset="utf-8"></head><body><main id="article"></main><script src="/app.js"></script></body></html>'''
    script = '''
      document.getElementById('article').innerText = '合成动态正文';
      fetch('/allowed').then(r=>r.text()).then(t=>document.getElementById('article').innerText += t);
      fetch('/write', {method:'POST', body:'synthetic'}).catch(()=>{});
      fetch('http://127.0.0.1/secret').catch(()=>{});
      fetch('https://outside.example/data').catch(()=>{});
      new WebSocket('wss://example.com/socket');
      const iframe=document.createElement('iframe'); iframe.src='/frame'; document.body.appendChild(iframe);
      const form=document.createElement('form'); form.action='/submit'; form.method='POST'; document.body.appendChild(form); form.submit();
      document.cookie='synthetic=not-reused';
    '''
    def handler(request):
        calls.append(request)
        assert request.method == "GET"
        assert "cookie" not in request.headers
        if request.url.path == "/":
            return response(markup, **{"content-type": "text/html", "set-cookie": "server=not-reused"})
        if request.url.path == "/app.js":
            return response(script, **{"content-type": "application/javascript"})
        assert request.url.path == "/allowed"
        return response("合成异步正文")
    result = asyncio.run(service(handler).read("https://example.com/", mode="playwright"))
    assert "合成动态正文" in result["content"], result
    assert "合成异步正文" in result["content"], result
    assert result["truncated"] and result["error"]["code"] == "RESOURCE_RESTRICTED"
    assert {r.url.path for r in calls} == {"/", "/app.js", "/allowed"}


def test_real_auto_and_redirect_relative_script():
    paths = []
    def handler(request):
        paths.append(request.url.path)
        if request.url.path == "/start":
            return response(status=302, location="/final/index.html")
        if request.url.path == "/final/index.html":
            return response('<html><head><meta charset="utf-8"></head><body><div id="app"></div><script src="app.js"></script></body></html>', **{"content-type": "text/html"})
        assert request.url.path == "/final/app.js"
        return response("document.getElementById('app').innerText='动态合成结果';", **{"content-type": "application/javascript"})
    result = asyncio.run(service(handler).read("https://example.com/start"))
    assert result["content"] == "动态合成结果", result
    assert result["mode"] == "playwright" and result["error"] is None
    assert result["source_url"] == "https://example.com/final/index.html"


def test_real_document_navigation_and_page_resource_budget():
    paths = []
    markup = '''<html><head><meta charset="utf-8"></head><body>合成范围测试<script>
      for(let i=0;i<45;i++) fetch('/data?i='+i).catch(()=>{});
      setTimeout(()=>location.href='/next', 100);
    </script></body></html>'''
    def handler(request):
        paths.append(request.url.path)
        if request.url.path == "/":
            return response(markup, **{"content-type": "text/html"})
        assert request.url.path == "/data"
        return response("synthetic")
    result = asyncio.run(service(handler).read("https://example.com/", mode="playwright"))
    assert result["error"], result
    assert "/next" not in paths and len(paths) <= 30


def test_real_unicode_truncation_preserves_utf8_protocol():
    import json
    markup = "<html><head><meta charset='utf-8'></head><body><script>document.body.innerText='x'+'😀'.repeat(5000);</script></body></html>"
    result = asyncio.run(service(lambda r: response(markup, **{"content-type": "text/html"})).read("https://example.com/", mode="playwright"))
    assert result["error"] is None and result["truncated"], result
    assert result["content"].startswith("x😀")
    assert len(json.dumps(result, ensure_ascii=False).encode("utf-8")) < 64000
