"""M20 真实Application/SQLite/合成目录，模型与网络仅使用异步替身。"""

import asyncio
import json
from uuid import uuid4

import pytest

from orvia_backend.configuration.client import Completion, ModelUnavailable
from orvia_backend.computer.paths import ToolError
from orvia_backend.chat.routing import obvious
from test_chat import call, create, setup


def send(cid, text):
    return {"id": cid, "request_id": str(uuid4()), "text": text}


def continuation(cid, workflow, answer=None):
    value = {"id": cid, "request_id": workflow["request_id"], "continuation_id": workflow["continuation_id"]}
    if answer is not None:
        value["answer"] = answer
    return value


async def material(app, cid, title="synthetic.pdf", text="合成原文说明引用须复核。"):
    value = await app.chat.documents.save(cid, title, title.encode(), {"format": "pdf", "units": [
        {"number": 1, "locator": "第1页", "text": text, "method": "text", "confidence": None, "error": None}],
        "total_units": 1, "truncated": False, "missing_units": [], "error": None})
    await app.chat.natural.material_added(cid, "document", value["evidence_id"], input_bytes=len(title.encode()))
    return value


def test_directory_authorization_once_resume_real_batches_pages_and_restart(tmp_path):
    async def run():
        app = await setup(tmp_path)
        root = tmp_path / "synthetic-directory"
        root.mkdir()
        for index in range(121):
            (root / f"synthetic-{index:03d}.txt").write_text("合成", encoding="utf-8")
        (root / "data.csv").write_text("a,b", encoding="utf-8")
        (root / "nested").mkdir()
        (root / "nested" / "child.py").write_text("# synthetic", encoding="utf-8")
        events = []
        async def sink(value):
            events.append(value)
            if value["kind"] == "scan_batch":
                page = await app.chat.scans.page(value["conversation_id"], value["payload"]["scan_id"])
                assert page["total"] == value["payload"]["discovered"]
                assert not any(event["kind"] == "completed" for event in events)
        app.chat.set_event_sink(sink)
        cid = (await create(app))["id"]
        request = send(cid, "列出目录并按文件类型展示全部文件清单")
        first = (await call(app, "chat.natural", request))["result"]
        workflow = first["workflow"]
        assert workflow["action"] == "directory" and first["operation"] is None
        stream_id = first["stream"]["stream_id"]
        await call(app, "chat.grant", {"id": cid, "root": str(root)})
        next_request = continuation(cid, workflow)
        response = await call(app, "chat.continue", next_request)
        assert response["ok"], response
        final = response["result"]
        assert final["workflow"] is None and final["stream"]["state"] == "completed"
        assert final["stream"]["request_id"] == request["request_id"] and final["stream"]["stream_id"] == stream_id
        directory = next(item for item in final["messages"] if item["kind"] == "directory_result")["data"]
        summary = directory["summary"]
        assert summary["discovered"] == 123 and summary["visited"] == 123 and summary["displayed"] == 100
        assert summary["depth"] == 1 and summary["complete"] and not summary["truncated"]
        assert len(directory["entries"]) == 100 and "未读取正文" in final["messages"][-1]["text"]
        assert len([item for item in final["messages"] if item["kind"] == "natural_request"]) == 1
        scan_id = directory["scan_id"]
        page = (await call(app, "chat.scan.page", {"id": cid, "scan_id": scan_id, "offset": 100}))["result"]
        assert len(page["entries"]) == 23 and page["next_offset"] is None
        assert not any(item["path"] == "nested/child.py" for item in [*directory["entries"], *page["entries"]])
        (root / "synthetic-later.txt").write_text("不属于旧快照", encoding="utf-8")
        assert (await call(app, "chat.scan.page", {"id": cid, "scan_id": scan_id}))["result"]["total"] == 123
        other = (await create(app))["id"]
        assert (await call(app, "chat.scan.page", {"id": other, "scan_id": scan_id}))["error"]["code"] == "NOT_FOUND"
        assert (await call(app, "chat.continue", next_request))["error"]["code"] == "STALE_CONTINUATION"
        count = len(events)
        assert (await call(app, "chat.natural", request))["result"]["workflow"] is None
        assert len(events) == count
        assert [item["seq"] for item in events] == list(range(1, len(events) + 1))
        assert sum(len(item["payload"]["entries"]) for item in events if item["kind"] == "scan_batch") == 123
        assert all(len(item["payload"]["entries"]) <= 40 for item in events if item["kind"] == "scan_batch")
        await app.close()
        app = await setup(tmp_path)
        restored = (await call(app, "chat.scan.page", {"id": cid, "scan_id": scan_id, "offset": 100}))["result"]
        assert restored == page and (await call(app, "chat.get", {"id": cid}))["result"]["grant"] is None
        await app.close()
    asyncio.run(run())


@pytest.mark.parametrize("operation", ["cancel", "revoke"])
def test_real_batch_cancellation_or_revoke_keeps_only_discovered_prefix(tmp_path, operation):
    async def run():
        app = await setup(tmp_path)
        root = tmp_path / "files"
        root.mkdir()
        for index in range(81):
            (root / f"item-{index}.txt").write_text("合成", encoding="utf-8")
        cid = (await create(app))["id"]
        await call(app, "chat.grant", {"id": cid, "root": str(root)})
        request = send(cid, "列出目录")
        events = []
        async def sink(value):
            events.append(value)
            if value["kind"] == "scan_batch" and value["payload"]["discovered"] == 40:
                params = {"id": cid, "request_id": request["request_id"]} if operation == "cancel" else {"id": cid}
                response = await call(app, "chat.cancel" if operation == "cancel" else "chat.revoke", params)
                assert response["ok"]
        app.chat.set_event_sink(sink)
        result = (await call(app, "chat.natural", request))["result"]
        directory = next(item for item in result["messages"] if item["kind"] == "directory_result")["data"]
        assert directory["summary"]["discovered"] <= 80 and not directory["summary"]["complete"]
        assert result["stream"]["state"] == ("cancelled" if operation == "cancel" else "completed")
        page = (await call(app, "chat.scan.page", {"id": cid, "scan_id": directory["scan_id"]}))["result"]
        assert page["total"] == directory["summary"]["discovered"]
        assert not any(value["kind"] == "model_delta" for value in events)
        await app.close()
    asyncio.run(run())


