"""M18 共同账本/私有协议：合成数据，执行器 mock 不代表 LPAC 能力。"""
import asyncio
import json
from uuid import uuid4

from orvia_backend.computer.paths import ToolError
from orvia_backend.configuration.client import Completion, ModelUnavailable
from test_chat import call, create, setup


def test_script_preview_copy_export_once_and_restart(tmp_path):
    async def run():
        app = await setup(tmp_path)
        count = []
        try:
            cid = (await create(app))["id"]
            other = (await create(app))["id"]
            root = tmp_path / "synthetic"
            root.mkdir()
            (root / "input.txt").write_text("synthetic input", encoding="utf-8")
            await call(app, "chat.grant", {"id": cid, "root": str(root)})

            def mock_runner(task_root, **kwargs):
                count.append(1)
                assert (task_root / "input/input.txt").read_text() == "synthetic input"
                (task_root / "output/result.txt").write_text("synthetic output", encoding="utf-8")
                return dict(status="completed", exit_code=0, stdout="mock", stderr="", token_verified=True, processes_reaped=True)

            app.chat.automation.scripts.runner = mock_runner
            p = {"id": cid, "source": "print('synthetic')", "inputs": ["input.txt"]}
            preview = (await call(app, "chat.automation.script.preview", p))["result"]
            assert preview["plan"]["inputs"][0]["bytes"] == 15 and not count
            oid, revision = preview["operation_id"], preview["revision"]
            execute = {"id": cid, "operation_id": oid, "revision": revision}
            assert (await call(app, "chat.automation.script.execute", {**execute, "revision": "0"*64}))["error"]["code"] == "STALE_APPROVAL"
            assert (await call(app, "chat.automation.script.execute", {**execute, "id": other}))["error"]["code"] == "M18_AUTH_EXPIRED"
            assert not count
            # 审批后原输入变化不影响只读复制，真实目录不会交给执行器。
            (root / "input.txt").write_text("user changed", encoding="utf-8")
            assert (await call(app, "chat.automation.script.execute", execute))["ok"]
            await app.chat.automation.scripts.tasks[oid]
            fact = (await call(app, "chat.automation.script.status", {"id": cid, "operation_id": oid}))["result"]
            assert fact["status"] == "completed" and len(count) == 1
            assert (await call(app, "chat.automation.script.execute", execute))["error"]["code"] == "INVALID_STATE"
            target = root / "result.txt"
            export = {**execute, "index": 0, "path": str(target)}
            # 模拟元数据检查后、真正取回字节前变化；不得回传并误报旧哈希。
            original_outputs = app.chat.automation.scripts._outputs
            def change_after_validation(task_root):
                result = original_outputs(task_root)
                (task_root / "output/result.txt").write_text("race replacement", encoding="utf-8")
                return result
            app.chat.automation.scripts._outputs = change_after_validation
            assert (await call(app, "chat.automation.script.export", export))["error"]["code"] == "STALE_APPROVAL"
            assert not target.exists()
            app.chat.automation.scripts._outputs = original_outputs
            (app.chat.automation.scripts.live[oid]["root"] / "output/result.txt").write_text("synthetic output", encoding="utf-8")
            assert (await call(app, "chat.automation.script.export", export))["result"]["verified"]
            assert target.read_text() == "synthetic output"
            assert (await call(app, "chat.automation.script.export", export))["error"]["code"] == "INVALID_STATE"
            # SQLite审计只留摘要，不写正文或任务复制的完整路径。
            history = (await call(app, "chat.automation.history", {"id": cid}))["result"]
            assert "print('synthetic')" not in json.dumps(history) and "synthetic output" not in json.dumps(history)
            await app.close()
            app = await setup(tmp_path)
            assert (await call(app, "chat.automation.script.status", {"id": cid, "operation_id": oid}))["result"]["live"] is False
            assert (await call(app, "chat.automation.script.execute", execute))["error"]["code"] == "M18_AUTH_EXPIRED"
        finally:
            await app.close()
    asyncio.run(run())


