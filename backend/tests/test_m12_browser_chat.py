"""M12 合成网络、真实 SQLite/FTS；禁止访问真实网页、用户文件或模型。"""
import asyncio
import json
from uuid import uuid4

import pytest
from pydantic import SecretStr

from orvia_backend.application import Application
from test_browser import service, response


class Harness:
    def __init__(self, directory):
        self.app, self.directory, self.calls = Application(), directory, []
        self.content = "Orvia 合成网页正文，许可条件为保留来源。"

    def network(self, request):
        self.calls.append(request)
        if request.method == "POST":
            return response(json.dumps({"results": [
                {"url": "https://example.com/synthetic", "title": "合成来源", "content": "Orvia 合成搜索摘要"},
                {"url": "https://example.com/synthetic", "title": "合成来源", "content": "Orvia 合成搜索摘要"},
            ]}), **{"content-type": "application/json"})
        return response(self.content)

    async def open(self):
        await self.call("hello")
        await self.call("initialize", {"data_directory": str(self.directory), "credentials": {}})
        # 只替换已有 Browser 的安全网络适配器；产品不提供 mock 开关。
        self.app.browser.network = service(self.network).network
        self.app.browser.key = SecretStr("synthetic-only")

    async def call(self, method, params=None):
        return await self.app.handle(json.dumps({"v": 1, "id": str(uuid4()), "method": method, "params": params or {}}).encode())

    async def create(self):
        result = await self.call("chat.create", {"client_request_id": str(uuid4()), "title": "M12 合成会话"})
        return result["result"]["id"]

    async def browser(self, cid, action, **params):
        params.setdefault("request_id", str(uuid4()))
        result = await self.call("chat.browser." + action, {"id": cid, **params})
        assert result["ok"], result
        return result["result"]


def test_versions_dedup_citations_and_cross_conversation_isolation(tmp_path):
    async def run():
        h = Harness(tmp_path)
        try:
            await h.open()
            cid, other = await h.create(), await h.create()
            searched = await h.browser(cid, "search", query="Orvia")
            assert len(searched["sources"]) == 1
            eid = searched["sources"][0]["evidence_id"]
            read = await h.browser(cid, "read", url="https://example.com/synthetic")
            assert len(read["sources"]) == 2
            repeated = await h.browser(cid, "read", url="https://example.com/synthetic")
            assert len(repeated["sources"]) == 2
            ask = await h.browser(cid, "ask", query="Orvia")
            assert len(ask["messages"][-1]["data"]["items"]) == 2
            assert ask["grant"] is None and ask["operation"] is None
            before = len(h.calls)
            empty = await h.browser(other, "ask", query="Orvia")
            assert not empty["messages"][-1]["data"]["items"] and len(h.calls) == before
            assert not (await h.call("chat.browser.source", {"id": other, "evidence_id": eid}))["ok"]
            old = (await h.call("chat.browser.source", {"id": cid, "evidence_id": eid}))["result"]
            h.content = "Orvia 更新的合成正文"
            changed = await h.browser(cid, "read", url="https://example.com/synthetic")
            assert len(changed["sources"]) == 3
            assert (await h.call("chat.browser.source", {"id": cid, "evidence_id": eid}))["result"] == old
            await h.app.close()
            h.app = Application()
            await h.open()
            assert (await h.call("chat.browser.source", {"id": cid, "evidence_id": eid}))["result"] == old
            assert len((await h.browser(cid, "ask", query="Orvia"))["messages"][-1]["data"]["items"]) == 3
        finally:
            await h.app.close()
    asyncio.run(run())


def test_idempotency_budget_and_unknown_request_never_replay(tmp_path):
    async def run():
        h = Harness(tmp_path)
        try:
            await h.open()
            cid = await h.create()
            rid = str(uuid4())
            first = await h.browser(cid, "read", request_id=rid, url="https://example.com/synthetic")
            second = await h.browser(cid, "read", request_id=rid, url="https://example.com/synthetic")
            assert first == second and len(h.calls) == 1
            bad = await h.call("chat.browser.read", {"id": cid, "request_id": rid, "url": "https://example.com/changed"})
            assert not bad["ok"] and len(h.calls) == 1
            for _ in range(99):
                await h.app.chat.repository.claim(cid, str(uuid4()), "synthetic budget")
            limited = await h.call("chat.browser.search", {"id": cid, "request_id": str(uuid4()), "query": "Orvia"})
            assert limited["error"]["code"] == "BUDGET_EXCEEDED" and len(h.calls) == 1
        finally:
            await h.app.close()
    asyncio.run(run())