def test_empty_recursive_mixed_sensitive_and_gateway_role_rejection(tmp_path):
    async def run():
        app = await setup(tmp_path)
        cid = (await create(app))["id"]
        root = tmp_path / "files"
        root.mkdir()
        await call(app, "chat.grant", {"id": cid, "root": str(root)})
        empty = (await call(app, "chat.natural", send(cid, "列出目录")))["result"]
        assert empty["messages"][-1]["data"]["summary"]["discovered"] == 0
        (root / "nested").mkdir()
        (root / "nested" / "child.py").write_text("# 合成", encoding="utf-8")
        (root / ".env.local").write_text("SYNTHETIC=not-a-key", encoding="utf-8")
        recursive = (await call(app, "chat.natural", send(cid, "递归列出目录")))["result"]
        data = recursive["messages"][-1]["data"]
        assert data["summary"]["depth"] == 3 and data["summary"]["errors"]
        assert any(item["path"] == "nested/child.py" and item["category"] == "代码" for item in data["entries"])
        assert not any(".env" in item["path"] for item in data["entries"])
        grant = app.computer.status(cid)["grant_id"]
        with pytest.raises(ToolError, match="此角色"):
            app.computer.begin_scan("main", cid, grant)
        before = app.computer.status(cid)["calls_remaining"]
        app.computer.begin_scan("computer", cid, grant)
        assert app.computer.status(cid)["calls_remaining"] == before - 1
        app.computer.revoke(cid)
        with pytest.raises(ToolError):
            app.computer.check_scan("computer", cid, grant)
        await app.close()
    asyncio.run(run())


def test_wait_cancel_restart_and_cross_conversation_never_resume(tmp_path):
    async def run():
        app = await setup(tmp_path)
        cid, other = (await create(app))["id"], (await create(app))["id"]
        original = send(cid, "总结这份附件")
        first = (await call(app, "chat.natural", original))["result"]
        pending = continuation(cid, first["workflow"])
        assert first["workflow"]["action"] == "materials"
        assert (await call(app, "chat.continue", {**pending, "id": other}))["error"]["code"] == "STALE_CONTINUATION"
        assert (await call(app, "chat.cancel", {"id": cid, "request_id": original["request_id"]}))["result"]["cancelled"]
        assert (await call(app, "chat.continue", pending))["error"]["code"] == "STALE_CONTINUATION"
        second = send(cid, "列出目录")
        latest = (await call(app, "chat.natural", second))["result"]
        stale = continuation(cid, latest["workflow"])
        await app.close()
        app = await setup(tmp_path)
        snapshot = (await call(app, "chat.get", {"id": cid}))["result"]
        assert snapshot["workflow"] is None and snapshot["stream"]["state"] == "interrupted"
        assert (await call(app, "chat.continue", stale))["error"]["code"] == "STALE_CONTINUATION"
        assert (await call(app, "chat.natural", second))["error"]["code"] == "REQUEST_INTERRUPTED"
        await app.close()
    asyncio.run(run())


def test_material_wait_native_stream_citations_single_continue_and_removal(tmp_path):
    async def run():
        app = await setup(tmp_path)
        cid = (await create(app))["id"]
        original = send(cid, "总结这份附件")
        result = (await call(app, "chat.natural", original))["result"]
        source = await material(app, cid)
        result = (await call(app, "chat.continue", continuation(cid, result["workflow"])))["result"]
        wf = result["workflow"]
        assert wf["action"] == "synthesis" and wf["state"] == "waiting_approval"
        preview = (await call(app, "chat.synthesis.preview", {"id": cid, **wf["input"]}))["result"]
        events, calls = [], []
        async def sink(event):
            events.append(event)
        app.chat.set_event_sink(sink)
        async def stream(profile, messages, **kwargs):
            calls.append((profile, messages, kwargs))
            raw = json.dumps({"answer": "合成逐步回答。", "claims": [{"text": "须复核引用。", "kind": "fact", "citations": [preview["fragments"][0]["citation"]]}]}, ensure_ascii=False)
            for index in range(0, len(raw), 3):
                await kwargs["on_delta"](raw[index:index + 3])
                await asyncio.sleep(0)
            return Completion(raw, (), "stop", {"total_tokens": 40})
        app.chat.client.stream = stream
        generation = {"id": cid, "request_id": str(uuid4()), "revision": preview["revision"], "stream_mode": "stream", **wf["input"]}
        generated = (await call(app, "chat.synthesis.generate", generation))["result"]
        assert generated["workflow"]["request_id"] == original["request_id"] and generated["messages"][-1]["kind"] == "synthesis"
        assert "".join(event["payload"]["text"] for event in events if event["kind"] == "model_delta") == "合成逐步回答。"
        final = (await call(app, "chat.continue", continuation(cid, wf)))["result"]
        assert final["workflow"] is None and final["stream"]["request_id"] == original["request_id"]
        assert len(calls) == 1 and calls[0][0].model == "deepseek-flash"
        assert len([item for item in final["messages"] if item["kind"] == "natural_request"]) == 1
        await call(app, "chat.material.remove", {"id": cid, "kind": "document", "evidence_id": source["evidence_id"]})
        assert (await call(app, "chat.get", {"id": cid}))["result"]["materials"] == []
        assert (await call(app, "chat.document.source", {"id": cid, "evidence_id": source["evidence_id"]}))["ok"]
        quoted = (await call(app, "chat.natural", send(cid, "检索原文引用")))["result"]
        assert quoted["workflow"] is None and quoted["messages"][-1]["data"]["items"] == []
        await app.close()
    asyncio.run(run())


