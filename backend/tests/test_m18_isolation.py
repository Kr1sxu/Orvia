"""M18 合成 LPAC 验收：此处使用真实 Windows 令牌及私有解释器，没有模型。"""

import json
import os
from pathlib import Path
import sys
import subprocess
import threading
import time

import pytest

from orvia_backend.automation.windows_isolation import IsolationError, prepare_runtime, run_script


@pytest.fixture(scope="module")
def runtime(tmp_path_factory):
    if os.name != "nt" or sys.version_info[:2] != (3, 12):
        pytest.skip("真实 LPAC 验收需要 Windows 和固定 Python 3.12")
    return prepare_runtime(tmp_path_factory.mktemp("m18-private-runtime"))


def task(tmp_path: Path, code: str):
    directory = tmp_path / "task"
    directory.mkdir()
    (directory / "input").mkdir()
    (directory / "output").mkdir()
    (directory / "script.py").write_text(code, encoding="utf-8")
    return directory


def test_real_lpac_smoke(runtime, tmp_path):
    directory = task(tmp_path, 'from pathlib import Path\nprint("synthetic-ok")\nPath("output/result.txt").write_text("合成结果", encoding="utf-8")\n')
    result = run_script(runtime, directory, cancel_event=threading.Event())
    assert result["status"] == "completed", result
    assert result["token_verified"] and result["processes_reaped"] and result["isolation"] == "lpac"
    assert result["stdout"].strip() == "synthetic-ok"
    assert (directory / "output/result.txt").read_text(encoding="utf-8") == "合成结果"


def test_private_acl_diagnostics_only_fixed_fields(runtime):
    from orvia_backend.automation.windows_isolation import _Native
    native = _Native()
    value = native.acl_diagnostics(runtime.parent, native.user_sid())
    assert value.startswith("host-il-"), value
    assert "-owner-1-" in value and "-dac-1-own-1" in value, value
    assert str(runtime.parent) not in value and "S-1-" not in value


def test_real_lpac_private_owner_without_inherited_write_owner(runtime, tmp_path):
    import ctypes
    from ctypes import wintypes as w
    from orvia_backend.automation.windows_isolation import _Native
    native = _Native()
    user = native.user_sid()
    descriptor = w.LPVOID()
    # 模拟 Electron profile：当前用户为 owner，有 WRITE_DAC，但 DACL 不给 WRITE_OWNER。
    native.check(native.a.ConvertStringSecurityDescriptorToSecurityDescriptorW(
        f"D:P(A;OICI;0x1701ff;;;{user})(A;OICI;FA;;;SY)", 1, ctypes.byref(descriptor), None), "fixture-dacl")
    try:
        native.check(native.a.SetFileSecurityW(str(runtime.parent), 0x4 | 0x80000000, descriptor), "fixture-dacl-set")
    finally:
        native.k.LocalFree(descriptor)
    try:
        observation = native.acl_diagnostics(runtime.parent, user)
        assert "-dac-1-own-0" in observation, observation
        directory = task(tmp_path, 'print("synthetic-owner-acl")\n')
        result = run_script(runtime, directory, cancel_event=threading.Event())
        assert result["status"] == "completed" and result["token_verified"] and result["processes_reaped"], result
        assert "-dac-1-own-1" in native.acl_diagnostics(runtime.parent, user)
    finally:
        native.protect(runtime.parent, user, stage="runtime")


def test_real_lpac_denies_outside_input_registry_network_and_environment(runtime, tmp_path, monkeypatch):
    outside = tmp_path / "synthetic-secret.txt"
    outside.write_text("SYNTHETIC_NOT_A_KEY", encoding="utf-8")
    write_target = tmp_path / "must-not-exist.txt"
    directory = task(tmp_path, f'''import json, os, winreg
from pathlib import Path
checks = {{}}
def denied(name, action):
    try:
        action()
    except OSError:
        checks[name] = True
    else:
        checks[name] = False
denied("outside_read", lambda: Path({str(outside)!r}).read_text())
denied("outside_write", lambda: Path({str(write_target)!r}).write_text("unexpected"))
denied("input_write", lambda: Path("input/sample.txt").write_text("changed"))
denied("script_write", lambda: Path("script.py").write_text("changed"))
denied("runtime_write", lambda: Path({str(runtime.parent / "python312._pth")!r}).write_text("changed"))
denied("registry_write", lambda: winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software", 0, winreg.KEY_WRITE))
try:
    import socket
except ImportError as error:
    checks["network_stack_blocked"] = "10107" in str(error)
else:
    checks["network_stack_blocked"] = False
checks["credential_absent"] = "ORVIA_SYNTHETIC_SECRET" not in os.environ
checks["input_read"] = Path("input/sample.txt").read_text() == "synthetic-input"
print(json.dumps(checks))
''')
    (directory / "input/sample.txt").write_text("synthetic-input", encoding="utf-8")
    monkeypatch.setenv("ORVIA_SYNTHETIC_SECRET", "SYNTHETIC_NOT_A_KEY")
    result = run_script(runtime, directory, cancel_event=threading.Event())
    assert result["status"] == "completed", json.dumps(result)
    checks = json.loads(result["stdout"])
    assert all(checks.values()), checks
    assert outside.read_text() == "SYNTHETIC_NOT_A_KEY" and not write_target.exists()
    assert (directory / "input/sample.txt").read_text() == "synthetic-input"


