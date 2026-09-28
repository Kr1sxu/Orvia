from pathlib import Path
from types import SimpleNamespace

import pytest

from orvia_backend.computer.system import SystemTools, SystemToolError


def test_detect_runtimes_fixed_paths(monkeypatch, tmp_path: Path):
    root = tmp_path / "Windows"
    pf = tmp_path / "Program Files"
    ps = pf / "PowerShell" / "7" / "pwsh.exe"
    ps.parent.mkdir(parents=True)
    ps.write_text("")
    monkeypatch.setenv("SystemRoot", str(root))
    monkeypatch.setenv("ProgramFiles", str(pf))
    tools = SystemTools()
    result = tools.detect_runtimes()
    item = next(x for x in result["data"] if x["runtime"] == "powershell")
    assert item["available"] and item["path"] == str(ps)


def test_run_template_rejects_arbitrary():
    with pytest.raises(SystemToolError) as exc:
        SystemTools().run_template("exec", "powershell")
    assert exc.value.code == "UNSUPPORTED_TEMPLATE"


def test_run_template_mock(monkeypatch):
    tools = SystemTools()
    monkeypatch.setattr(tools, "detect_runtimes", lambda: {"data": [{"runtime": "powershell", "available": True, "path": "pwsh.exe"}]})
    monkeypatch.setattr(tools, "_spawn", lambda argv, timeout=3: SimpleNamespace(stdout="7.5.0\n", stderr="", returncode=0))
    result = tools.run_template("runtime_version")
    assert result["complete"] is True
    assert result["data"]["version"] == "7.5.0"


def test_run_template_rejects_distribution():
    with pytest.raises(SystemToolError) as exc:
        SystemTools().run_template("runtime_version", "wsl", "Ubuntu")
    assert exc.value.code == "UNSUPPORTED"


def test_list_processes_mock(monkeypatch):
    class P:
        def __init__(self, pid, name): self.info = {"pid": pid, "name": name}
    monkeypatch.setattr("orvia_backend.computer.system.psutil", SimpleNamespace(process_iter=lambda fields: iter([P(1, "One"), P(2, "Two")]), AccessDenied=PermissionError, NoSuchProcess=ProcessLookupError))
    result = SystemTools().list_processes("two")
    assert result["data"] == [{"pid": 2, "name": "Two"}]


def test_list_processes_limit_is_partial(monkeypatch):
    class P:
        def __init__(self, pid): self.info = {"pid": pid, "name": "p"}
    monkeypatch.setattr("orvia_backend.computer.system.psutil", SimpleNamespace(process_iter=lambda fields: iter([P(1), P(2)]), AccessDenied=PermissionError, NoSuchProcess=ProcessLookupError))
    result = SystemTools().list_processes(limit=1)
    assert result["truncated"] is True and result["complete"] is False