def test_three_materials_limit_and_removed_source_never_sent(tmp_path):
    async def run():
        app = await setup(tmp_path)
        cid = (await create(app))["id"]
        sources = [await material(app, cid, f"synthetic-{index}.pdf") for index in range(3)]
        with pytest.raises(ToolError):
            await material(app, cid, "fourth.pdf")
        assert len(await app.chat.natural.materials(cid)) == 3
        result = (await call(app, "chat.natural", send(cid, "综合这些资料回答")))["result"]
        wf = result["workflow"]
        preview = (await call(app, "chat.synthesis.preview", {"id": cid, **wf["input"]}))["result"]
        await call(app, "chat.material.remove", {"id": cid, "kind": "document", "evidence_id": sources[0]["evidence_id"]})
        denied = await call(app, "chat.synthesis.generate", {"id": cid, **wf["input"], "request_id": str(uuid4()), "revision": preview["revision"], "stream_mode": "stream"})
        assert denied["error"]["code"] == "STALE_APPROVAL"
        await app.close()
    asyncio.run(run())


def test_typed_understanding_context_compound_general_question_and_no_bare_url_fetch(tmp_path):
    async def run():
        app = await setup(tmp_path)
        cid = (await create(app))["id"]
        requests = []
        async def stream(profile, messages, **kwargs):
            requests.append(messages)
            if "schema=" in messages[0]["content"]:
                return Completion(json.dumps({"steps": [{"kind": "answer", "query": "流式输出是什么"}]}), (), "stop", {})
            raw = '{"answer":"逐次呈现实际产生的结果。"}'
            await kwargs["on_delta"](raw[:15])
            await kwargs["on_delta"](raw[15:])
            return Completion(raw, (), "stop", {})
        app.chat.client.stream = stream
        result = (await call(app, "chat.natural", send(cid, "解释什么是流式")))["result"]
        assert result["workflow"] is None and result["messages"][-1]["kind"] == "natural_answer"
        await call(app, "chat.natural", send(cid, "讨论链接 https://example.com/reference 是什么意思"))
        assert len(requests) == 4 and not (await app.chat.evidence.list(cid))[0]
        root = tmp_path / "files"
        root.mkdir()
        await call(app, "chat.grant", {"id": cid, "root": str(root)})
        compound = (await call(app, "chat.natural", send(cid, "列出目录再统计空间")))["result"]
        assert len([item for item in compound["messages"] if item["kind"] == "directory_result"]) == 2 and len(requests) == 4
        assert obvious("读取 https://example.com 然后总结并生成Word").steps[-1].kind == "publication"
        await app.close()
    asyncio.run(run())


@pytest.mark.parametrize("purpose", ["routing", "answer"])
def test_same_model_explicit_nonstream_fallback_is_single_use(tmp_path, purpose):
    async def run():
        app = await setup(tmp_path)
        cid = (await create(app))["id"]
        calls = []
        async def stream(profile, messages, **kwargs):
            if purpose == "answer" and "schema=" in messages[0]["content"]:
                return Completion('{"steps":[{"kind":"answer","query":"合成解释"}]}', (), "stop", {})
            if kwargs.get("on_delta"):
                await kwargs["on_delta"]('{"answer":"临时')
            raise ModelUnavailable("STREAM_INCOMPLETE")
        async def complete(profile, messages, **kwargs):
            calls.append(profile)
            raw = '{"steps":[{"kind":"answer","query":"经确认的解释"}]}' if purpose == "routing" else '{"answer":"经确认的解释"}'
            return Completion(raw, (), "stop", {})
        app.chat.client.stream, app.chat.client.complete = stream, complete
        request = send(cid, "解释普通合成问题")
        first = (await call(app, "chat.natural", request))["result"]
        wf = first["workflow"]
        assert wf["action"] == "stream_fallback" and wf["input"]["purpose"] == purpose
        assert not calls and all(item["kind"] != "natural_answer" for item in first["messages"])
        confirmed = await call(app, "chat.fallback.confirm", continuation(cid, wf))
        assert confirmed["ok"], confirmed
        final = confirmed["result"]
        assert final["workflow"] is None and final["stream"]["request_id"] == request["request_id"]
        assert len(calls) == 1 and calls[0].model == "deepseek-flash"
        denied = await call(app, "chat.fallback.confirm", continuation(cid, wf))
        assert denied["error"]["code"] == "STALE_CONTINUATION" and len(calls) == 1
        await app.close()
    asyncio.run(run())


def test_missing_key_and_unsupported_task_do_not_invent_result(tmp_path):
    async def run():
        app = await setup(tmp_path)
        cid = (await create(app))["id"]
        missing = (await call(app, "chat.natural", send(cid, "解释普通问题")))["result"]
        assert missing["workflow"] is None and missing["messages"][-1]["data"]["code"] == "MISSING_CREDENTIAL"
        refused = (await call(app, "chat.natural", send(cid, "永久删除系统目录并修改注册表")))["result"]
        assert refused["messages"][-1]["data"]["code"] == "UNSUPPORTED_TASK" and refused["operation"] is None
        assert refused["stream"]["state"] == "failed"
        await app.close()
    asyncio.run(run())


