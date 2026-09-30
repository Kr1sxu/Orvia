"""M18 桌面权限/漂移/不确定结果测试；显式环境开关才启动自有合成 WinForms。"""

import asyncio
from copy import deepcopy
import os
import json
from pathlib import Path
import subprocess
import time
from unittest.mock import patch

import pytest

from orvia_backend.automation.desktop import DesktopAdapter
from orvia_backend.computer.paths import ToolError


def binding(executable):
    return {"hwnd": 1234, "pid": 999999, "start_ticks": "synthetic-start", "exe_path": str(executable),
            "process_name": "synthetic.exe", "class_name": "SyntheticForm", "label": "synthetic only",
            "integrity": 8192, "same_session": True, "same_user": True, "visible": True}


def snapshot(bound):
    return {"binding": bound, "active_hwnd": bound["hwnd"], "file_dialog": False, "truncated": False,
            "controls": [{"runtime_id": [1, 2], "window_hwnd": bound["hwnd"], "path": "0.1", "native_id": "input",
                          "name": "synthetic input", "control_type": "Edit", "patterns": ["value", "focus"],
                          "enabled": True, "offscreen": False, "focused": False, "value": "before", "text": None,
                          "selected": None, "toggle_state": None, "rectangle": [1, 2, 100, 20],
                          "blocked_reason": None, "save_button": False}]}


class FakeDesktop(DesktopAdapter):
    def __init__(self, executable, **kwargs):
        super().__init__(**kwargs)
        self.bound = binding(executable)
        self.snap = snapshot(self.bound)
        self.actions = []
        self.uncertain = False

    async def _worker(self, payload, cancel_event=None):
        if payload["op"] == "windows":
            return {"windows": [deepcopy(self.bound)]}
        if payload["op"] == "observe":
            return deepcopy(self.snap)
        self.actions.append(deepcopy(payload))
        if self.uncertain:
            return {"uncertain": True}
        if payload["action"] == "save_new":
            Path(payload["value"]).write_bytes(b"synthetic copy")
            self.snap["file_dialog"] = False
            self.snap["controls"][0]["blocked_reason"] = None
            return {"observation": deepcopy(self.snap)}
        self.snap["controls"][0]["value"] = payload["value"]
        return {"verified": True, "observation": deepcopy(self.snap)}


def adapter(tmp_path, **kwargs):
    executable = tmp_path / "synthetic.exe"
    executable.write_bytes(b"synthetic executable identity")
    return FakeDesktop(executable, **kwargs)


async def grant(desktop, cid="session-a"):
    windows = await desktop.windows()
    assert len(windows) == 1
    return await desktop.grant(cid, windows[0]["target_id"])


def test_session_and_grant_token_are_not_reusable(tmp_path):
    async def run():
        desktop = adapter(tmp_path)
        observed = await grant(desktop)
        assert "exe_path" not in str(observed)
        assert "runtime_id" not in str(observed)
        assert "window_hwnd" not in str(observed)
        for cid, token in [("session-b", observed["grant_id"]), ("session-a", "wrong")]:
            with pytest.raises(ToolError) as error:
                await desktop.observe(cid, token)
            assert error.value.code == "DESKTOP_DENIED"
        desktop.revoke("session-a")
        with pytest.raises(ToolError):
            await desktop.observe("session-a", observed["grant_id"])
    asyncio.run(run())


def test_step_approval_hash_stops_changed_value_and_pid_reuse(tmp_path):
    async def run():
        desktop = adapter(tmp_path)
        observed = await grant(desktop)
        control = observed["controls"][0]["control_id"]
        desktop.snap["controls"][0]["value"] = "outside modification"
        with pytest.raises(ToolError) as error:
            await desktop.execute("session-a", observed["grant_id"], control, "set_value", "after", observed["state_hash"])
        assert error.value.code == "DESKTOP_STALE"
        assert not desktop.actions
        desktop.snap["binding"]["start_ticks"] = "different-process-start"
        with pytest.raises(ToolError) as error:
            await desktop.observe("session-a", observed["grant_id"])
        assert error.value.code == "DESKTOP_TARGET_CHANGED"
    asyncio.run(run())


def test_password_file_dialog_unknown_actions_and_duplicate_controls_denied(tmp_path):
    async def run():
        desktop = adapter(tmp_path)
        observed = await grant(desktop)
        control = observed["controls"][0]["control_id"]
        for action in ["shell", "click_coordinates", "run_command"]:
            with pytest.raises(ToolError):
                await desktop.execute("session-a", observed["grant_id"], control, action, None, observed["state_hash"])
        desktop.snap["controls"][0]["blocked_reason"] = "password"
        observed = await desktop.observe("session-a", observed["grant_id"])
        with pytest.raises(ToolError):
            await desktop.execute("session-a", observed["grant_id"], control, "set_value", "ignored", observed["state_hash"])
        desktop.snap["controls"][0]["blocked_reason"] = "file_dialog"
        desktop.snap["file_dialog"] = True
        observed = await desktop.observe("session-a", observed["grant_id"])
        with pytest.raises(ToolError):
            await desktop.execute("session-a", observed["grant_id"], control, "set_value", "C:/outside.txt", observed["state_hash"])
        desktop.snap["controls"].append(deepcopy(desktop.snap["controls"][0]))
        with pytest.raises(ToolError) as error:
            await desktop.observe("session-a", observed["grant_id"])
        assert error.value.code == "DESKTOP_STALE"
        assert not desktop.actions
    asyncio.run(run())


