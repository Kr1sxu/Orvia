"""仅测试入口：公开URL/DNS绑定合成站点到自有HTTP服务器；云模型为明确替身。

SafeHTTP原校验、限额、提取、引用、SQLite和成品服务仍实际执行。此路由替换
不在产品入口注册，不读取凭据，不访问用户网站或文件。
"""
import asyncio
import json
from pathlib import Path
import sys

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend/src"))
from orvia_backend.browser.network import SafeHTTP
from orvia_backend.browser.service import BrowserService
from orvia_backend.configuration.client import ModelClient, Completion


class LocalSocketTransport(httpx.AsyncBaseTransport):
    """只映射测试固定IP/Host到本测试服务器，仍通过真实有界HTTP读取。"""
    def __init__(self, port):
        self.port = port
        self.inner = httpx.AsyncHTTPTransport(retries=0)

    async def handle_async_request(self, request):
        assert request.url.host == "93.184.216.34"
        assert request.headers["host"] == "research.example"
        assert request.method == "GET"
        url = request.url.copy_with(scheme="http", host="127.0.0.1", port=self.port)
        return await self.inner.handle_async_request(httpx.Request("GET", url, headers=request.headers))

    async def aclose(self):
        await self.inner.aclose()


async def dns(host, port):
    assert host == "research.example" and port == 80
    return ["93.184.216.34"]


def install(port, stats):
    """只由测试显式调用，两个替身均局限在独立后端测试进程。"""
    init = BrowserService.__init__
    def configured(self, key=None, **kwargs):
        init(self, key, network=SafeHTTP(transport=LocalSocketTransport(port), resolver=dns))
    BrowserService.__init__ = configured
    calls = []
    async def complete(self, profile, messages, **kwargs):
        assert profile.role == "main" and profile.model == "deepseek-flash" and profile.base_url == "https://api.deepseek.com"
        assert kwargs["max_tokens"] == 4096
        value = json.loads(messages[-1]["content"])
        fragments = value["fragments"]
        assert fragments and all("合成" in item["text"] for item in fragments)
        cited = [item["citation"] for item in fragments]
        claims = [{"text": "合成资料记载了独立观察。", "kind": "fact", "citations": [cited[0]]}]
        if len({item["evidence_id"] for item in fragments}) > 1:
            second = next(item["citation"] for item in fragments if item["evidence_id"] != fragments[0]["evidence_id"])
            claims.append({"text": "两份合成记录的数值相互冲突，需回查。", "kind": "conflict", "citations": [cited[0], second]})
        claims.append({"text": "缺少长期测量，无法确定普遍效果。", "kind": "unknown", "citations": []})
        calls.append({"model": profile.model, "fragment_count": len(fragments), "mock": True})
        Path(stats).write_text(json.dumps({"model_calls": calls, "real_cloud_calls": 0}, ensure_ascii=False), encoding="utf-8")
        return Completion(json.dumps({"answer": "比较：两份合成资料均提供观察。冲突：数值不同，需核对原文。缺口：缺少长期测量。覆盖：仅所选合成片段，不能代表完整研究。", "claims": claims}, ensure_ascii=False), (), "stop", {})
    ModelClient.complete = complete


if __name__ == "__main__":
    install(int(sys.argv[1]), sys.argv[2])
    from orvia_backend.server import serve
    asyncio.run(serve(sys.stdin.buffer, sys.stdout.buffer))
