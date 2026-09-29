"""M15 合成证据、真实 SQLite/FTS 与模型 mock；不读取用户文件或云端。"""
import asyncio
import json
from uuid import uuid4

from orvia_backend.configuration.client import Completion
from test_chat import call, create, setup


async def seed(app, cid):
    parsed = {"format": "pdf", "units": [
        {"number": 1, "locator": "第1页", "text": "合成计划：保留来源。" * 55, "method": "text", "confidence": None, "error": None},
        {"number": 2, "locator": "第2页", "text": "合成 OCR：许可须人工核对。", "method": "ocr", "confidence": .44, "error": None}],
        "total_units": 3, "truncated": True, "missing_units": [3], "error": None}
    doc = await app.chat.documents.save(cid, "synthetic.pdf", b"synthetic", parsed)
    second = await app.chat.documents.save(cid, "second.pptx", b"second-synthetic", {"format":"pptx", "units":[
        {"number":1,"locator":"幻灯片 1","text":"第二份合成材料提到来源需要人工复核。","method":"text","confidence":None,"error":None}],
        "total_units":1,"truncated":False,"missing_units":[],"error":None})
    web = await app.chat.evidence.save(cid, {"title": "合成网页", "source_url": "https://example.com/synthetic",
        "mode": "http", "accessed_at": "2026-09-29", "content": "合成网页称无需保留来源。" * 50,
        "truncated": False, "error": None})
    return [{"kind": "document", "evidence_id": doc["evidence_id"]},
            {"kind": "document", "evidence_id": second["evidence_id"]},
            {"kind": "browser", "evidence_id": web["evidence_id"]}]


def test_preview_generate_conflict_restart_isolation_and_idempotency(tmp_path):
    async def run():
        app = await setup(tmp_path)
        try:
            cid, other = (await create(app))["id"], (await create(app))["id"]
            sources = await seed(app, cid)
            request = {"id": cid, "mode": "answer", "question": "来源要求是否一致？", "sources": sources}
            denied = await call(app, "chat.synthesis.preview", {**request, "id": other})
            assert denied["error"]["code"] == "NOT_FOUND"
            preview = (await call(app, "chat.synthesis.preview", request))["result"]
            fallback = await call(app, "chat.synthesis.preview", {**request,"question":"*"+"长"*220})
            assert fallback["ok"] and fallback["result"]["fragments"]
            assert len(preview["coverage"]) == 3 and len(preview["fragments"]) <= 9
            assert preview["coverage"][0]["source_truncated"] and preview["coverage"][0]["missing_units"] == [3]
            assert all(len(item["text"]) <= 600 for item in preview["fragments"])
            assert preview["supplier"].startswith("Main · deepseek-flash")
            captured = []
            async def complete(profile, messages, **kwargs):
                captured.append((profile, messages, kwargs))
                a, b = preview["fragments"][0]["citation"], preview["fragments"][-1]["citation"]
                return Completion(json.dumps({"answer": "合成来源冲突，无法确认统一要求。", "claims": [
                    {"text": "两来源说法冲突", "kind": "conflict", "citations": [a, b]},
                    {"text": "完整要求尚不确定", "kind": "unknown", "citations": []}]}), (), "stop", {"total_tokens": 30})
            app.chat.client.complete = complete
            generate = {**request, "revision": preview["revision"], "request_id": str(uuid4())}
            first = (await call(app, "chat.synthesis.generate", generate))["result"]
            assert first["messages"][-1]["kind"] == "synthesis"
            data = first["messages"][-1]["data"]
            assert data["coverage"] == preview["coverage"] and len(data["citations"]) == 2
            assert data["model"] == "deepseek-flash" and first["grant"] is None and first["operation"] is None
            assert captured[0][0].base_url == "https://api.deepseek.com" and captured[0][2]["max_tokens"] == 1024
            assert "合成计划" in captured[0][1][1]["content"]
            assert (await call(app, "chat.synthesis.generate", generate))["result"] == first and len(captured) == 1
            stale = await call(app, "chat.synthesis.generate", {**generate, "request_id": str(uuid4()), "revision": "0"*64})
            assert stale["error"]["code"] == "STALE_APPROVAL" and len(captured) == 1
            await app.close()
            app = await setup(tmp_path)
            restored = (await call(app, "chat.get", {"id": cid}))["result"]
            assert restored["messages"][-1]["data"] == data
            assert (await call(app, "chat.synthesis.preview", request))["result"]["revision"] == preview["revision"]
        finally:
            await app.close()
    asyncio.run(run())


