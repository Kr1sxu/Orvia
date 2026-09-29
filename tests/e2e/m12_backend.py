"""M12 真正 BrowserService + SafeHTTP，DNS/HTTP 合成替身，绝不联网或调用模型。"""
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend/src"))
import httpx
import orvia_backend.application as application
from orvia_backend.browser.network import SafeHTTP
from orvia_backend.browser.service import BrowserService
from orvia_backend.configuration.client import ModelClient
from orvia_backend.server import serve


class Body(httpx.AsyncByteStream):
    def __init__(self, text):
        self.data = text.encode("utf-8")

    async def __aiter__(self):
        yield self.data


async def resolver(host, port):
    return ["93.184.216.34"]


def handler(request):
    if request.method == "POST":
        query = json.loads(request.content)["query"]
        if query == "失败":
            return httpx.Response(503, stream=Body("synthetic-private-provider-body"))
        items = [] if query == "空结果" else [{"url":"https://example.com/article", "title":"Orvia 合成资料", "content":"合成来源摘要：许可条件。"}]
        return httpx.Response(200, headers={"content-type":"application/json"}, stream=Body(json.dumps({"results":items})))
    if request.url.path == "/fail":
        return httpx.Response(403, stream=Body("private-response"))
    if request.url.path == "/long":
        return httpx.Response(200,headers={"content-type":"text/plain"},stream=Body("合成许可正文😀" * 1600))
    html = '<html><head><title>Orvia 合成正文</title></head><body><article>' + ('<p>合成许可要求保留来源，引用可追溯。</p>' * 20) + '</article></body></html>'
    return httpx.Response(200,headers={"content-type":"text/html"},stream=Body(html))


async def no_model(*args, **kwargs):
    raise AssertionError("M12 synthetic flow must not call a model")


ModelClient.complete = no_model
application.BrowserService = lambda: BrowserService(network=SafeHTTP(transport=httpx.MockTransport(handler), resolver=resolver))
asyncio.run(serve(sys.stdin.buffer, sys.stdout.buffer))
