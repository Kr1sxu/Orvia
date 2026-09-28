"""M10 使用临时数据库、合成文件和模型 mock 验证会话与授权闭环。"""

import asyncio
import json
from uuid import uuid4

import pytest

from orvia_backend.application import Application
from orvia_backend.configuration.client import Completion


async def call(app, method, params=None):
    return await app.handle(json.dumps({"v": 1, "id": str(uuid4()), "method": method, "params": params or {}}).encode())


async def setup(tmp_path):
    app = Application()
    await call(app, "hello")
    assert (await call(app, "initialize", {"data_directory": str(tmp_path / "db"), "credentials": {}}))["ok"]
    return app


async def create(app):
    return (await call(app, "chat.create", {"client_request_id": str(uuid4()), "title": "合成文件整理"}))["result"]


class FakeModel:
    def __init__(self, proposals):
        self.proposals = iter(proposals)
        self.calls = 0

    async def complete(self, profile, messages, **kwargs):
        self.calls += 1
        assert profile.model == "deepseek-flash"
        return Completion(json.dumps(next(self.proposals)), (), "stop", {})


def test_chat_persistence_idempotency_and_restart_grant(tmp_path):
    async def scenario():
        app = await setup(tmp_path)
        root = tmp_path / "files"
        root.mkdir()
        (root / "a.txt").write_text("synthetic", encoding="utf-8")
        try:
            request = {"client_request_id": str(uuid4()), "title": "合成文件整理"}
            first = (await call(app, "chat.create", request))["result"]
            assert (await call(app, "chat.create", request))["result"] == first
            cid = first["id"]
            await call(app, "chat.grant", {"id": cid, "root": str(root)})
            result = await call(app, "chat.inspect", {"id": cid, "tool": "list_directory", "arguments": {}})
            assert result["ok"]
            assert result["result"]["messages"][-1]["kind"] == "scan"
            denied = await call(app, "chat.inspect", {"id": cid, "tool": "get_file_metadata", "arguments": {"path": "../other"}})
            assert denied["error"]["code"] == "path_denied"
            denied = await call(app, "chat.inspect", {"id": cid, "tool": "read_text_file", "arguments": {"path": "a.txt"}})
            assert denied["error"]["code"] == "INVALID_PARAMS"
        finally:
            await app.close()
        app = await setup(tmp_path)
        try:
            restored = (await call(app, "chat.get", {"id": cid}))["result"]
            assert restored["grant"] is None
            assert restored["messages"]
            assert (await call(app, "chat.list"))["result"]["conversations"][0]["id"] == cid
        finally:
            await app.close()
    asyncio.run(scenario())


def test_chat_mock_plan_approval_undo_and_ownership(tmp_path):
    async def scenario():
        app = await setup(tmp_path)
        root = tmp_path / "files"
        root.mkdir()
        (root / "a.txt").write_text("synthetic", encoding="utf-8")
        try:
            cid = (await create(app))["id"]
            await call(app, "chat.grant", {"id": cid, "root": str(root)})
            fake = FakeModel([{"kind": "inspect", "tool": "list_directory", "arguments": {}},
                              {"kind": "plan", "actions": [{"kind": "rename", "source": "a.txt", "destination": "b.txt"}]}])
            app.chat.client = fake
            send = {"id": cid, "request_id": str(uuid4()), "text": "请将 a.txt 重命名为 b.txt"}
            response = await call(app, "chat.send", send)
            assert response["ok"], response
            snapshot = response["result"]
            assert snapshot["operation"]["status"] == "planned"
            saved_plan = snapshot["messages"][-1]["data"]
            assert saved_plan["operation_id"] == snapshot["operation"]["operation_id"]
            assert saved_plan["revision"] == snapshot["operation"]["revision"]
            assert saved_plan["status"] == "planned"
            assert saved_plan["actions"] == [{"kind": "rename", "source": "a.txt", "destination": "b.txt"}]
            assert "source_identity" not in json.dumps(saved_plan)
            assert "root" not in saved_plan
            assert len(json.dumps(saved_plan).encode()) < 12 * 1024
            assert (root / "a.txt").exists()
            assert (await call(app, "chat.send", send))["result"] == snapshot
            assert fake.calls == 2
            assert (await call(app, "chat.send", {**send, "text": "不同内容"}))["error"]["code"] == "CONFLICT"
            operation = snapshot["operation"]
            approval = {"id": cid, "operation_id": operation["operation_id"], "revision": operation["revision"]}
            other = (await create(app))["id"]
            assert (await call(app, "chat.approve", {**approval, "id": other}))["error"]["code"] == "STALE_APPROVAL"
            assert (await call(app, "chat.approve", {**approval, "revision": "0" * 64}))["error"]["code"] == "STALE_APPROVAL"
            approved = (await call(app, "chat.approve", approval))["result"]
            assert approved["operation"]["status"] == "completed"
            evidence = approved["messages"][-1]["data"]
            assert evidence["status"] == "completed" and evidence["completed"] == 1
            assert evidence["verify"] == {"complete": True, "checks": [{"sequence": 0, "destination_exists": True, "source_absent": True}]}
            assert "root" not in evidence and "error" not in evidence
            assert (root / "b.txt").exists()
            assert (await call(app, "chat.approve", approval))["ok"] is False
            undone = (await call(app, "chat.undo", approval))["result"]
            assert undone["operation"]["status"] == "undone"
            assert undone["messages"][-1]["text"].startswith("已撤销")
            assert undone["messages"][-1]["data"]["undone"] == 1
            assert (root / "a.txt").exists()
        finally:
            await app.close()
    asyncio.run(scenario())