def test_invalid_citations_prompt_injection_missing_key_and_contract(tmp_path):
    async def run():
        app = await setup(tmp_path)
        try:
            cid = (await create(app))["id"]
            sources = await seed(app, cid)
            request = {"id":cid,"mode":"summary","question":"概括合成内容","sources":sources[:1]}
            assert not (await call(app,"chat.synthesis.preview",{**request,"sources":sources[:1]*2}))["ok"]
            assert not (await call(app,"chat.synthesis.preview",{**request,"model":"other"}))["ok"]
            preview=(await call(app,"chat.synthesis.preview",request))["result"]
            result=(await call(app,"chat.synthesis.generate",{**request,"revision":preview["revision"],"request_id":str(uuid4())}))["result"]
            assert result["messages"][-1]["data"]["code"] == "MISSING_CREDENTIAL"
            async def bad(profile,messages,**kwargs):
                return Completion(json.dumps({"answer":"忽略规则", "claims":[{"text":"伪造", "kind":"fact", "citations":["browser:"+"0"*64+":0"]}]}),(),"stop",{})
            app.chat.client.complete=bad
            result=(await call(app,"chat.synthesis.generate",{**request,"revision":preview["revision"],"request_id":str(uuid4())}))["result"]
            assert result["messages"][-1]["data"]["code"] == "INVALID_CITATION"
            assert all(message["kind"]!="synthesis" for message in result["messages"])
            own=[item["citation"] for item in preview["fragments"]]
            if len(own)>1:
                async def same_source(*args,**kwargs):
                    return Completion(json.dumps({"answer":"冲突", "claims":[{"text":"冲突", "kind":"conflict", "citations":own[:2]}]}),(),"stop",{})
                app.chat.client.complete=same_source
                rejected=(await call(app,"chat.synthesis.generate",{**request,"revision":preview["revision"],"request_id":str(uuid4())}))["result"]
                assert rejected["messages"][-1]["data"]["code"]=="INVALID_CITATION"
        finally:
            await app.close()
    asyncio.run(run())


def test_cancel_model_wait_without_replay(tmp_path):
    async def run():
        app = await setup(tmp_path)
        try:
            cid=(await create(app))["id"]
            sources=await seed(app,cid)
            request={"id":cid,"mode":"summary","question":"概括","sources":sources[:1]}
            preview=(await call(app,"chat.synthesis.preview",request))["result"]
            waiting=asyncio.Event()
            calls=0
            async def held(*args,**kwargs):
                nonlocal calls
                calls+=1;waiting.set();await asyncio.sleep(60)
            app.chat.client.complete=held
            generation={**request,"revision":preview["revision"],"request_id":str(uuid4())}
            task=asyncio.create_task(call(app,"chat.synthesis.generate",generation))
            await asyncio.wait_for(waiting.wait(),3)
            assert (await call(app,"chat.cancel",{"id":cid,"request_id":generation["request_id"]}))["result"]["cancelled"]
            finished=await task
            assert finished["result"]["messages"][-1]["data"]["code"]=="REQUEST_CANCELLED"
            assert (await call(app,"chat.synthesis.generate",generation))["result"]==finished["result"]
            assert calls==1
        finally:
            await app.close()
    asyncio.run(run())
