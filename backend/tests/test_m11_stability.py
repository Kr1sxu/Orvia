"""M11 合成目录、临时数据库与故障注入，不访问真实模型或用户文件。"""
import asyncio
import errno
import io
import json
import sqlite3
from uuid import uuid4

import pytest

from test_chat import call, setup, create, FakeModel
from orvia_backend.configuration.client import ModelUnavailable
from orvia_backend import server


def test_cancel_active_model_is_terminal_and_not_replayed(tmp_path):
    async def scenario():
        app = await setup(tmp_path)
        started = asyncio.Event()
        class WaitingModel:
            calls = 0
            async def complete(self, *args, **kwargs):
                self.calls += 1
                started.set()
                await asyncio.Event().wait()
        model = WaitingModel()
        cid = (await create(app))["id"]
        root = tmp_path / "synthetic"
        root.mkdir()
        await call(app, "chat.grant", {"id": cid, "root": str(root)})
        app.chat.client = model
        request = {"id": cid, "request_id": str(uuid4()), "text": "合成规划"}
        try:
            sending = asyncio.create_task(call(app, "chat.send", request))
            await asyncio.wait_for(started.wait(), 2)
            assert (await call(app, "chat.list"))["result"]["conversations"][0]["status"] == "running"
            assert (await call(app, "chat.cancel", {"id": cid, "request_id": str(uuid4())}))["result"] == {"cancelled": False}
            cancel = {k: request[k] for k in ("id", "request_id")}
            assert (await call(app, "chat.cancel", cancel))["result"] == {"cancelled": True}
            result = (await asyncio.wait_for(sending, 2))["result"]
            assert result["status"] == "cancelled"
            assert result["messages"][-1]["data"]["code"] == "REQUEST_CANCELLED"
            assert (await call(app, "chat.cancel", cancel))["result"] == {"cancelled": False}
            assert (await call(app, "chat.send", request))["result"] == result
            assert model.calls == 1
        finally:
            await app.close()
        app = await setup(tmp_path)
        try:
            app.chat.client = model
            restored = (await call(app, "chat.send", request))["result"]
            assert restored["status"] == "cancelled" and restored["grant"] is None
            assert model.calls == 1
        finally:
            await app.close()
    asyncio.run(scenario())


@pytest.mark.parametrize("error,code", [(ModelUnavailable("network detail must stay private"), "MODEL_UNAVAILABLE"), (TimeoutError("private endpoint"), "MODEL_TIMEOUT")])
def test_model_faults_are_terminal_and_sanitized(tmp_path, error, code):
    async def scenario():
        app = await setup(tmp_path)
        class BrokenModel:
            calls = 0
            async def complete(self, *args, **kwargs):
                self.calls += 1
                raise error
        try:
            cid = (await create(app))["id"]
            root = tmp_path / "synthetic"
            root.mkdir()
            await call(app, "chat.grant", {"id": cid, "root": str(root)})
            app.chat.client = model = BrokenModel()
            request = {"id": cid, "request_id": str(uuid4()), "text": "合成规划"}
            result = (await call(app, "chat.send", request))["result"]
            assert result["status"] == "failed"
            assert result["messages"][-1]["data"]["code"] == code
            assert "private" not in json.dumps(result)
            await call(app, "chat.send", request)
            assert model.calls == 1
        finally:
            await app.close()
    asyncio.run(scenario())


@pytest.mark.parametrize("kind,expected", [("busy", "STORAGE_BUSY"), ("full", "STORAGE_FULL"), ("db", "STORAGE_UNAVAILABLE"), ("disk", "STORAGE_FULL"), ("permission", "PERMISSION_DENIED")])
def test_storage_fault_mapping_never_leaks_detail(tmp_path, kind, expected):
    async def scenario():
        app = await setup(tmp_path)
        errors = {"busy": sqlite3.OperationalError("private db"), "full": sqlite3.OperationalError("private db"),
                  "db": sqlite3.DatabaseError("private db"), "disk": OSError(errno.ENOSPC, "private path"), "permission": PermissionError(errno.EACCES, "private path")}
        errors["busy"].sqlite_errorcode = sqlite3.SQLITE_BUSY
        errors["full"].sqlite_errorcode = sqlite3.SQLITE_FULL
        async def broken():
            raise errors[kind]
        app.chat.repository.list = broken
        try:
            result = await call(app, "chat.list")
            assert result["error"]["code"] == expected
            assert "private" not in json.dumps(result)
            assert (await call(app, "health"))["ok"]
        finally:
            await app.close()
    asyncio.run(scenario())