def test_cancel_before_step_and_uncertain_action_never_replayed(tmp_path):
    async def run():
        desktop = adapter(tmp_path)
        observed = await grant(desktop)
        control = observed["controls"][0]["control_id"]
        cancelled = asyncio.Event(); cancelled.set()
        result = await desktop.execute("session-a", observed["grant_id"], control, "set_value", "after", observed["state_hash"], cancelled)
        assert result["status"] == "cancelled" and not desktop.actions
        desktop.uncertain = True
        result = await desktop.execute("session-a", observed["grant_id"], control, "set_value", "after", observed["state_hash"])
        assert result["status"] == "uncertain" and result["verified"] is False
        assert len(desktop.actions) == 1
    asyncio.run(run())


def test_focus_change_is_not_authority_and_observation_limits_fail_closed(tmp_path):
    async def run():
        desktop = adapter(tmp_path)
        observed = await grant(desktop)
        desktop.snap["controls"][0]["focused"] = True
        assert (await desktop.observe("session-a", observed["grant_id"]))["state_hash"] == observed["state_hash"]
        desktop.snap["controls"][0]["value"] = "x" * 17000
        with pytest.raises(ToolError) as error:
            await desktop.observe("session-a", observed["grant_id"])
        assert error.value.code == "DESKTOP_LIMIT"
        desktop.snap["controls"][0]["value"] = "before"
        desktop.snap["controls"] = [dict(deepcopy(desktop.snap["controls"][0]), runtime_id=[1, number]) for number in range(161)]
        with pytest.raises(ToolError) as error:
            await desktop.observe("session-a", observed["grant_id"])
        assert error.value.code == "DESKTOP_LIMIT" and not desktop.actions
    asyncio.run(run())