@pytest.mark.parametrize("nonstream_succeeds", [True, False])
def test_m15_partial_stream_fallback_native_confirm_is_once_and_bound(tmp_path, nonstream_succeeds):
    async def run():
        app = await setup(tmp_path)
        cid = (await create(app))["id"]
        await material(app, cid)
        original = send(cid, "总结这份附件")
        first = (await call(app, "chat.natural", original))["result"]
        wf = first["workflow"]
        preview = (await call(app, "chat.synthesis.preview", {"id": cid, **wf["input"]}))["result"]
        counts = []
        async def stream(profile, messages, **kwargs):
            assert kwargs["max_tokens"] == 4096
            await kwargs["on_delta"]('{"answer":"未核验暂态')
            raise ModelUnavailable("STREAM_INCOMPLETE")
        async def complete(profile, messages, **kwargs):
            assert kwargs["max_tokens"] == 4096
            counts.append(profile)
            if not nonstream_succeeds:
                raise ModelUnavailable("NETWORK_OR_TIMEOUT")
            raw = json.dumps({"answer": "降级后完整结果", "claims": [{"text": "合成结论", "kind": "fact", "citations": [preview["fragments"][0]["citation"]]}]})
            return Completion(raw, (), "stop", {})
        app.chat.client.stream, app.chat.client.complete = stream, complete
        failed = (await call(app, "chat.synthesis.generate", {"id": cid, **wf["input"], "request_id": str(uuid4()), "revision": preview["revision"], "stream_mode": "stream"}))["result"]
        assert all(item["kind"] != "synthesis" for item in failed["messages"])
        fallback = failed["workflow"]
        assert fallback["action"] == "stream_fallback" and fallback["input"]["purpose"] == "synthesis"
        before = len(counts)
        denial = await call(app, "chat.fallback.confirm", {**continuation(cid, fallback), "continuation_id": str(uuid4())})
        assert not denial["ok"] and len(counts) == before
        blocked_generic = await call(app, "chat.fallback.confirm", continuation(cid, fallback))
        assert blocked_generic["error"]["code"] == "FALLBACK_APPROVAL_REQUIRED" and not counts
        args = {key: fallback["input"][key] for key in ("mode", "question", "sources")}
        fresh = (await call(app, "chat.synthesis.preview", {"id": cid, **args}))["result"]
        confirmed = await call(app, "chat.synthesis.generate", {"id": cid, "request_id": str(uuid4()), **args, "revision": fresh["revision"], "stream_mode": "confirmed_nonstream"})
        assert confirmed["ok"], confirmed
        final = confirmed["result"]
        if nonstream_succeeds:
            final = (await call(app, "chat.continue", continuation(cid, fallback)))["result"]
        assert final["workflow"] is None and len(counts) == 1
        if nonstream_succeeds:
            assert final["stream"]["request_id"] == original["request_id"]
        assert final["stream"]["state"] == ("completed" if nonstream_succeeds else "failed")
        assert (await call(app, "chat.fallback.confirm", continuation(cid, fallback)))["error"]["code"] == "STALE_CONTINUATION"
        assert len(counts) == 1 and all(profile.model == "deepseek-flash" for profile in counts)
        await app.close()
    asyncio.run(run())


def test_real_attachment_cancel_and_failure_do_not_resume_parent(tmp_path, monkeypatch):
    import orvia_backend.chat as chat_module
    async def run():
        app = await setup(tmp_path)
        cid = (await create(app))["id"]
        original = send(cid, "总结这份附件")
        pending = (await call(app, "chat.natural", original))["result"]
        selected = tmp_path / "synthetic.pdf"
        selected.write_bytes(b"synthetic-local-only")
        entered = asyncio.Event()
        async def held(data, suffix):
            entered.set()
            await asyncio.Event().wait()
        monkeypatch.setattr(chat_module, "extract_document", held)
        attach = asyncio.create_task(call(app, "chat.document.attach", {"id": cid, "request_id": str(uuid4()), "path": str(selected)}))
        await asyncio.wait_for(entered.wait(), 2)
        result = await call(app, "chat.cancel", {"id": cid, "request_id": original["request_id"]})
        assert result["result"]["cancelled"]
        completed = await asyncio.wait_for(attach, 2)
        assert completed["ok"] and completed["result"]["workflow"] is None and not completed["result"]["materials"]
        assert (await call(app, "chat.continue", continuation(cid, pending["workflow"])))["error"]["code"] == "STALE_CONTINUATION"
        assert selected.read_bytes() == b"synthetic-local-only"
        await app.close()
    asyncio.run(run())


def test_resource_truncation_and_oversized_depth_do_not_claim_full_scan(tmp_path, monkeypatch):
    import orvia_backend.chat.scans as scans_module
    async def run():
        app = await setup(tmp_path)
        cid = (await create(app))["id"]
        root = tmp_path / "files"
        root.mkdir()
        for index in range(7):
            (root / f"synthetic-{index}.csv").write_text("1,2", encoding="utf-8")
        await call(app, "chat.grant", {"id": cid, "root": str(root)})
        assert scans_module.MAX_VISITED == 5000 and scans_module.MAX_WORK_SECONDS == 10 and scans_module.MAX_LEDGER_BYTES == 4 * 1024 * 1024
        monkeypatch.setattr(scans_module, "MAX_VISITED", 3)
        result = (await call(app, "chat.natural", send(cid, "列出目录")))["result"]
        summary = result["messages"][-1]["data"]["summary"]
        assert summary["visited"] == 3 and summary["discovered"] == 3 and summary["truncated"] and not summary["complete"]
        deep = (await call(app, "chat.natural", send(cid, "递归列目录深度99")))["result"]
        assert deep["workflow"]["action"] == "clarification" and "最多8层" in deep["workflow"]["question"]
        await app.close()
    asyncio.run(run())