def test_stdio_cancel_bypasses_serial_send_but_ordinary_requests_stay_ordered(monkeypatch):
    events = []
    class FakeApplication:
        def __init__(self, event_sink=None):
            self.release = asyncio.Event()
        async def handle(self, line):
            request = json.loads(line)
            method = request["method"]
            if method == "chat.send":
                events.append("send-start")
                await self.release.wait()
                events.append("send-end")
            elif method == "chat.cancel":
                events.append("cancel")
                self.release.set()
            else:
                events.append(method)
            return {"id": request["id"], "ok": True}
        async def close(self):
            events.append("close")
    monkeypatch.setattr(server, "Application", FakeApplication)
    frames = [json.dumps({"id": str(i), "method": method}).encode() + b"\n" for i, method in enumerate(["initialize", "chat.send", "chat.approve", "chat.cancel"])]
    output = io.BytesIO()
    asyncio.run(asyncio.wait_for(server.serve(io.BytesIO(b"".join(frames)), output), 2))
    assert events == ["initialize", "send-start", "cancel", "send-end", "chat.approve", "close"]
    assert len(output.getvalue().splitlines()) == 4


def test_cancel_refused_during_plan_persistence_and_approval(tmp_path):
    async def scenario():
        app = await setup(tmp_path)
        root = tmp_path / "synthetic"
        root.mkdir()
        (root / "a.txt").write_text("synthetic")
        cid = (await create(app))["id"]
        await call(app, "chat.grant", {"id": cid, "root": str(root)})
        app.chat.client = FakeModel([{"kind": "inspect", "tool": "list_directory", "arguments": {}}, {"kind": "plan", "actions": [{"kind": "rename", "source": "a.txt", "destination": "b.txt"}]}])
        entered, release = asyncio.Event(), asyncio.Event()
        original = app.graph.start
        async def slow_plan(*args):
            entered.set()
            await release.wait()
            return await original(*args)
        app.graph.start = slow_plan
        request = {"id": cid, "request_id": str(uuid4()), "text": "合成重命名"}
        try:
            sending = asyncio.create_task(call(app, "chat.send", request))
            await asyncio.wait_for(entered.wait(), 2)
            assert (await call(app, "chat.cancel", {k: request[k] for k in ("id", "request_id")}))["result"] == {"cancelled": False}
            release.set()
            result = (await sending)["result"]
            assert result["status"] == "awaiting_approval"
            assert len(result["operations"]) == 1 and not result["operation"]["can_undo"]
            operation = result["operation"]
            approved = (await call(app, "chat.approve", {"id": cid, "operation_id": operation["operation_id"], "revision": operation["revision"]}))["result"]
            assert approved["operation"]["can_undo"]
            assert (await call(app, "chat.cancel", {k: request[k] for k in ("id", "request_id")}))["result"] == {"cancelled": False}
            assert (root / "b.txt").exists()
        finally:
            release.set()
            await app.close()
    asyncio.run(scenario())