def test_script_denied_inputs_tamper_and_isolation_failure(tmp_path):
    async def run():
        app = await setup(tmp_path)
        try:
            cid = (await create(app))["id"]
            root = tmp_path / "synthetic"
            root.mkdir()
            (root / "input.txt").write_text("synthetic", encoding="utf-8")
            (root / ".env.local").write_text("synthetic-only", encoding="utf-8")
            await call(app, "chat.grant", {"id": cid, "root": str(root)})
            for inputs in [["../escape"], [".env.local"], ["input.txt", "INPUT.txt"], ["input.txt","./input.txt"]]:
                assert not (await call(app, "chat.automation.script.preview", {"id": cid, "source": "pass", "inputs": inputs}))["ok"]
            assert not (await call(app, "chat.automation.script.preview", {"id": cid, "source": "invalid!", "inputs": []}))["ok"]
            assert (await call(app,"chat.automation.history",{"id":cid}))["result"]["operations"] == []
            preview = (await call(app, "chat.automation.script.preview", {"id": cid, "source": "pass", "inputs": ["input.txt"]}))["result"]
            execute = {"id": cid, "operation_id": preview["operation_id"], "revision": preview["revision"]}
            active = app.chat.automation.scripts.live[preview["operation_id"]]
            (active["root"] / "input/input.txt").write_text("tampered", encoding="utf-8")
            assert (await call(app, "chat.automation.script.execute", execute))["error"]["code"] == "STALE_APPROVAL"
            preview = (await call(app, "chat.automation.script.preview", {"id": cid, "source": "pass", "inputs": []}))["result"]
            execute = {"id": cid, "operation_id": preview["operation_id"], "revision": preview["revision"]}
            app.chat.automation.scripts.runner = lambda *a, **k: dict(status="completed", exit_code=0, token_verified=False, processes_reaped=True)
            assert (await call(app, "chat.automation.script.execute", execute))["ok"]
            await app.chat.automation.scripts.tasks[preview["operation_id"]]
            fact = await app.chat.automation.scripts.get(cid,preview["operation_id"])
            assert fact["status"] == "failed" and fact["audit"]["evidence"]["code"] == "M18_ISOLATION_UNAVAILABLE"
            assert (await call(app, "chat.automation.script.preview", {"id": cid, "source": "pass", "inputs": [], "approved": True}))["error"]["code"] == "INVALID_PARAMS"
        finally:
            await app.close()
    asyncio.run(run())


def test_script_output_directory_scan_has_budget_before_expansion(tmp_path):
    async def run():
        app = await setup(tmp_path)
        try:
            cid = (await create(app))["id"]
            preview = (await call(app,"chat.automation.script.preview",dict(id=cid,source="pass",inputs=[])))["result"]
            oid = preview["operation_id"]
            output = app.chat.automation.scripts.live[oid]["root"] / "output"
            for index in range(513):
                (output / f"synthetic-{index}").mkdir()
            app.chat.automation.scripts.runner = lambda *a, **k: dict(status="completed",exit_code=0,token_verified=True,processes_reaped=True)
            assert (await call(app,"chat.automation.script.execute",dict(id=cid,operation_id=oid,revision=preview["revision"])))["ok"]
            await app.chat.automation.scripts.tasks[oid]
            fact = await app.chat.automation.scripts.get(cid,oid)
            assert fact["status"] == "failed" and fact["audit"]["evidence"]["code"] == "M18_OUTPUT_LIMIT"
        finally:
            await app.close()
    asyncio.run(run())


def test_model_draft_fixed_computer_no_execution_and_no_replay(tmp_path):
    async def run():
        app = await setup(tmp_path)
        try:
            cid = (await create(app))["id"]
            calls = []
            async def mock_complete(profile, messages, **kwargs):
                calls.append(profile)
                assert profile.role == "computer" and profile.model == "glm-5.3-flashx"
                assert profile.base_url == "https://open.bigmodel.cn/api/paas/v4"
                assert kwargs["max_tokens"] == 4096 and messages[1]["content"] == "合成测试需求"
                return Completion('{"source":"print(123)"}', (), "stop", {})
            app.chat.client.complete = mock_complete
            preview = (await call(app, "chat.automation.script.model_preview", {"id": cid, "requirement": "合成测试需求"}))["result"]
            generate = {"id": cid, "requirement": "合成测试需求", "revision": preview["revision"], "request_id": str(uuid4())}
            assert (await call(app, "chat.automation.script.model_generate", generate))["result"]["plan"]["origin"] == "model"
            assert len(calls) == 1 and not app.chat.automation.scripts.tasks
            assert (await call(app, "chat.automation.script.model_generate", generate))["error"]["code"] == "CONFLICT"
            conversation = (await call(app, "chat.get", {"id": cid}))["result"]
            assert conversation["messages"][-1]["kind"] == "automation"
            async def unavailable(*args, **kwargs): raise ModelUnavailable("MISSING_CREDENTIAL")
            app.chat.client.complete = unavailable
            missing = await call(app, "chat.automation.script.model_generate", {**generate,"request_id":str(uuid4())})
            assert missing["error"]["code"] == "MISSING_CREDENTIAL" and not app.chat.automation.scripts.tasks
        finally:
            await app.close()
    asyncio.run(run())