def test_scan_wall_clock_includes_sink_wait_without_visiting_next_entry(tmp_path, monkeypatch):
    import orvia_backend.chat.scans as scans_module
    from types import SimpleNamespace
    async def run():
        app = await setup(tmp_path)
        try:
            cid = (await create(app))["id"]
            root = tmp_path / "wall-clock"
            root.mkdir()
            for index in range(85):
                (root / f"synthetic-{index:03d}.txt").write_text("合成", encoding="utf-8")
            await call(app, "chat.grant", {"id": cid, "root": str(root)})
            clock, visited, batches = [0.0], [], []
            actual_scandir = scans_module.os.scandir
            class CountedEntries:
                def __init__(self, directory):
                    self.entries = actual_scandir(directory)
                def __enter__(self):
                    self.entries.__enter__()
                    return self
                def __exit__(self, *args):
                    return self.entries.__exit__(*args)
                def __next__(self):
                    entry = next(self.entries)
                    visited.append(entry.name)
                    return entry
            monkeypatch.setattr(scans_module, "os", SimpleNamespace(scandir=CountedEntries))
            monkeypatch.setattr(scans_module, "time", SimpleNamespace(monotonic=lambda: clock[0]))
            async def sink(event):
                if event["kind"] == "scan_batch":
                    batches.append(event)
                    # 可控时钟模拟真实sink背压跨过10秒，避免阻塞测试进程。
                    clock[0] = 11.0
            app.chat.set_event_sink(sink)
            final = (await call(app, "chat.natural", send(cid, "列出目录")))["result"]
            result = next(item for item in final["messages"] if item["kind"] == "directory_result")["data"]
            assert len(visited) == 40 and len(batches) == 1
            assert result["summary"]["visited"] == result["summary"]["discovered"] == 40
            assert result["summary"]["truncated"] and not result["summary"]["complete"]
            assert "含保存及流式等待" in result["summary"]["reason"]
            page = (await call(app, "chat.scan.page", {"id": cid, "scan_id": result["scan_id"]}))["result"]
            assert page["total"] == 40 and len(page["entries"]) == 40
        finally:
            await app.close()
    asyncio.run(run())


def test_unknown_route_fields_cannot_supply_approval_or_arbitrary_method(tmp_path):
    async def run():
        app = await setup(tmp_path)
        cid = (await create(app))["id"]
        async def stream(profile, messages, **kwargs):
            return Completion('{"steps":[{"kind":"list","approved":true,"method":"os.system"}]}', (), "stop", {})
        app.chat.client.stream = stream
        result = (await call(app, "chat.natural", send(cid, "为我做个特别任务")))["result"]
        assert result["workflow"] is None and result["messages"][-1]["data"]["code"] == "INVALID_ROUTING"
        assert result["grant"] is None and result["operation"] is None
        await app.close()
    asyncio.run(run())


def test_multisource_clarification_accepts_current_hash_and_rejects_other_history(tmp_path):
    async def run():
        app = await setup(tmp_path)
        cid, other = (await create(app))["id"], (await create(app))["id"]
        first = await material(app, cid, "same-name.pdf", "合成第一版")
        second = await material(app, cid, "same-name.pdf", "合成第二版")
        outsider = await material(app, other, "other.pdf", "别的会话")
        initial = (await call(app, "chat.natural", send(cid, "总结这份附件")))["result"]
        wf = initial["workflow"]
        assert wf["action"] == "clarification" and len(wf["choices"]) == 2
        rejected = await call(app, "chat.continue", continuation(cid, wf, outsider["evidence_id"]))
        assert rejected["error"]["code"] == "AMBIGUOUS_SOURCE"
        same_name = await call(app, "chat.continue", continuation(cid, wf, "same-name.pdf"))
        assert same_name["error"]["code"] == "AMBIGUOUS_SOURCE"
        selected = (await call(app, "chat.continue", continuation(cid, wf, first["evidence_id"])))["result"]
        assert selected["workflow"]["action"] == "synthesis"
        assert selected["workflow"]["input"]["sources"] == [{"kind": "document", "evidence_id": first["evidence_id"]}]
        assert second["evidence_id"] != first["evidence_id"]
        await app.close()
    asyncio.run(run())


def test_material_30mib_limit_and_bad_document_state_are_explicit(tmp_path):
    async def run():
        app = await setup(tmp_path)
        cid = (await create(app))["id"]
        for index in range(2):
            item = await material(app, cid, f"item-{index}.pdf")
            await app.chat.natural.material_added(cid, "document", item["evidence_id"], input_bytes=10 * 1024 * 1024)
        with pytest.raises(ToolError) as error:
            await app.chat.natural.check_material_budget(cid, input_bytes=11 * 1024 * 1024)
        assert error.value.code == "MATERIAL_LIMIT"
        bad = await app.chat.documents.save(cid, "bad.pdf", b"synthetic-bad", {"format": "pdf", "units": [], "total_units": 0, "truncated": False, "missing_units": [], "error": {"code": "DOCUMENT_PARSE", "message": "合成失败"}})
        await app.chat.natural.material_added(cid, "document", bad["evidence_id"], input_bytes=1)
        assert (await app.chat.natural.materials(cid))[-1]["status"] == "failed"
        await app.close()
    asyncio.run(run())


