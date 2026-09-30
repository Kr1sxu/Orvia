"""M18 Application→桌面批准→共同账本的 L2 合成/mock 测试；不代替真实 UIA 验收。"""

import asyncio
import json
from uuid import uuid4

from orvia_backend.computer.paths import ToolError
from test_chat import call, create, setup


class DesktopMock:
    def __init__(self):
        self.owners = {}
        self.hash = "1" * 64
        self.calls = []
        self.wait_for_cancel = False
        self.started = asyncio.Event()
        self.save_mode = False

    async def windows(self):
        return [{"target_id": "synthetic-target", "label": "合成应用"}]

    async def grant(self, cid, target_id):
        assert target_id == "synthetic-target"
        token = str(uuid4())
        self.owners[cid] = token
        return await self.observe(cid, token)

    async def observe(self, cid, grant_id):
        if self.owners.get(cid) != grant_id:
            raise ToolError("DESKTOP_DENIED", "合成授权不匹配")
        return {"grant_id": grant_id, "label": "合成应用", "state_hash": self.hash,
                "file_dialog": self.save_mode, "controls": [{"control_id": "synthetic-control", "name": "合成控件",
                    "patterns": ["value", "invoke", "focus"], "save_button": self.save_mode,
                    "blocked_reason": "file_dialog" if self.save_mode else None, "enabled": True, "offscreen": False}]}

    async def execute(self, cid, grant_id, control_id, action, value, expected_state_hash, cancel_event):
        assert self.owners[cid] == grant_id and expected_state_hash == self.hash
        self.calls.append((cid, action, value))
        self.started.set()
        if self.wait_for_cancel:
            await cancel_event.wait()
            return {"status": "uncertain", "verified": False, "observation": None}
        result = {"status": "completed", "verified": True, "verification": "control_state",
                  "observation": await self.observe(cid, grant_id)}
        if action == "save_new":
            result.update(file_name="synthetic.txt", sha256="2" * 64, verification="saved_copy_bytes",
                          notice="保存新副本，应用内部路径仍在私有暂存。")
        return result


async def prepare(app, mock, cid, *, action="set_value", value="合成文字"):
    granted = await call(app, "chat.automation.desktop.grant", {"id": cid, "target_id": "synthetic-target"})
    assert granted["ok"], granted
    observation = granted["result"]
    request = {"id": cid, "grant_id": observation["grant_id"], "control_id": "synthetic-control",
               "action": action, "value": value, "state_hash": observation["state_hash"], "category": "local",
               "expectation": "合成控件展示已审批值"}
    preview = await call(app, "chat.automation.desktop.preview", request)
    assert preview["ok"], preview
    plan = preview["result"]
    return request, {"id": cid, "operation_id": plan["operation_id"], "revision": plan["revision"]}


def test_application_desktop_ownership_stale_and_once_only_audit(tmp_path):
    async def run():
        app = await setup(tmp_path)
        try:
            cid = (await create(app))["id"]
            other = (await create(app))["id"]
            mock = DesktopMock(); app.chat.automation.desktop = mock
            request, approval = await prepare(app, mock, cid)
            for modified in [{**request, "state_hash": "0" * 64}, {**request, "control_id": "forged"},
                             {**request, "selected_path": "C:/forged.txt"}]:
                assert not (await call(app, "chat.automation.desktop.preview", modified))["ok"]
            assert not (await call(app, "chat.automation.desktop.execute", {**approval, "id": other}))["ok"]
            assert not (await call(app, "chat.automation.desktop.execute", {**approval, "revision": "0" * 64}))["ok"]
            assert not mock.calls
            mock.hash = "3" * 64
            assert not (await call(app, "chat.automation.desktop.execute", approval))["ok"]
            assert not mock.calls
            mock.hash = "1" * 64
            assert (await call(app, "chat.automation.desktop.execute", approval))["ok"]
            await app.chat.automation.active[approval["operation_id"]]["task"]
            assert (await call(app, "chat.automation.desktop.execute", approval))["error"]["code"] == "INVALID_STATE"
            assert len(mock.calls) == 1
            history = (await call(app, "chat.automation.history", {"id": cid}))["result"]
            assert history["operations"][0]["status"] == "completed"
            assert history["operations"][0]["audit"]["evidence"]["verified"] is True
            assert "合成文字" not in json.dumps(history, ensure_ascii=False)
            assert (await call(app, "chat.automation.history", {"id": other}))["result"]["operations"] == []
        finally:
            await app.close()
    asyncio.run(run())