class BrowserMock:
    def __init__(self):
        self.observation = dict(session_id="synthetic-session", title="synthetic", url="https://synthetic.example/", controls=[dict(control_id="synthetic-control", name="submit")], state_hash="1"*64)
        self.actions = 0
        self.verified = False
    async def observe(self, *args): return self.observation
    async def start_action(self, *args, **kwargs):
        self.actions += 1
        return {"started": True}
    async def pending(self, *args): return dict(status="response_received", pending_request=None, result=dict(status="response_received", verified=False), observation=self.observation)
    async def verify_result(self, cid, sid, expected):
        assert expected == "合成新结果"
        return dict(status="verified" if self.verified else "awaiting_verification", verified=self.verified)
    async def close_all(self): pass

    async def approve_request(self, cid, sid, request_id, revision, approved):
        return dict(status="approved" if approved else "rejected", request_meta=dict(
            method="POST",url="https://synthetic.example/private/path?value=synthetic-secret",body_bytes=12,
            body_sha256="2"*64,url_sha256="3"*64,category="message",body_preview_complete=False,
            fields_truncated=True,file_count=1,fields=[{"name":"private","value":"synthetic-secret"}],
            files=[{"path":"synthetic/private/file"}],headers={"Authorization":"synthetic-secret"}))


def test_browser_request_audit_omits_body_paths_headers_and_query(tmp_path):
    async def run():
        app = await setup(tmp_path)
        try:
            cid = (await create(app))["id"]
            app.chat.automation.browser = BrowserMock()
            response = await call(app,"chat.automation.browser.request",dict(id=cid,session_id="synthetic-session",request_id="synthetic-request",revision="4"*64,approved=False))
            assert response["ok"]
            saved = (await call(app,"chat.get",{"id":cid}))["result"]["messages"][-1]
            meta = saved["data"]["request_meta"]
            assert meta["origin"] == "https://synthetic.example" and meta["method"] == "POST"
            assert meta["body_sha256"] == "2"*64 and meta["file_count"] == 1
            serial = json.dumps(saved)
            assert "synthetic-secret" not in serial and "/private/path" not in serial
            assert "headers" not in meta and "fields" not in meta and "files" not in meta and "url" not in meta
        finally:
            await app.close()
    asyncio.run(run())


def test_browser_http_receipt_never_completes_without_readback(tmp_path):
    async def run():
        app = await setup(tmp_path)
        try:
            cid = (await create(app))["id"]
            mock = BrowserMock()
            app.chat.automation.browser = mock
            p = dict(id=cid, session_id="synthetic-session", control_id="synthetic-control", action="click", value="", state_hash="1"*64, category="transaction", expectation="合成新结果")
            preview = (await call(app, "chat.automation.browser.preview", p))["result"]
            execute = {"id": cid, "operation_id": preview["operation_id"], "revision": preview["revision"]}
            assert (await call(app, "chat.automation.browser.execute", execute))["ok"]
            assert (await call(app, "chat.automation.browser.execute", execute))["error"]["code"] == "INVALID_STATE" and mock.actions == 1
            await call(app, "chat.automation.browser.pending", {"id": cid, "session_id": "synthetic-session"})
            assert (await app.chat.automation.repository.get(cid,preview["operation_id"]))["status"] == "awaiting_verification"
            mock.verified = True
            await call(app, "chat.automation.browser.pending", {"id": cid, "session_id": "synthetic-session"})
            assert (await app.chat.automation.repository.get(cid,preview["operation_id"]))["status"] == "completed"
            cancelled = await call(app, "chat.automation.cancel", execute)
            assert cancelled["result"]["status"] == "completed"  # 终态不能被取消改写。
        finally:
            await app.close()
    asyncio.run(run())