def test_real_lpac_timeout_reaps_owned_process(runtime, tmp_path):
    directory = task(tmp_path, 'import os, time\nfrom pathlib import Path\nPath("output/process.txt").write_text(str(os.getpid()))\ntime.sleep(60)\n')
    result = run_script(runtime, directory, cancel_event=threading.Event(), timeout=1)
    assert result["status"] == "timed_out", json.dumps(result)
    assert result["processes_reaped"]
    import psutil
    assert not psutil.pid_exists(int((directory / "output/process.txt").read_text()))


def test_real_lpac_cancel_and_output_budgets(runtime, tmp_path):
    directory = task(tmp_path, 'import time\nprint("started", flush=True)\ntime.sleep(60)\n')
    event = threading.Event()
    timer = threading.Timer(1, event.set)
    timer.start()
    try:
        result = run_script(runtime, directory, cancel_event=event)
    finally:
        timer.cancel()
    assert result["status"] == "cancelled" and result["processes_reaped"], result
    (directory / "script.py").write_text('print("x" * 20000)\n', encoding="utf-8")
    result = run_script(runtime, directory, cancel_event=threading.Event())
    assert result["status"] == "output_limit" and len(result["stdout"].encode()) <= 16 * 1024
    (directory / "script.py").write_text('from pathlib import Path\nPath("output/large.txt").write_bytes(b"x" * (3 * 1024 * 1024))\n', encoding="utf-8")
    result = run_script(runtime, directory, cancel_event=threading.Event())
    assert result["status"] == "output_limit" and result["processes_reaped"]


def test_runtime_source_and_modified_copy_are_rejected(runtime, tmp_path):
    with pytest.raises(IsolationError):
        prepare_runtime(tmp_path, tmp_path / "custom.exe")
    manifest = runtime.parent / "orvia-runtime.json"
    original = manifest.read_bytes()
    manifest.write_text("{}", encoding="utf-8")
    try:
        directory = task(tmp_path, 'print("must-not-run")\n')
        with pytest.raises(IsolationError):
            run_script(runtime, directory, cancel_event=threading.Event())
    finally:
        manifest.write_bytes(original)


def test_real_lpac_process_budget(runtime, tmp_path):
    directory = task(tmp_path, '''import subprocess, sys, time, json
children=[]
blocked=False
error_code=None
for _ in range(5):
    try:
        children.append(subprocess.Popen([sys.executable,"-I","-S","-c","import time; time.sleep(60)"], creationflags=8))
    except OSError as error:
        blocked=True
        error_code=error.winerror
        break
print(json.dumps({"count":len(children), "blocked":blocked, "winerror":error_code}))
''')
    result = run_script(runtime, directory, cancel_event=threading.Event())
    assert result["status"] == "completed" and result["processes_reaped"], result
    value = json.loads(result["stdout"])
    # 本机 LPAC 常规 subprocess 在首个子进程即被系统拒绝；不冒称成功创建三个。
    assert value["blocked"] and value["winerror"] == 5 and 0 <= value["count"] <= 3


