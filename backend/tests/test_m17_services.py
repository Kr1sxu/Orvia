"""M17 合成项目与临时目录：差异、版本冲突、隔离和恢复。"""

import asyncio
import os
import time
from functools import wraps
from pathlib import Path
from uuid import uuid4

import pytest

from orvia_backend.cleanup import CleanupService
from orvia_backend.computer.contracts import GrantRequest
from orvia_backend.computer.gateway import ComputerGateway
from orvia_backend.computer.paths import ToolError
from orvia_backend.development import DevelopmentService
from orvia_backend.development.service import context_preview
from orvia_backend.storage import Store


def async_test(function):
    @wraps(function)
    def run(*args, **kwargs):
        return asyncio.run(function(*args, **kwargs))
    return run


@async_test
async def test_code_existing_file_requires_current_version_and_applies_one_file(tmp_path: Path):
    root = tmp_path / "project"
    root.mkdir()
    source = root / "src" / "App.tsx"
    source.parent.mkdir()
    source.write_text("export default function App(){return <p>old</p>}\n", encoding="utf-8")
    store = Store(tmp_path / "app.sqlite")
    await store.open()
    gateway = ComputerGateway()
    cid = str(uuid4())
    gateway.grant(GrantRequest(mission_id=cid, root=str(root)))
    service = DevelopmentService(store, gateway)
    await service.open()
    preview = context_preview(service.policy(cid), ["src/App.tsx"])
    assert preview["files"][0]["content"].strip().endswith("old</p>}")
    draft = await service.create(cid, "code", {"files": [
        {"path": "src/App.tsx", "content": "export default function App(){return <p>new</p>}\n"},
        {"path": "src/main.tsx", "content": "import App from './App';\n"},
    ]})
    assert draft["files"][0]["operation"] == "modify" and "-export" in draft["files"][0]["diff"]
    source.write_text("user edit\n", encoding="utf-8")
    with pytest.raises(ToolError, match="CODE_CHANGED"):
        await service.apply(cid, draft["draft_id"], draft["revision"], 0)
    assert source.read_text(encoding="utf-8") == "user edit\n"
    result = await service.apply(cid, draft["draft_id"], draft["revision"], 1)
    assert result["verified"] and result["remaining"] == 1
    assert (root / "src" / "main.tsx").read_text(encoding="utf-8").strip() == "import App from './App';"
    with pytest.raises(ToolError, match="CODE_ALREADY_APPLIED"):
        await service.apply(cid, draft["draft_id"], draft["revision"], 1)
    with pytest.raises(ToolError, match="NOT_FOUND"):
        await service.get(str(uuid4()), draft["draft_id"])
    await store.close()


@async_test
async def test_prototype_is_bounded_and_escapes_model_text(tmp_path: Path):
    root = tmp_path / "project"
    root.mkdir()
    store = Store(tmp_path / "app.sqlite")
    await store.open()
    gateway = ComputerGateway()
    cid = str(uuid4())
    gateway.grant(GrantRequest(mission_id=cid, root=str(root)))
    service = DevelopmentService(store, gateway)
    await service.open()
    spec = {"title": "合成演示", "pages": [
        {"id": "home", "title": "首页", "body": "<script>alert(1)</script>", "buttons": [{"label": "下一页", "target": "detail"}], "form": None},
        {"id": "detail", "title": "详情", "body": "仅演示", "buttons": [{"label": "返回", "target": "home"}], "form": {"label": "姓名", "success": "已记录"}},
    ]}
    draft = await service.create(cid, "prototype", spec, "web-native")
    assert {item["path"] for item in draft["files"]} == {"index.html", "style.css", "app.js"}
    assert "&lt;script&gt;" in draft["files"][0]["content"]
    assert "<script>alert(1)</script>" not in draft["files"][0]["content"]
    for item in draft["files"]:
        await service.apply(cid, draft["draft_id"], draft["revision"], item["index"])
    assert (root / "index.html").exists() and (root / "app.js").exists()
    with pytest.raises(ToolError):
        await service.create(cid, "code", {"files": [{"path": "../escape.ts", "content": "x"}]})
    await store.close()


def _old(path: Path, content: bytes):
    path.write_bytes(content)
    stamp = time.time() - 40 * 24 * 3600
    os.utime(path, (stamp, stamp))


@async_test
async def test_cleanup_whitelist_conflict_quarantine_and_restore(tmp_path: Path):
    local = tmp_path / "Local"
    temp = local / "Temp"
    temp.mkdir(parents=True)
    _old(temp / "old.tmp", b"disposable")
    _old(temp / "notes.txt", b"must stay")
    (temp / "young.log").write_text("current", encoding="utf-8")
    store = Store(tmp_path / "app.sqlite")
    await store.open()
    cid = str(uuid4())
    service = CleanupService(store, local)
    await service.open()
    plan = await service.scan(cid)
    assert [item["name"] for item in plan["entries"]] == ["old.tmp"]
    assert plan["released_bytes"] == 0 and plan["logical_bytes"] == len(b"disposable")
    (temp / "old.tmp").write_bytes(b"changed")
    partial = await service.execute(cid, plan["plan_id"], plan["revision"], [0])
    assert partial["entries"][0]["status"] == "skipped"
    assert (temp / "old.tmp").read_bytes() == b"changed"
    _old(temp / "old.tmp", b"disposable")
    fresh = await service.scan(cid)
    complete = await service.execute(cid, fresh["plan_id"], fresh["revision"], [0])
    assert complete["status"] == "completed" and complete["entries"][0]["status"] == "moved"
    assert complete["released_bytes"] == 0 and complete["quarantined_bytes"] == len(b"disposable")
    assert not (temp / "old.tmp").exists()
    (temp / "old.tmp").write_text("collision", encoding="utf-8")
    with pytest.raises(ToolError, match="RESTORE_CONFLICT"):
        await service.restore(cid, fresh["plan_id"], 0)
    (temp / "old.tmp").unlink()
    restored = await service.restore(cid, fresh["plan_id"], 0)
    assert restored["entries"][0]["status"] == "restored"
    assert (temp / "old.tmp").read_bytes() == b"disposable"
    assert (temp / "notes.txt").exists() and (temp / "young.log").exists()
    await store.close()


@async_test
async def test_cleanup_skips_link_and_busy_candidate(tmp_path: Path, monkeypatch):
    local = tmp_path / "Local"
    temp = local / "Temp"
    temp.mkdir(parents=True)
    _old(temp / "linked.tmp", b"shared")
    os.link(temp / "linked.tmp", temp / "second.tmp")
    _old(temp / "busy.log", b"in use")
    store = Store(tmp_path / "app.sqlite")
    await store.open()
    service = CleanupService(store, local)
    await service.open()
    monkeypatch.setattr("orvia_backend.cleanup.service._not_busy", lambda path: path.name != "busy.log")
    plan = await service.scan(str(uuid4()))
    assert plan["entries"] == []
    assert (temp / "linked.tmp").exists() and (temp / "second.tmp").exists() and (temp / "busy.log").exists()
    await store.close()
