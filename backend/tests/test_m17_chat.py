"""M17 私有协议：固定 Computer 模型、显式上下文、逐文件写入及清理隔离。"""

import asyncio
import json
import os
import time
from uuid import uuid4

from orvia_backend.configuration.client import Completion
from test_chat import call, create, setup
from test_m15_synthesis import seed


def test_development_protocol_model_role_context_and_restart(tmp_path):
    async def run():
        app = await setup(tmp_path)
        try:
            root = tmp_path / "project"
            root.mkdir()
            (root / "App.tsx").write_text("export const Old = 1;", encoding="utf-8")
            cid = (await create(app))["id"]
            other = (await create(app))["id"]
            await call(app, "chat.grant", {"id": cid, "root": str(root)})
            context = (await call(app, "chat.development.context", {"id": cid, "requirement": "替换合成常量", "paths": ["App.tsx"]}))["result"]
            assert context["files"][0]["content"] == "export const Old = 1;"
            assert not (await call(app, "chat.development.context", {"id": cid, "requirement": "替换合成常量", "paths": ["../other.ts"]}))["ok"]
            captured = []

            async def complete(profile, messages, **kwargs):
                captured.append((profile, messages, kwargs))
                return Completion(json.dumps({"files": [{"path": "App.tsx", "content": "export const New = 2;"}]}), (), "stop", {"total_tokens": 80})

            app.chat.client.complete = complete
            request = {"id": cid, "paths": ["App.tsx"], "kind": "code", "stack": "react-vite", "requirement": "替换合成常量",
                       "context_revision": context["revision"], "request_id": str(uuid4())}
            stale = await call(app, "chat.development.generate", {**request, "context_revision": "0" * 64})
            assert stale["error"]["code"] == "STALE_APPROVAL" and not captured
            generated = (await call(app, "chat.development.generate", request))["result"]
            assert generated["files"][0]["operation"] == "modify" and generated["files"][0]["status"] == "pending"
            assert captured[0][0].role == "computer" and captured[0][0].model == "glm-5.3-flashx"
            assert captured[0][0].base_url == "https://open.bigmodel.cn/api/paas/v4"
            assert captured[0][2]["max_tokens"] == 4096
            assert "export const Old" in captured[0][1][1]["content"]
            assert (root / "App.tsx").read_text(encoding="utf-8") == "export const Old = 1;"
            assert (await call(app, "chat.development.draft", {"id": other, "draft_id": generated["draft_id"]}))["error"]["code"] == "NOT_FOUND"
            assert (await call(app, "chat.development.apply", {"id": cid, "draft_id": generated["draft_id"], "revision": "0" * 64, "index": 0}))["error"]["code"] == "STALE_APPROVAL"
            applied = (await call(app, "chat.development.apply", {"id": cid, "draft_id": generated["draft_id"], "revision": generated["revision"], "index": 0}))["result"]
            assert applied["verified"] and (root / "App.tsx").read_text(encoding="utf-8") == "export const New = 2;"
            assert (await call(app, "chat.development.generate", request))["error"]["code"] == "STALE_APPROVAL"
            await app.close()
            app = await setup(tmp_path)
            saved = (await call(app, "chat.development.draft", {"id": cid, "draft_id": generated["draft_id"]}))["result"]
            assert saved["files"][0]["status"] == "applied"
            assert (await call(app, "chat.development.apply", {"id": cid, "draft_id": generated["draft_id"], "revision": generated["revision"], "index": 0}))["error"]["code"] == "PERMISSION_DENIED"
        finally:
            await app.close()
    asyncio.run(run())