def test_deny_own_elevated_terminal_and_replaced_executable(tmp_path):
    async def run():
        desktop = adapter(tmp_path)
        for key, value in [("integrity", 12288), ("process_name", "powershell.exe"), ("same_session", False),
                           ("same_user", False), ("pid", os.getpid())]:
            previous = desktop.bound[key]; desktop.bound[key] = value
            assert await desktop.windows() == []
            desktop.bound[key] = previous
        for browser in ["chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "vivaldi.exe", "chromium.exe"]:
            desktop.bound["process_name"] = browser
            assert await desktop.windows() == []
        desktop.bound["process_name"] = "synthetic.exe"
        observed = await grant(desktop)
        Path(desktop.bound["exe_path"]).write_bytes(b"replaced")
        with pytest.raises(ToolError) as error:
            await desktop.observe("session-a", observed["grant_id"])
        assert error.value.code == "DESKTOP_TARGET_CHANGED"
    asyncio.run(run())


def test_save_copy_uses_private_stage_and_refuses_existing_target(tmp_path):
    async def run():
        desktop = adapter(tmp_path, staging_root=tmp_path / "stage")
        desktop.snap["file_dialog"] = True
        desktop.snap["controls"][0].update(save_button=True, blocked_reason="file_dialog")
        observed = await grant(desktop)
        control = observed["controls"][0]["control_id"]
        target = tmp_path / "chosen.txt"
        target.write_bytes(b"pre-existing user data")
        with pytest.raises(ToolError):
            await desktop.execute("session-a", observed["grant_id"], control, "save_new", str(target), observed["state_hash"])
        assert not desktop.actions and target.read_bytes() == b"pre-existing user data"
        target = tmp_path / "new-copy.txt"
        result = await desktop.execute("session-a", observed["grant_id"], control, "save_new", str(target), observed["state_hash"])
        assert result["verified"] and target.read_bytes() == b"synthetic copy"
        assert Path(desktop.actions[0]["value"]).parent == tmp_path / "stage"
        assert desktop.actions[0]["value"] != str(target)
        assert str(tmp_path) not in str(result)
    asyncio.run(run())


@pytest.mark.skipif(os.name != "nt" or os.environ.get("ORVIA_M18_REAL_DESKTOP") != "1",
                    reason="explicit synthetic real desktop test only")
def test_real_uia_synthetic_window(tmp_path):
    """真实 UIA 对自有 fixture 点击/输入/焦点/保存核验；不代表任意应用兼容。"""
    root = Path(__file__).resolve().parents[2]
    script = root / "tests/e2e/m18_desktop_fixture.ps1"
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    subprocess.run([str(powershell), "-NoProfile", "-NonInteractive", "-File", str(script),
                    "-OutputDirectory", str(tmp_path), "-PrepareOnly"], check=True, capture_output=True, timeout=20)
    title = "Orvia M18 synthetic desktop validation"
    fixture = subprocess.Popen([str(tmp_path / "m18_desktop_fixture.exe"), title], env={
        key: value for key, value in os.environ.items() if key.upper() in {"SYSTEMROOT", "WINDIR", "TEMP", "TMP"}})

    class FixtureDesktop(DesktopAdapter):
        async def _worker(self, payload, cancel_event=None):
            if payload["op"] == "windows":
                payload = {**payload, "filter_pid": fixture.pid}
            try:
                return await super()._worker(payload, cancel_event)
            except ToolError as error:
                if payload["op"] == "act" and error.code == "DESKTOP_STALE":
                    fresh = await super()._worker({"op": "observe", "binding": payload["binding"]})
                    (tmp_path / "synthetic-stale-diagnostic.json").write_text(json.dumps({"expected": payload["expected_snapshot"], "fresh": fresh}, ensure_ascii=False), encoding="utf-8")
                raise

    async def run():
        desktop = FixtureDesktop(staging_root=tmp_path / "stage", timeout=12)
        windows = []
        for _ in range(5):
            windows = await desktop.windows()
            if windows:
                break
            await asyncio.sleep(0.2)
        assert len(windows) == 1 and windows[0]["identity"]["pid"] == fixture.pid
        observed = await desktop.grant("synthetic-session", windows[0]["target_id"])
        assert "SYNTHETIC-DO-NOT-EXPOSE" not in str(observed)

        async def action(name, kind, value=None):
            nonlocal observed
            if name == "M18 synthetic input":
                matches = [row for row in observed["controls"] if row["control_type"] == "Edit" and "value" in row["patterns"]]
            else:
                matches = [row for row in observed["controls"] if row["name"] == name]
            assert len(matches) == 1, [(row["name"], row["control_type"]) for row in observed["controls"]]
            result = await desktop.execute("synthetic-session", observed["grant_id"], matches[0]["control_id"], kind, value, observed["state_hash"])
            assert result["verified"], result
            observed = result["observation"]
            return result

        # 独立自有原生确认窗口夺取焦点后关闭，不能污染目标窗口审批摘要。
        approval = subprocess.Popen([str(tmp_path / "m18_desktop_fixture.exe"), "--confirmation"], env={
            key: value for key, value in os.environ.items() if key.upper() in {"SYSTEMROOT", "WINDIR", "TEMP", "TMP"}})
        try:
            await asyncio.sleep(0.6)
            fresh = await desktop.observe("synthetic-session", observed["grant_id"])
            assert fresh["state_hash"] == observed["state_hash"]
        finally:
            approval.terminate()
            approval.wait(timeout=5)
        await action("M18 synthetic input", "set_value", "synthetic desktop output")
        await action("M18 synthetic input", "focus")
        await action("M18 apply", "invoke")
        assert any(row["name"] == "APPLIED:synthetic desktop output" for row in observed["controls"])
        await action("M18 synthetic toggle", "toggle")
        # 真实 SelectionItem 由应用 provider 决定；fixture 所支持的能力必须实际读回。
        radio = next(row for row in observed["controls"] if row["name"] == "M18 synthetic radio")
        assert "select" in radio["patterns"]
        await action("M18 synthetic radio", "select")
        opened = await action("M18 open save dialog", "invoke")
        # Invoke 回执可能早于异步保存框稳定；仅刷新观察，不重复写入动作。
        for _ in range(4):
            if observed["file_dialog"]:
                break
            await asyncio.sleep(0.2)
            observed = await desktop.observe("synthetic-session", observed["grant_id"])
        if not observed["file_dialog"]:
            (tmp_path / "synthetic-dialog-diagnostic.json").write_text(json.dumps(observed, ensure_ascii=False), encoding="utf-8")
        assert observed["file_dialog"]
        save = [row for row in observed["controls"] if row.get("save_button")]
        assert len(save) == 1
        target = tmp_path / "verified-copy.txt"
        result = await desktop.execute("synthetic-session", observed["grant_id"], save[0]["control_id"], "save_new", str(target), observed["state_hash"])
        assert result["verified"] and target.read_text(encoding="utf-8") == "synthetic desktop output"
        assert result["verification"] == "saved_copy_bytes"

        # 实际启动的仅为自有 helper；开始时取消要回收它并保留目标应用，绝不重发动作。
        cancelled = asyncio.Event()
        created = []
        original_create = asyncio.create_subprocess_exec

        async def capture_helper(*args, **kwargs):
            process = await original_create(*args, **kwargs)
            created.append(process)
            cancelled.set()
            return process

        with patch("orvia_backend.automation.desktop.asyncio.create_subprocess_exec", capture_helper):
            cancellation = await desktop._worker({"op": "act", "binding": desktop._grants["synthetic-session"]["binding"],
                                                  "action": "focus"}, cancelled)
        assert cancellation["uncertain"] and len(created) == 1 and created[0].returncode is not None
        assert fixture.poll() is None

    try:
        time.sleep(0.3)
        asyncio.run(run())
    finally:
        fixture.terminate()
        fixture.wait(timeout=5)