def test_total_phase_timeout_only_cancels_readonly_network_and_does_not_retry(tmp_path, monkeypatch):
    import orvia_backend.chat.coordinator as coordinator_module
    from orvia_backend.chat.routing import Route, Step
    async def run():
        app = await setup(tmp_path)
        cid = (await create(app))["id"]
        calls = []
        async def route(chat, current_cid, text, materials, history, active, **kwargs):
            assert 49 <= active["deadline"] - asyncio.get_running_loop().time() <= 50
            active["deadline"] = asyncio.get_running_loop().time() + .02
            return Route(steps=[Step(kind="read_url", url="https://example.com/synthetic")])
        async def held(url, **kwargs):
            calls.append(url)
            await asyncio.Event().wait()
        monkeypatch.setattr(coordinator_module, "understand", route)
        app.browser.read = held
        result = (await call(app, "chat.natural", send(cid, "读取 https://example.com/synthetic")))["result"]
        assert result["workflow"] is None and result["stream"]["state"] == "failed"
        assert result["messages"][-1]["data"]["code"] == "REQUEST_TIMEOUT" and len(calls) == 1
        await app.close()
    asyncio.run(run())


def test_compound_compiles_dependencies_once_and_preserves_following_targets(tmp_path):
    from orvia_backend.chat.routing import understand
    async def run():
        app = await setup(tmp_path)
        cid = (await create(app))["id"]
        active = {"model": None}
        async def forbidden(*args, **kwargs):
            raise AssertionError("明确组合不应增加模型调用")
        app.chat.client.stream = forbidden
        document = await understand(app.chat, cid, "总结这份文档，然后生成Word简报", [], [], active)
        assert [step.kind for step in document.steps] == ["material_answer", "publication"]
        metadata = obvious("列出目录中的Word与PPT文件")
        assert [step.kind for step in metadata.steps] == ["list"]
        assert obvious("解释什么是React") is None
        assert obvious("解释什么是文件夹") is None
        assert obvious("什么是管理员权限") is None
        assert obvious("总结Word附件").steps[0].kind == "material_answer"
        webpage = await understand(app.chat, cid, "读取 https://example.com/synthetic，然后总结并生成Word简报", [], [], active)
        assert [step.kind for step in webpage.steps] == ["read_url", "material_answer", "publication"]
        assert "https://example.com/synthetic" in webpage.steps[1].query
        excess = await understand(app.chat, cid, "读取 https://example.com/a，然后读取 https://example.com/b，然后读取 https://example.com/c，然后总结，然后生成Word", [], [], active)
        assert len(excess.steps) == 1 and excess.steps[0].kind == "clarify" and "超过4" in excess.steps[0].query
        await app.close()
    asyncio.run(run())


def test_saved_history_migration_is_bounded_once_and_never_reopens_original(tmp_path):
    async def run():
        app = await setup(tmp_path)
        cid = (await create(app))["id"]
        saved = []
        for index in range(5):
            value = await app.chat.documents.save(cid, f"history-{index}.pdf", f"synthetic-{index}".encode(), {
                "format": "pdf", "units": [{"number": 1, "locator": "第1页", "text": "旧合成证据", "method": "text", "confidence": None, "error": None}],
                "total_units": 1, "truncated": False, "missing_units": [], "error": None})
            saved.append(value)
        # 模拟M19数据库：没有有效资料注册表记录；迁移仅使用已保存证据版本。
        async with app.store._lock:
            await app.store._db().execute("DELETE FROM m20_materials_initialized WHERE conversation_id=?", (cid,))
        initial = (await call(app, "chat.get", {"id": cid}))["result"]
        assert {item["evidence_id"] for item in initial["materials"]} == {item["evidence_id"] for item in saved[-3:]}
        assert initial["grant"] is None
        selected = initial["materials"][0]
        await call(app, "chat.material.remove", {"id": cid, "kind": "document", "evidence_id": selected["evidence_id"]})
        await app.close()
        app = await setup(tmp_path)
        restarted = (await call(app, "chat.get", {"id": cid}))["result"]
        assert len(restarted["materials"]) == 2 and selected["evidence_id"] not in {item["evidence_id"] for item in restarted["materials"]}
        assert (await app.chat.documents.get(cid, saved[0]["evidence_id"]))["title"] == "history-0.pdf"
        # 相同证据ID不能混淆document/browser，从而绕过3份总量。
        await material(app, cid, "new.pdf")
        with pytest.raises(ToolError) as error:
            await app.chat.natural.check_material_budget(cid, kind="browser", eid=restarted["materials"][0]["evidence_id"])
        assert error.value.code == "MATERIAL_LIMIT"
        await app.close()
    asyncio.run(run())


def test_browser_fill_cannot_complete_send_without_approved_receipt_and_new_verification(tmp_path):
    async def run():
        app = await setup(tmp_path)
        cid = (await create(app))["id"]
        request = send(cid, "填写并发送消息到 https://example.com/synthetic")
        first = (await call(app, "chat.natural", request))["result"]
        wf = first["workflow"]
        rule = wf["input"]["success_rule"]
        assert rule["effect"] == "external" and rule["categories"] == ["message"] and rule["control_actions"] == ["fill"]
        repository = app.chat.automation.repository
        async def operation(action, category, evidence, *, approved=False, origin="https://example.com"):
            oid = await repository.create(cid, "browser", "a" * 64, {"action": action, "category": category, "origin": origin})
            if approved:
                await app.chat.repository.append(cid, "system", "合成原生外发批准摘要", "automation", {
                    "kind": "browser-request", "request_id": str(uuid4()), "approved": True,
                    "request_meta": {"origin": origin, "category": category, "body_sha256": evidence["request_sha256"]}})
            await repository.transition(cid, oid, ["awaiting_approval"], "completed", {"verified": True, **evidence})
            await app.chat.repository.append(cid, "system", "合成M18核验事实", "automation", {"kind": "browser", "operation_id": oid, "status": "completed", "verified": True})
        await operation("fill", "message", {"action": "fill", "control_matched": True})
        partial = await call(app, "chat.continue", continuation(cid, wf))
        assert partial["error"]["code"] == "STEP_NOT_VERIFIED"
        receipt = {"http_status": 200, "request_sha256": "b" * 64, "response_sha256": "c" * 64,
                   "expected_sha256": "d" * 64, "page_sha256": "e" * 64, "matched": True}
        await operation("click", "message", receipt)
        no_approval = await call(app, "chat.continue", continuation(cid, wf))
        assert no_approval["error"]["code"] == "STEP_NOT_VERIFIED"
        await operation("click", "message", receipt, approved=True, origin="https://other.example.com")
        wrong_site = await call(app, "chat.continue", continuation(cid, wf))
        assert wrong_site["error"]["code"] == "STEP_NOT_VERIFIED"
        await operation("click", "message", receipt, approved=True)
        complete = (await call(app, "chat.continue", continuation(cid, wf)))["result"]
        assert complete["workflow"] is None and complete["stream"]["state"] == "completed"
        await app.close()
    asyncio.run(run())