def test_chat_missing_key_and_no_grant_are_explicit(tmp_path):
    async def scenario():
        app = await setup(tmp_path)
        root = tmp_path / "files"
        root.mkdir()
        try:
            cid = (await create(app))["id"]
            no_grant = await call(app, "chat.send", {"id": cid, "request_id": str(uuid4()), "text": "扫描"})
            assert "授权" in no_grant["result"]["messages"][-1]["text"]
            await call(app, "chat.grant", {"id": cid, "root": str(root)})
            missing = await call(app, "chat.send", {"id": cid, "request_id": str(uuid4()), "text": "扫描"})
            assert missing["result"]["messages"][-1]["data"]["code"] == "MISSING_CREDENTIAL"
        finally:
            await app.close()
    asyncio.run(scenario())


def test_chat_superseded_and_restart_approvals_refused(tmp_path):
    async def scenario():
        root = tmp_path / "files"
        root.mkdir()
        (root / "a.txt").write_text("synthetic", encoding="utf-8")
        app = await setup(tmp_path)
        try:
            cid = (await create(app))["id"]
            await call(app, "chat.grant", {"id": cid, "root": str(root)})
            await call(app, "chat.inspect", {"id": cid, "tool": "list_directory", "arguments": {}})
            app.chat.client = FakeModel([{"kind": "plan", "actions": [{"kind": "rename", "source": "a.txt", "destination": name}]} for name in ("b.txt", "c.txt")])
            old = None
            for _ in range(2):
                snapshot = (await call(app, "chat.send", {"id": cid, "request_id": str(uuid4()), "text": "生成计划"}))["result"]
                op = snapshot["operation"]
                approval = {"id": cid, "operation_id": op["operation_id"], "revision": op["revision"]}
                if old is None:
                    old = approval
            assert (await call(app, "chat.approve", old))["error"]["code"] == "STALE_APPROVAL"
        finally:
            await app.close()
        app = await setup(tmp_path)
        try:
            assert (await call(app, "chat.approve", approval))["error"]["code"] == "PERMISSION_DENIED"
            await call(app, "chat.grant", {"id": cid, "root": str(root)})
            assert (await call(app, "chat.approve", approval))["result"]["operation"]["status"] == "completed"
        finally:
            await app.close()
    asyncio.run(scenario())


@pytest.mark.parametrize("proposal", [{"kind": "inspect", "tool": "read_text_file", "arguments": {"path": "a.txt"}},
                                      {"kind": "plan", "actions": [{"kind": "rename", "source": "a.txt", "destination": "b.txt"}]},
                                      {"kind": "answer", "text": "raw-sensitive-marker", "execute": True}])
def test_chat_rejects_invalid_model_proposals(tmp_path, proposal):
    async def scenario():
        app = await setup(tmp_path)
        root = tmp_path / "files"
        root.mkdir()
        try:
            cid = (await create(app))["id"]
            await call(app, "chat.grant", {"id": cid, "root": str(root)})
            app.chat.client = FakeModel([proposal])
            result = (await call(app, "chat.send", {"id": cid, "request_id": str(uuid4()), "text": "合成需求"}))["result"]
            assert result["messages"][-1]["kind"] == "error"
            assert "raw-sensitive-marker" not in json.dumps(result)
            assert result["operation"] is None
        finally:
            await app.close()
    asyncio.run(scenario())


def test_chat_bounded_history_and_model_calls(tmp_path):
    async def scenario():
        app = await setup(tmp_path)
        root = tmp_path / "files"
        root.mkdir()
        try:
            cid = (await create(app))["id"]
            await call(app, "chat.grant", {"id": cid, "root": str(root)})
            fake = FakeModel([{"kind": "inspect", "tool": "list_directory", "arguments": {}}] * 3)
            app.chat.client = fake
            await call(app, "chat.send", {"id": cid, "request_id": str(uuid4()), "text": "合成需求"})
            assert fake.calls == 3
            for _ in range(40):
                await app.chat.repository.append(cid, "assistant", "合成" * 1000)
            result = (await call(app, "chat.get", {"id": cid}))["result"]
            assert result["messages_truncated"] is True
            assert len(json.dumps(result, ensure_ascii=False).encode()) < 48 * 1024
            assert len(result["messages"]) < 30
        finally:
            await app.close()
    asyncio.run(scenario())