def test_desktop_cancel_before_approval_and_running_uncertain_no_replay(tmp_path):
    async def run():
        app = await setup(tmp_path)
        try:
            cid = (await create(app))["id"]
            other = (await create(app))["id"]
            mock = DesktopMock(); app.chat.automation.desktop = mock
            _, approval = await prepare(app, mock, cid)
            assert (await call(app, "chat.automation.cancel", approval))["result"]["status"] == "cancelled"
            assert not (await call(app, "chat.automation.desktop.execute", approval))["ok"]
            assert not mock.calls
            _, approval = await prepare(app, mock, cid)
            mock.wait_for_cancel = True
            assert (await call(app, "chat.automation.desktop.execute", approval))["ok"]
            await asyncio.wait_for(mock.started.wait(), timeout=2)
            # 焦点是整机共享资源：第二个会话也不能趁后台执行期间另派窗口动作。
            for params in [{"id": cid}, {"id": other}]:
                blocked = await call(app, "chat.automation.desktop.windows", params)
                assert not blocked["ok"] and blocked["error"]["code"] == "INVALID_STATE"
            assert (await call(app, "chat.automation.history", {"id": other}))["ok"]
            assert not (await call(app, "chat.automation.cancel", {**approval, "id": other}))["ok"]
            assert (await call(app, "chat.automation.cancel", approval))["ok"]
            await app.chat.automation.active[approval["operation_id"]]["task"]
            fact = await app.chat.automation.repository.get(cid, approval["operation_id"])
            assert fact["status"] == "uncertain" and fact["audit"]["evidence"]["verified"] is False
            assert not (await call(app, "chat.automation.desktop.execute", approval))["ok"]
            assert len(mock.calls) == 1
        finally:
            await app.close()
    asyncio.run(run())


def test_desktop_save_requires_native_path_and_audits_copy_evidence(tmp_path):
    async def run():
        app = await setup(tmp_path)
        try:
            cid = (await create(app))["id"]
            mock = DesktopMock(); mock.save_mode = True; app.chat.automation.desktop = mock
            _, approval = await prepare(app, mock, cid, action="save_new", value="")
            assert not (await call(app, "chat.automation.desktop.execute", approval))["ok"]
            assert not mock.calls
            selected = str(tmp_path / "synthetic.txt")
            assert (await call(app, "chat.automation.desktop.execute", {**approval, "selected_path": selected}))["ok"]
            await app.chat.automation.active[approval["operation_id"]]["task"]
            fact = await app.chat.automation.repository.get(cid, approval["operation_id"])
            evidence = fact["audit"]["evidence"]
            assert evidence["file_name"] == "synthetic.txt" and evidence["sha256"] == "2" * 64
            assert evidence["verification"] == "saved_copy_bytes"
            assert selected not in json.dumps(fact)
        finally:
            await app.close()
    asyncio.run(run())


def test_desktop_restart_interrupts_without_restoring_window_authorization(tmp_path):
    async def run():
        app = await setup(tmp_path)
        cid = (await create(app))["id"]
        mock = DesktopMock(); app.chat.automation.desktop = mock
        _, approval = await prepare(app, mock, cid)
        await app.chat.automation.repository.transition(cid, approval["operation_id"], ["awaiting_approval"], "running")
        await app.close()
        app = await setup(tmp_path)
        try:
            mock = DesktopMock(); app.chat.automation.desktop = mock
            fact = (await call(app, "chat.automation.history", {"id": cid}))["result"]["operations"][0]
            assert fact["status"] == "interrupted"
            assert not (await call(app, "chat.automation.desktop.execute", approval))["ok"]
            assert not mock.owners and not mock.calls
        finally:
            await app.close()
    asyncio.run(run())