def test_desktop_compound_requires_each_new_matching_uia_operation(tmp_path):
    async def run():
        app = await setup(tmp_path)
        cid = (await create(app))["id"]
        original = send(cid, '请在桌面应用输入到控件“正文”文本“synthetic M20 desktop”，然后点击应用窗口“M18 apply”')
        first = (await call(app, "chat.natural", original))["result"]["workflow"]
        assert first["action"] == "desktop" and first["input"]["success_rule"]["action"] == "set_value"
        assert "然后点击" not in first["input"]["requirement"]
        repository = app.chat.automation.repository
        async def operation(action, *, value="", name="", verification="control_state", publish=True):
            import hashlib
            oid = await repository.create(cid, "desktop", "a" * 64, {
                "action": action, "category": "local", "target_name": name,
                "value_sha256": hashlib.sha256(value.encode()).hexdigest()})
            await repository.transition(cid, oid, ["awaiting_approval"], "completed", {"verified": True, "verification": verification})
            if publish:
                await app.chat.repository.append(cid, "system", "合成M18控件核验账本", "automation", {"kind": "desktop", "operation_id": oid, "status": "completed", "verified": True})
            return oid
        await operation("invoke", name="M18 apply", verification="ui_state_changed")
        assert (await call(app, "chat.continue", continuation(cid, first)))["error"]["code"] == "STEP_NOT_VERIFIED"
        await operation("set_value", value="wrong synthetic text")
        assert (await call(app, "chat.continue", continuation(cid, first)))["error"]["code"] == "STEP_NOT_VERIFIED"
        # 真实后台先提交completed再追加摘要；接续不能依赖尚未落盘的会话消息。
        first_oid = await operation("set_value", value="synthetic M20 desktop", publish=False)
        second = (await call(app, "chat.continue", continuation(cid, first)))["result"]["workflow"]
        assert second["action"] == "desktop" and second["request_id"] == first["request_id"] and second["continuation_id"] != first["continuation_id"]
        assert second["input"]["success_rule"]["action"] == "invoke" and second["input"]["success_rule"]["target_name"] == "M18 apply"
        assert (await call(app, "chat.continue", continuation(cid, second)))["error"]["code"] == "STEP_NOT_VERIFIED"
        # 基线之后再发旧操作摘要也不能把上一步或错误动作冒充下一步。
        await app.chat.repository.append(cid, "system", "合成旧控件摘要", "automation", {"kind": "desktop", "operation_id": first_oid, "status": "completed", "verified": True})
        await operation("set_value", value="synthetic M20 desktop")
        await operation("invoke", name="wrong synthetic button", verification="ui_state_changed")
        assert (await call(app, "chat.continue", continuation(cid, second)))["error"]["code"] == "STEP_NOT_VERIFIED"
        await operation("invoke", name="M18 apply", verification="ui_state_changed", publish=False)
        final = (await call(app, "chat.continue", continuation(cid, second)))["result"]
        assert final["workflow"] is None and final["stream"]["state"] == "completed"
        assert len([item for item in final["messages"] if item["kind"] == "natural_request"]) == 1
        await app.close()
    asyncio.run(run())


@pytest.mark.parametrize("instruction", ['请在桌面应用输入到控件“正文”文本“synthetic M20 desktop”', '请在桌面应用输入“synthetic M20 desktop”'])
def test_desktop_completed_ledger_precedes_any_summary_message(tmp_path, instruction):
    async def run():
        import hashlib
        app = await setup(tmp_path)
        try:
            cid = (await create(app))["id"]
            first = (await call(app, "chat.natural", send(cid, instruction)))["result"]["workflow"]
            assert first["input"]["success_rule"]["value_sha256"] == hashlib.sha256(b"synthetic M20 desktop").hexdigest()
            repository = app.chat.automation.repository
            oid = await repository.create(cid, "desktop", "a" * 64, {"action": "set_value", "category": "local", "target_name": "",
                "value_sha256": hashlib.sha256(b"synthetic M20 desktop").hexdigest()})
            await repository.transition(cid, oid, ["awaiting_approval"], "completed", {"verified": True, "verification": "control_state"})
            messages, _ = await app.chat.repository.messages(cid)
            assert not any(item["kind"] == "automation" for item in messages)
            final = (await call(app, "chat.continue", continuation(cid, first)))["result"]
            assert final["workflow"] is None and final["stream"]["state"] == "completed"
            assert not any(item["kind"] == "automation" for item in final["messages"])
        finally:
            await app.close()
    asyncio.run(run())