@pytest.mark.parametrize("action,params,code", [
    ("read", {"url": "file:///C:/secret"}, "URL_BLOCKED"),
    ("read", {"url": "http://127.0.0.1/"}, "URL_BLOCKED"),
    ("search", {"query": "合成搜索"}, "SEARCH_UNAVAILABLE"),
    ("ask", {"query": 'bad*"query'}, "INVALID_QUERY"),
])
def test_fixed_error_evidence_without_network(tmp_path, action, params, code):
    async def run():
        h = Harness(tmp_path)
        try:
            await h.open()
            h.app.browser.key = None
            cid = await h.create()
            result = await h.browser(cid, action, **params)
            data = result["messages"][-1]["data"]
            assert (data.get("error") or data)["code"] == code
            assert not h.calls and result["status"] == "failed"
            assert not result["grant"] and not result["operation"]
        finally:
            await h.app.close()
    asyncio.run(run())


def test_reject_extra_fields_missing_conversation_and_rendering_budget(tmp_path):
    async def run():
        h = Harness(tmp_path)
        try:
            await h.open()
            cid = await h.create()
            for field in ["script", "cookie", "root", "command", "upload"]:
                rejected = await h.call("chat.browser.read", {"id": cid, "request_id": str(uuid4()), "url": "https://example.com/", field: "evil"})
                assert rejected["error"]["code"] == "INVALID_PARAMS"
            missing = await h.call("chat.browser.read", {"id": str(uuid4()), "request_id": str(uuid4()), "url": "https://example.com/"})
            assert missing["error"]["code"] == "NOT_FOUND" and not h.calls
            h.content = "😀" * 9000
            for n in range(22):
                snapshot = await h.browser(cid, "read", url=f"https://example.com/{n}")
                assert len(json.dumps(snapshot, ensure_ascii=False).encode()) < 46 * 1024
            assert snapshot["sources_truncated"]
            item = snapshot["sources"][0]
            detail = (await h.call("chat.browser.source", {"id": cid, "evidence_id": item["evidence_id"]}))["result"]
            assert len(detail["content"]) == 8000 and detail["truncated"]
            assert len(json.dumps(detail, ensure_ascii=False).encode()) < 46 * 1024
        finally:
            await h.app.close()
    asyncio.run(run())


def test_empty_result_partial_error_and_html_title(tmp_path):
    async def run():
        h = Harness(tmp_path)
        try:
            await h.open()
            cid = await h.create()
            h.app.browser.network = service(lambda r: response('{"results":[]}', **{"content-type":"application/json"})).network
            empty = await h.browser(cid, "search", query="empty")
            assert not empty["sources"] and not empty["messages"][-1]["data"]["items"]
            h.app.browser.network = service(lambda r: response("", status=403)).network
            failed = await h.browser(cid, "read", url="https://example.com/")
            assert failed["sources"][0]["error"]["code"] == "HTTP_FAILED"
            h.app.browser.network = service(lambda r: response('<html><head><title>合成标题</title></head><body><article>'+('Orvia 只读证据。'*50)+'</article></body></html>', **{"content-type":"text/html"})).network
            html = await h.browser(cid, "read", url="https://example.com/title")
            assert html["sources"][0]["title"] == "合成标题"
        finally:
            await h.app.close()
    asyncio.run(run())


def test_interrupted_browser_request_requires_new_id_and_preserves_saved_evidence(tmp_path):
    async def run():
        h = Harness(tmp_path)
        try:
            await h.open()
            cid, rid = await h.create(), str(uuid4())
            original = h.app.chat.repository.append
            async def disk_failure(conversation_id, role, text, kind="text", data=None):
                if kind == "source":
                    raise OSError(28, "synthetic full disk")
                return await original(conversation_id, role, text, kind, data)
            h.app.chat.repository.append = disk_failure
            request = {"id":cid, "request_id":rid, "url":"https://example.com/synthetic"}
            failed = await h.call("chat.browser.read", request)
            assert failed["error"]["code"] == "STORAGE_FULL" and len(h.calls) == 1
            h.app.chat.repository.append = original
            again = await h.call("chat.browser.read", request)
            assert again["error"]["code"] == "REQUEST_INTERRUPTED" and len(h.calls) == 1
            await h.app.close()
            h.app = Application()
            await h.open()
            restored = (await h.call("chat.get", {"id":cid}))["result"]
            assert restored["status"] == "interrupted" and len(restored["sources"]) == 1
            assert (await h.call("chat.browser.read", request))["error"]["code"] == "REQUEST_INTERRUPTED"
            assert len(h.calls) == 1
        finally:
            await h.app.close()
    asyncio.run(run())