def test_real_lpac_cannot_read_canary_process(runtime, tmp_path, monkeypatch):
    import ctypes
    from ctypes import wintypes as w
    from orvia_backend.automation.windows_isolation import _Native
    # 用真实隔离进程的令牌查询本测试自有进程权限；不读取进程内存或窗口。
    previous = _Native.verify_lpac
    observation = {}
    def inspect(self, token, user, package_sid):
        valid = previous(self, token, user, package_sid)
        self._bind(self.a, "ImpersonateLoggedOnUser", [w.HANDLE], w.BOOL)
        self._bind(self.a, "RevertToSelf", [], w.BOOL)
        self._bind(self.k, "OpenProcess", [w.DWORD, w.BOOL, w.DWORD], w.HANDLE)
        duplicate = w.HANDLE()
        self.check(self.a.DuplicateToken(token, 2, ctypes.byref(duplicate)), "canary-duplicate")
        try:
            self.check(self.a.ImpersonateLoggedOnUser(duplicate), "canary-impersonation")
            try:
                handle = self.k.OpenProcess(0x410, False, os.getpid())
                observation.update({"denied": not bool(handle), "error": ctypes.get_last_error()})
                if handle:
                    self.k.CloseHandle(handle)
            finally:
                self.check(self.a.RevertToSelf(), "canary-revert")
        finally:
            self.k.CloseHandle(duplicate)
        return valid
    monkeypatch.setattr(_Native, "verify_lpac", inspect)
    directory = task(tmp_path, 'print("synthetic-canary")\n')
    result = run_script(runtime, directory, cancel_event=threading.Event())
    assert result["status"] == "completed", json.dumps(result)
    assert observation == {"denied": True, "error": 5}


def _clean_env():
    return {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "TEMP", "TMP") if key in os.environ}


def _probe_args(runtime, directory):
    return [sys.executable, "-I", "-u", "-X", "utf8", str(Path(__file__).with_name("m18_isolation_probe.py")),
            "--runtime", str(runtime), "--task", str(directory)]


def test_real_lpac_clean_product_environment(runtime, tmp_path):
    directory = task(tmp_path, 'print("synthetic-clean-environment")\n')
    process = subprocess.run(_probe_args(runtime, directory), env=_clean_env(), stdin=subprocess.DEVNULL,
                             capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    assert process.returncode == 0, process.stdout.decode("utf-8", errors="replace")
    value = json.loads(process.stdout)
    assert value["status"] == "completed" and value["token_verified"] and value["processes_reaped"]


def test_real_lpac_node_backend_launch(runtime, tmp_path):
    import shutil
    node = shutil.which("node")
    if not node:
        pytest.skip("Node 未安装；Electron 启动条件由产品 L3 覆盖")
    directory = task(tmp_path, 'print("synthetic-node-worker")\n')
    # 与 BackendClient 一致的主进程 spawn 条件，仅接收合成目录与固定白名单环境。
    program = '''const {spawn}=require('node:child_process');
const args=JSON.parse(process.argv[1]); const env=JSON.parse(process.argv[2]);
const child=spawn(args[0],args.slice(1),{shell:false,windowsHide:true,env,stdio:'pipe'});
child.stdin.end(); child.stdout.pipe(process.stdout); child.stderr.resume();
child.once('error',()=>process.exit(2)); child.once('close',code=>process.exit(code??3));'''
    process = subprocess.run([node, "-e", program, json.dumps(_probe_args(runtime, directory)), json.dumps(_clean_env())],
                             stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
    assert process.returncode == 0, process.stdout.decode("utf-8", errors="replace")
    value = json.loads(process.stdout)
    assert value["status"] == "completed" and value["token_verified"] and value["processes_reaped"]


def test_real_lpac_parent_crash_closes_job(runtime, tmp_path):
    import psutil
    directory = task(tmp_path, 'import os,time\nfrom pathlib import Path\nPath("output/process.txt").write_text(str(os.getpid()))\ntime.sleep(25)\n')
    helper = subprocess.Popen(_probe_args(runtime, directory), env=_clean_env(), stdin=subprocess.DEVNULL,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    child = None
    try:
        marker = directory / "output/process.txt"
        deadline = time.monotonic() + 15
        while not marker.exists() and helper.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        assert marker.exists(), "合成 LPAC 未启动"
        child = psutil.Process(int(marker.read_text()))
        assert Path(child.exe()).resolve() == runtime.resolve()
        created_at = child.create_time()
        helper.kill()
        helper.wait(timeout=5)
        deadline = time.monotonic() + 5
        while child.is_running() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not child.is_running(), "父进程异常退出没有回收 Job"
    finally:
        if helper.poll() is None:
            helper.kill()
            helper.wait(timeout=5)
        if child and child.is_running() and Path(child.exe()).resolve() == runtime.resolve() and child.create_time() == created_at:
            child.kill()


def test_real_lpac_memory_budget(runtime, tmp_path):
    directory = task(tmp_path, 'try:\n    data=bytearray(700*1024*1024)\nexcept MemoryError:\n    print("memory-budget-blocked")\n')
    result = run_script(runtime, directory, cancel_event=threading.Event())
    assert result["status"] == "completed" and result["stdout"].strip() == "memory-budget-blocked", json.dumps(result)