def test_history_is_bounded_and_old_plans_are_never_undoable(tmp_path):
    async def scenario():
        app = await setup(tmp_path)
        root = tmp_path / "synthetic"
        root.mkdir()
        (root / "a.txt").write_text("synthetic")
        cid = (await create(app))["id"]
        await call(app, "chat.grant", {"id": cid, "root": str(root)})
        try:
            for index in range(11):
                app.chat.client = FakeModel([{"kind": "inspect", "tool": "list_directory", "arguments": {}}, {"kind": "plan", "actions": [{"kind": "rename", "source": "a.txt", "destination": f"b{index}.txt"}]}])
                result = await call(app, "chat.send", {"id": cid, "request_id": str(uuid4()), "text": "合成规划"})
                assert result["ok"]
            snapshot = result["result"]
            assert len(snapshot["operations"]) == 10 and snapshot["operations_truncated"]
            assert all(not row["can_undo"] for row in snapshot["operations"])
            assert all("root" not in row and "actions" not in row for row in snapshot["operations"])
            assert len(json.dumps(snapshot).encode()) < 46 * 1024
        finally:
            await app.close()
    asyncio.run(scenario())


def test_checkpoint_init_failure_does_not_publish_partial_application(tmp_path, monkeypatch):
    from orvia_backend.agents.graph import MissionGraph
    from orvia_backend.application import Application
    original = MissionGraph.__aenter__
    async def broken(self):
        await original(self)
        raise sqlite3.OperationalError("private checkpoint")
    async def scenario():
        app = Application()
        await call(app, "hello")
        params = {"data_directory": str(tmp_path / "db"), "credentials": {}}
        monkeypatch.setattr(MissionGraph, "__aenter__", broken)
        result = await call(app, "initialize", params)
        assert result["error"]["code"] == "STORAGE_UNAVAILABLE"
        assert app.store is None and app.chat is None and app.graph is None
        assert (await call(app, "chat.list"))["error"]["code"] == "NOT_INITIALIZED"
        monkeypatch.setattr(MissionGraph, "__aenter__", original)
        assert (await call(app, "initialize", params))["ok"]
        await app.close()
    asyncio.run(scenario())


def test_later_approval_and_undo_supersede_failed_request_status(tmp_path):
    async def scenario():
        app = await setup(tmp_path)
        root = tmp_path / "synthetic"
        root.mkdir()
        (root / "a.txt").write_text("synthetic")
        cid = (await create(app))["id"]
        await call(app, "chat.grant", {"id": cid, "root": str(root)})
        app.chat.client = FakeModel([{"kind": "inspect", "tool": "list_directory", "arguments": {}}, {"kind": "plan", "actions": [{"kind": "rename", "source": "a.txt", "destination": "b.txt"}]}, {"kind": "invalid"}])
        try:
            planned = (await call(app, "chat.send", {"id": cid, "request_id": str(uuid4()), "text": "合成规划"}))["result"]
            failed = (await call(app, "chat.send", {"id": cid, "request_id": str(uuid4()), "text": "合成错误"}))["result"]
            assert failed["status"] == "failed"
            operation = planned["operation"]
            approval = {"id": cid, "operation_id": operation["operation_id"], "revision": operation["revision"]}
            assert (await call(app, "chat.approve", approval))["result"]["status"] == "completed"
            assert (await call(app, "chat.undo", approval))["result"]["status"] == "undone"
            assert (await call(app, "chat.grant", {"id": cid, "root": str(root)}))["result"]["status"] == "undone"
            assert (await call(app, "chat.list"))["result"]["conversations"][0]["status"] == "undone"
        finally:
            await app.close()
    asyncio.run(scenario())


def test_stdio_runtime_error_and_broken_output_are_sanitized(monkeypatch):
    class BrokenApplication:
        closed = False
        def __init__(self, event_sink=None):
            pass
        async def handle(self, line):
            raise RuntimeError("private provider and path")
        async def close(self):
            BrokenApplication.closed = True
    monkeypatch.setattr(server, "Application", BrokenApplication)
    frame = b'{"id":"x","method":"chat.send"}\n'
    output = io.BytesIO()
    asyncio.run(server.serve(io.BytesIO(frame), output))
    result = json.loads(output.getvalue())
    assert result["error"]["code"] == "INTERNAL_ERROR"
    assert "private" not in output.getvalue().decode()
    assert BrokenApplication.closed
    class BrokenWriter:
        def write(self, value):
            raise BrokenPipeError("private pipe")
    asyncio.run(server.serve(io.BytesIO(frame), BrokenWriter()))