def test_cleanup_protocol_uses_only_synthetic_user_temp(tmp_path):
    async def run():
        app = await setup(tmp_path)
        try:
            local = tmp_path / "Local"
            temp = local / "Temp"
            temp.mkdir(parents=True)
            source = temp / "old.log"
            source.write_text("synthetic log", encoding="utf-8")
            stamp = time.time() - 40 * 24 * 3600
            os.utime(source, (stamp, stamp))
            app.chat.cleanup.local_base = local
            cid = (await create(app))["id"]
            other = (await create(app))["id"]
            plan = (await call(app, "chat.cleanup.scan", {"id": cid}))["result"]
            assert plan["entries"][0]["name"] == "old.log" and plan["entries"][0]["risk"] == "medium"
            assert (await call(app, "chat.cleanup.plan", {"id": other, "plan_id": plan["plan_id"]}))["error"]["code"] == "NOT_FOUND"
            assert (await call(app, "chat.cleanup.execute", {"id": cid, "plan_id": plan["plan_id"], "revision": "0" * 64, "indices": [0]}))["error"]["code"] == "STALE_APPROVAL"
            assert source.exists()
            moved = (await call(app, "chat.cleanup.execute", {"id": cid, "plan_id": plan["plan_id"], "revision": plan["revision"], "indices": [0]}))["result"]
            assert moved["entries"][0]["status"] == "moved" and moved["released_bytes"] == 0
            assert not source.exists()
            restored = (await call(app, "chat.cleanup.restore", {"id": cid, "plan_id": plan["plan_id"], "index": 0}))["result"]
            assert restored["entries"][0]["status"] == "restored" and source.exists()
        finally:
            await app.close()
    asyncio.run(run())


def test_development_selected_evidence_and_saved_result_are_conversation_scoped(tmp_path):
    async def run():
        app = await setup(tmp_path)
        try:
            cid, other = (await create(app))["id"], (await create(app))["id"]
            root = tmp_path / "synthetic-project"
            root.mkdir()
            await call(app, "chat.grant", {"id": cid, "root": str(root)})
            await call(app, "chat.grant", {"id": other, "root": str(root)})
            sources = await seed(app, cid)
            synthesis = {"answer": "合成资料存在来源冲突。", "claims": [
                {"text": "来源冲突", "kind": "conflict", "citations": []}], "citations": []}
            await app.chat.repository.append(cid, "assistant", synthesis["answer"], "synthesis", synthesis)
            messages, _ = await app.chat.repository.messages(cid)
            message_id = messages[-1]["id"]
            await app.chat.repository.append(cid, "system", "合成简报", "publication", {"message_id": message_id})
            messages, _ = await app.chat.repository.messages(cid)
            publication_id = messages[-1]["id"]
            request = {"id": cid, "requirement": "制作合成证据页面", "paths": [], "sources": sources[:2],
                       "result_message_id": publication_id}
            preview = (await call(app, "chat.development.context", request))["result"]
            assert preview["fragments"] and preview["saved_result"]["answer"] == synthesis["answer"]
            assert "不包含导出后修改" in preview["saved_result"]["note"]
            assert (await call(app, "chat.development.context", {**request, "id": other}))["error"]["code"] == "NOT_FOUND"
            assert (await call(app, "chat.development.context", {**request, "requirement": "另一需求"}))["result"]["revision"] != preview["revision"]
            captured = []
            async def complete(profile, messages, **kwargs):
                captured.append(messages[1]["content"])
                return Completion(json.dumps({"title": "合成原型", "pages": [{"id": "home", "title": "首页",
                    "body": "mock", "buttons": [], "form": None}]}), (), "stop", {})
            app.chat.client.complete = complete
            stale = await call(app, "chat.development.generate", {**request, "requirement": "另一需求",
                "kind": "prototype", "stack": "web-native", "context_revision": preview["revision"], "request_id": str(uuid4())})
            assert stale["error"]["code"] == "STALE_APPROVAL" and not captured
            result = await call(app, "chat.development.generate", {**request, "kind": "prototype",
                "stack": "web-native", "context_revision": preview["revision"], "request_id": str(uuid4())})
            assert result["ok"] and result["result"]["kind"] == "prototype"
            assert "合成计划" in captured[0] and synthesis["answer"] in captured[0]
        finally:
            await app.close()
    asyncio.run(run())