def test_fenced_code_and_quoted_value_do_not_introduce_compound_tasks(tmp_path):
    from orvia_backend.chat.routing import understand
    async def run():
        app = await setup(tmp_path)
        cid = (await create(app))["id"]
        async def forbidden(*args, **kwargs):
            raise AssertionError("明确已实现意图无需新增模型")
        app.chat.client.stream = forbidden
        code = '运行下面Python脚本\n```python\nprint("输入然后点击并发送；读取 https://example.com/data")\n# 总结，然后生成Word，然后移动，然后统计\n```'
        route = await understand(app.chat, cid, code, [], [], {"model": None})
        assert len(route.steps) == 1 and route.steps[0].kind == "script" and route.steps[0].kind_hint == "paste"
        literal = await understand(app.chat, cid, '输入到桌面控件“正文”文本“然后点击再提交”', [], [], {"model": None})
        assert len(literal.steps) == 1 and literal.steps[0].kind == "desktop"
        missing = (await call(app, "chat.natural", send(cid, '请在桌面应用输入文本')))["result"]["workflow"]
        assert missing["action"] == "desktop" and "未给确切输入文本" in missing["question"] and "不能沿用旧任务值" in missing["question"]
        assert "value_sha256" not in missing["input"]["success_rule"]
        browser = await understand(app.chat, cid, '填写并发送消息到 https://example.com/synthetic', [], [], {"model": None})
        assert len(browser.steps) == 1 and browser.steps[0].kind == "browser" and "填写并发送" in browser.steps[0].query
        await app.close()
    asyncio.run(run())


@pytest.mark.parametrize("window", ["before_event_sequence", "sink_failure"])
def test_saved_scan_prefix_recovers_history_once_without_reading_or_replaying(tmp_path, monkeypatch, window):
    import orvia_backend.chat.scans as scans_module
    async def run():
        app = await setup(tmp_path)
        cid = (await create(app))["id"]
        root = tmp_path / "synthetic-prefix"
        root.mkdir()
        for index in range(205):
            (root / f"synthetic-{index:03d}.txt").write_text("合成已发现前缀", encoding="utf-8")
        await call(app, "chat.grant", {"id": cid, "root": str(root)})
        rid = str(uuid4())
        await app.chat.repository.claim(cid, rid, "natural:列出目录")
        await app.chat.repository.append(cid, "user", "列出目录", "natural_request")
        batch_count = 0
        delivered = []
        async def sink(event):
            if window == "sink_failure" and event["kind"] == "scan_batch" and batch_count == 3:
                raise ToolError("STREAM_DISCONNECTED", "合成输出管道已断开")
            delivered.append(event)
        app.chat.set_event_sink(sink)
        await app.chat.streams.start(cid, rid)
        async def emit(kind, payload):
            nonlocal batch_count
            batch_count += 1
            page = await app.chat.scans.page(cid, payload["scan_id"])
            assert page["total"] == payload["discovered"]  # 批次确已提交。
            if window == "before_event_sequence" and batch_count == 3:
                raise ToolError("STREAM_DISCONNECTED", "合成提交后/事件seq前中断")
            await app.chat.streams.emit(cid, rid, kind, payload)
        # 使用真实scandir/SQLite/流序号，故意不进入最终历史append或请求终态，模拟崩溃窗口。
        prefix = await app.chat.scans.run(cid, rid, emit=emit)
        assert prefix["total"] == 120 and batch_count == 3
        assert not prefix["summary"]["complete"] and prefix["summary"]["truncated"]
        assert not any(event["kind"] == "completed" for event in delivered)
        last_seq = (await app.chat.streams.get(cid, rid))["last_seq"]
        assert last_seq == (3 if window == "before_event_sequence" else 4)
        messages, _ = await app.chat.repository.messages(cid)
        assert not any(item["kind"] == "directory_result" for item in messages)
        await app.close()
        app = await setup(tmp_path)
        def forbidden(*args, **kwargs):
            raise AssertionError("恢复已发现入口禁止重新读取磁盘")
        monkeypatch.setattr(scans_module.os, "scandir", forbidden)
        replies = await asyncio.gather(call(app, "chat.get", {"id": cid}), call(app, "chat.get", {"id": cid}))
        snapshot = replies[-1]["result"]
        recovered = [item for item in snapshot["messages"] if item["kind"] == "directory_result"]
        assert len(recovered) == 1 and recovered[0]["data"]["scan_id"] == prefix["scan_id"]
        assert recovered[0]["data"]["recovered"] and recovered[0]["data"]["partial"]
        assert snapshot["grant"] is None and snapshot["workflow"] is None and snapshot["stream"]["state"] == "interrupted"
        first = (await call(app, "chat.scan.page", {"id": cid, "scan_id": prefix["scan_id"], "offset": 0}))["result"]
        second = (await call(app, "chat.scan.page", {"id": cid, "scan_id": prefix["scan_id"], "offset": first["next_offset"]}))["result"]
        assert len(first["entries"]) == 100 and len(second["entries"]) == 20 and second["next_offset"] is None
        assert (await call(app, "chat.natural", {"id": cid, "request_id": rid, "text": "列出目录"}))["error"]["code"] == "REQUEST_INTERRUPTED"
        snapshot = (await call(app, "chat.get", {"id": cid}))["result"]
        assert len([item for item in snapshot["messages"] if item["kind"] == "directory_result"]) == 1
        await app.close()
        app = await setup(tmp_path)
        snapshot = (await call(app, "chat.get", {"id": cid}))["result"]
        assert len([item for item in snapshot["messages"] if item["kind"] == "directory_result"]) == 1 and snapshot["grant"] is None
        await app.close()
    asyncio.run(run())