def test_chat_recovery_requires_same_authorized_root(tmp_path):
    async def scenario():
        app = await setup(tmp_path)
        root = tmp_path / "files"
        root.mkdir()
        wrong_root = tmp_path / "other"
        wrong_root.mkdir()
        (root / "a.txt").write_text("synthetic", encoding="utf-8")
        try:
            cid = (await create(app))["id"]
            await call(app, "chat.grant", {"id": cid, "root": str(root)})
            app.chat.client = FakeModel([{"kind": "inspect", "tool": "list_directory", "arguments": {}},
                                         {"kind": "plan", "actions": [{"kind": "rename", "source": "a.txt", "destination": "b.txt"}]}])
            result = (await call(app, "chat.send", {"id": cid, "request_id": str(uuid4()), "text": "合成重命名"}))["result"]
            operation = result["operation"]
            approval = {"id": cid, "operation_id": operation["operation_id"], "revision": operation["revision"]}
            await app.store.update_operation(operation["operation_id"], "interrupted")
            await call(app, "chat.grant", {"id": cid, "root": str(wrong_root)})
            assert (await call(app, "chat.resume", approval))["error"]["code"] == "PERMISSION_DENIED"
            await call(app, "chat.grant", {"id": cid, "root": str(root)})
            assert (await call(app, "chat.resume", approval))["result"]["operation"]["status"] == "completed"
            assert (root / "b.txt").exists()
        finally:
            await app.close()
    asyncio.run(scenario())


def test_chat_concurrent_replay_and_persistent_request_budget(tmp_path):
    async def scenario():
        app = await setup(tmp_path)
        root = tmp_path / "files"
        root.mkdir()
        try:
            cid = (await create(app))["id"]
            await call(app, "chat.grant", {"id": cid, "root": str(root)})
            fake = FakeModel([{"kind": "answer", "text": "合成建议"}])
            app.chat.client = fake
            request = {"id": cid, "request_id": str(uuid4()), "text": "合成请求"}
            responses = await asyncio.gather(call(app, "chat.send", request), call(app, "chat.send", request))
            assert all(response["ok"] for response in responses)
            assert fake.calls == 1
            for _ in range(99):
                await app.chat.repository.claim(cid, str(uuid4()), "合成请求")
            response = await call(app, "chat.send", {**request, "request_id": str(uuid4())})
            assert response["error"]["code"] == "BUDGET_EXCEEDED"
            assert fake.calls == 1
        finally:
            await app.close()
    asyncio.run(scenario())


def test_chat_large_directory_truncates_nested_entries_and_preserves_errors(tmp_path):
    async def scenario():
        app = await setup(tmp_path)
        root = tmp_path / "files"
        root.mkdir()
        for number in range(100):
            (root / f"synthetic-file-{number:03d}.txt").write_text("synthetic", encoding="utf-8")
        (root / ".env").write_text("synthetic", encoding="utf-8")
        try:
            cid = (await create(app))["id"]
            await call(app, "chat.grant", {"id": cid, "root": str(root)})
            response = await call(app, "chat.inspect", {"id": cid, "tool": "list_directory", "arguments": {"limit": 100}})
            assert response["ok"], response
            data = response["result"]["messages"][-1]["data"]
            assert 0 < len(data["data"]["entries"]) < 100
            assert data["complete"] is False and data["truncated"] is True
            assert {"code": "sensitive_path"} in data["errors"]
            assert len(json.dumps(data, ensure_ascii=False).encode()) <= 8 * 1024
        finally:
            await app.close()
    asyncio.run(scenario())


def test_chat_snapshot_hides_replaced_root_grant(tmp_path):
    async def scenario():
        app = await setup(tmp_path)
        root = tmp_path / "files"
        root.mkdir()
        try:
            cid = (await create(app))["id"]
            granted = await call(app, "chat.grant", {"id": cid, "root": str(root)})
            assert granted["result"]["grant"] is not None
            root.rename(tmp_path / "original-files")
            root.mkdir()
            response = await call(app, "chat.get", {"id": cid})
            assert response["ok"] and response["result"]["grant"] is None
        finally:
            await app.close()
    asyncio.run(scenario())


def test_chat_interrupted_claim_reports_error_without_replaying_model(tmp_path):
    async def scenario():
        app = await setup(tmp_path)
        request_id = str(uuid4())
        try:
            cid = (await create(app))["id"]
            # 模拟进程在幂等占位落盘后、用户消息落盘前退出。
            await app.chat.repository.claim(cid, request_id, "合成请求")
            request = {"id": cid, "request_id": request_id, "text": "合成请求"}
            assert (await call(app, "chat.send", request))["error"]["code"] == "REQUEST_INTERRUPTED"
        finally:
            await app.close()
        app = await setup(tmp_path)
        try:
            fake = FakeModel([])
            app.chat.client = fake
            snapshot = (await call(app, "chat.get", {"id": cid}))["result"]
            assert snapshot["messages"][-1]["data"] == {"code": "REQUEST_INTERRUPTED", "request_id": request_id}
            assert (await call(app, "chat.send", request))["error"]["code"] == "REQUEST_INTERRUPTED"
            assert fake.calls == 0
            assert len((await app.chat.repository.messages(cid))[0]) == 1
        finally:
            await app.close()
    asyncio.run(scenario())
