"""V4-002 临时 SQLite、真实 LangGraph 和合成目录权限网关验收，不调用模型。"""

import asyncio
import copy
import json
import os
import subprocess
from uuid import uuid4

import pytest

from orvia_backend.computer.contracts import GrantRequest, ToolRequest
from orvia_backend.computer.gateway import ComputerGateway
from orvia_backend.computer.paths import ToolError
from orvia_backend.skills import SkillError, SkillsService
from orvia_backend.skills.service import _builtin, _size
from orvia_backend.skills import service as skills_module
from orvia_backend.storage import Store


async def setup(tmp_path):
    store = Store(tmp_path / "facts.sqlite")
    await store.open()
    service = SkillsService(store)
    await service.open()
    return store, service


def package(tmp_path, sid="custom", **changes):
    root = tmp_path / sid
    root.mkdir(exist_ok=True)
    manifest = copy.deepcopy(next(_builtin())[0])
    manifest.update(id=sid, **changes)
    (root / "SKILL.md").write_text("# 合成声明\n此说明不能产生权限。", encoding="utf-8")
    (root / "workflow.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return root, manifest


async def register(service, path):
    review = await service.preview_import(str(path))
    return await service.register(review["review_id"], review["revision"])


def identities():
    return str(uuid4()), str(uuid4())


async def execute(service, plan, dispatcher):
    return await service.execute(plan["plan_id"], plan["revision"], plan["mission_id"], plan["grant_id"], dispatcher)


def test_real_gateway_graph_persistence_and_single_use(tmp_path):
    async def run():
        store, service = await setup(tmp_path)
        try:
            root = tmp_path / "synthetic"
            root.mkdir()
            (root / "hello.txt").write_text("合成资料", encoding="utf-8")
            gateway = ComputerGateway()
            mission, _ = identities()
            grant = gateway.grant(GrantRequest(mission_id=mission, root=str(root)))
            plan = await service.plan("file-organize", {"path": "."}, mission, grant["grant_id"])
            async def dispatch(tool, arguments):
                return gateway.execute("computer", ToolRequest.model_validate({"mission_id": mission, "grant_id": grant["grant_id"], "call": {"tool": tool, "arguments": arguments}}))
            result = await execute(service, plan, dispatch)
            assert result["status"] == "completed"
            assert len(result["steps"]) == 2
            assert result["steps"][0]["result"]["data"]["entries"][0]["name"] == "hello.txt"
            assert result == await service.get_execution(plan["plan_id"])
            assert _size(result) <= 32 * 1024
            with pytest.raises(SkillError, match="已执行"):
                await execute(service, plan, dispatch)
            reopened = SkillsService(store)
            await reopened.open()
            assert result == await reopened.get_execution(plan["plan_id"])
            with pytest.raises(SkillError):
                await execute(reopened, plan, dispatch)
        finally:
            await store.close()
    asyncio.run(run())


def test_builtins_versions_and_invalid_inputs_not_empty_success(tmp_path):
    async def run():
        store, service = await setup(tmp_path)
        try:
            items = (await service.list())["skills"]
            assert len(items) == 5
            assert sum(item["available"] for item in items) == 5
            for item in items:
                if item["id"] in {"web-research", "report-build"}:
                    assert item["version"] == "1.1.0"
                    # V4-010已实现真实适配；旧文件盘点输入仍不能变为空壳成功。
                    with pytest.raises(SkillError):
                        await service.plan(item["id"], {"path": "."}, *identities())
        finally:
            await store.close()
    asyncio.run(run())


def test_import_review_change_version_and_builtin_protection(tmp_path):
    async def run():
        store, service = await setup(tmp_path)
        try:
            root, manifest = package(tmp_path)
            review = await service.preview_import(str(root))
            assert review["manifest"] == manifest
            (root / "SKILL.md").write_text("正文已经变化", encoding="utf-8")
            with pytest.raises(SkillError, match="已变化"):
                await service.register(review["review_id"], review["revision"])
            first = await register(service, root)
            assert first["available"] and not first["builtin"]
            (root / "SKILL.md").write_text("同版本不同正文", encoding="utf-8")
            with pytest.raises(SkillError, match="不同版本"):
                await register(service, root)
            manifest["version"] = "1.0.1"
            (root / "workflow.json").write_text(json.dumps(manifest), encoding="utf-8")
            assert (await register(service, root))["version"] == "1.0.1"
            builtin, _ = package(tmp_path, "file-organize")
            with pytest.raises(SkillError, match="内置"):
                await service.preview_import(str(builtin))
        finally:
            await store.close()
    asyncio.run(run())


@pytest.mark.parametrize("change", [
    {"schema_version": True}, {"version": "latest"}, {"extra": "script"},
    {"input_schema": {"type": "array"}},
    {"input_schema": {"type": "object", "properties": {"grant_id": {"type": "string"}}}},
    {"input_schema": {"type": "object", "additionalProperties": True}},
    {"input_schema": {"type": "object", "$ref": "https://invalid.test"}},
    {"dependencies": ["custom"]}, {"dependencies": ["x"] * 17},
    {"steps": []}, {"steps": [{"id": "a", "tool": "run_shell", "arguments": {}, "output_schema": {"type": "object"}}]},
    {"steps": [{"id": "a", "tool": "list_directory", "arguments": {"path": {"from_step": "later"}}, "output_schema": {"type": "object"}}]},
    {"steps": [{"id": "a", "tool": "list_directory", "arguments": {"expression": "eval(1)"}, "output_schema": {"type": "object"}}]},
    {"steps": [{"id": "a", "tool": ["list_directory"], "arguments": {}, "output_schema": {"type": "object"}}]},
    {"output": {"bad": {"from_input": []}}},
])
def test_declarative_contract_rejects_unsafe_or_invalid(tmp_path, change):
    async def run():
        store, service = await setup(tmp_path)
        try:
            root, _ = package(tmp_path, **change)
            with pytest.raises(SkillError):
                await service.preview_import(str(root))
        finally:
            await store.close()
    asyncio.run(run())


@pytest.mark.parametrize("extra", ["script.py", "nested", "workflow.js"])
def test_extra_files_never_executed(tmp_path, extra):
    async def run():
        store, service = await setup(tmp_path)
        try:
            root, _ = package(tmp_path)
            if extra == "nested":
                (root / extra).mkdir()
            else:
                (root / extra).write_text("raise RuntimeError('must never execute')", encoding="utf-8")
            with pytest.raises(SkillError, match="额外"):
                await service.preview_import(str(root))
        finally:
            await store.close()
    asyncio.run(run())


@pytest.mark.parametrize("name,content", [("SKILL.md", "x" * (8 * 1024 + 1)), ("workflow.json", "x" * (16 * 1024 + 1)), ("workflow.json", '{"id":"a","id":"b"}'), ("workflow.json", '{"x":NaN}')])
def test_package_size_duplicate_json_nonfinite(tmp_path, name, content):
    async def run():
        store, service = await setup(tmp_path)
        try:
            root, _ = package(tmp_path)
            (root / name).write_text(content, encoding="utf-8")
            with pytest.raises(SkillError):
                await service.preview_import(str(root))
        finally:
            await store.close()
    asyncio.run(run())


def test_symlink_package_refused(tmp_path):
    async def run():
        store, service = await setup(tmp_path)
        try:
            root, _ = package(tmp_path)
            link = tmp_path / "package-link"
            try:
                link.symlink_to(root, target_is_directory=True)
            except OSError:
                pytest.skip("当前普通账户不具备创建Windows符号链接的能力")
            with pytest.raises(SkillError, match="链接|重解析"):
                await service.preview_import(str(link))
        finally:
            await store.close()
    asyncio.run(run())


def test_composition_real_metadata_previous_result_reference(tmp_path):
    async def run():
        store, service = await setup(tmp_path)
        try:
            root, _ = package(tmp_path, "child", steps=[{"id": "observe", "tool": "get_file_metadata", "arguments": {"path": {"from_input": "path"}}, "output_schema": {"type": "object", "additionalProperties": True}}], output={"observation": {"from_step": "observe"}}, output_schema={"type": "object", "properties": {"observation": {"type": "object", "additionalProperties": True}}, "required": ["observation"]})
            await register(service, root)
            parent, _ = package(tmp_path, "parent", dependencies=["child"], steps=[
                {"id": "first", "skill": "child", "arguments": {"path": {"from_input": "path"}}, "output_schema": {"type": "object", "additionalProperties": True}},
                {"id": "second", "tool": "get_file_metadata", "arguments": {"path": {"from_step": "first", "path": ["observation", "data", "path"]}}, "output_schema": {"type": "object", "additionalProperties": True}}], output={"last": {"from_step": "second"}}, output_schema={"type": "object", "additionalProperties": True})
            await register(service, parent)
            files = tmp_path / "files"
            files.mkdir()
            (files / "example.txt").write_text("合成资料", encoding="utf-8")
            mission, _ = identities()
            gateway = ComputerGateway()
            grant = gateway.grant(GrantRequest(mission_id=mission, root=str(files)))
            plan = await service.plan("parent", {"path": "example.txt"}, mission, grant["grant_id"])
            assert [step["id"] for step in plan["steps"]] == ["first/observe", "second"]
            async def dispatch(tool, arguments):
                return gateway.execute("computer", ToolRequest.model_validate({"mission_id": mission, "grant_id": grant["grant_id"], "call": {"tool": tool, "arguments": arguments}}))
            result = await execute(service, plan, dispatch)
            assert result["status"] == "completed"
            assert result["steps"][1]["result"]["data"]["path"] == "example.txt"
        finally:
            await store.close()
    asyncio.run(run())


def test_missing_cycle_and_depth_dependencies(tmp_path):
    async def run():
        store, service = await setup(tmp_path)
        try:
            a, _ = package(tmp_path, "alpha", dependencies=["beta"])
            summary = await register(service, a)
            assert not summary["available"] and "未登记" in summary["unavailable_reason"]
            with pytest.raises(SkillError):
                await service.plan("alpha", {"path": "."}, *identities())
            b, _ = package(tmp_path, "beta", dependencies=["alpha"])
            with pytest.raises(SkillError, match="循环"):
                await service.preview_import(str(b))
            for i in reversed(range(5)):
                root, _ = package(tmp_path, "layer" + str(i), dependencies=["layer" + str(i + 1)] if i < 4 else [])
                if i == 0:
                    with pytest.raises(SkillError, match="超过4层"):
                        await service.preview_import(str(root))
                else:
                    await register(service, root)
        finally:
            await store.close()
    asyncio.run(run())


def test_inputs_parameter_schema_and_identity_binding(tmp_path):
    async def run():
        store, service = await setup(tmp_path)
        try:
            for invalid in ({}, {"path": True}, {"path": ".", "grant_id": "pretend"}):
                with pytest.raises(SkillError):
                    await service.plan("file-organize", invalid, *identities())
            root, _ = package(tmp_path, steps=[{"id": "one", "tool": "list_directory", "arguments": {"limit": True}, "output_schema": {"type": "object", "additionalProperties": True}}], output={"one": {"from_step": "one"}}, output_schema={"type": "object", "additionalProperties": True})
            await register(service, root)
            with pytest.raises(SkillError, match="只读工具契约"):
                await service.plan("custom", {"path": "."}, *identities())
            plan = await service.plan("file-organize", {"path": "."}, *identities())
            calls = []
            async def never(tool, arguments):
                calls.append(tool)
                return {}
            with pytest.raises(SkillError, match="不匹配"):
                await service.execute(plan["plan_id"], plan["revision"], str(uuid4()), plan["grant_id"], never)
            assert calls == []
        finally:
            await store.close()
    asyncio.run(run())


def test_toggle_epoch_and_dependency_update_invalidate_plans(tmp_path):
    async def run():
        store, service = await setup(tmp_path)
        try:
            plan = await service.plan("file-organize", {"path": "."}, *identities())
            await service.set_enabled("file-organize", False)
            await service.set_enabled("file-organize", True)
            async def never(*_):
                raise AssertionError("旧批准不得执行")
            with pytest.raises(SkillError, match="旧计划失效"):
                await execute(service, plan, never)
            root, manifest = package(tmp_path)
            await register(service, root)
            plan = await service.plan("custom", {"path": "."}, *identities())
            manifest["version"] = "1.0.1"
            (root / "workflow.json").write_text(json.dumps(manifest), encoding="utf-8")
            await register(service, root)
            with pytest.raises(SkillError, match="旧计划失效"):
                await execute(service, plan, never)
        finally:
            await store.close()
    asyncio.run(run())


@pytest.mark.parametrize("failure", ["tool", "limited", "oversize", "output_schema", "revoked"])
def test_step_failures_stop_and_save_facts(tmp_path, failure):
    async def run():
        store, service = await setup(tmp_path)
        try:
            sid = "file-organize"
            if failure == "output_schema":
                root, _ = package(tmp_path, steps=[{"id": "one", "tool": "list_directory", "arguments": {}, "output_schema": {"type": "object", "properties": {"wanted": {"type": "boolean"}}, "required": ["wanted"]}}], output={"one": {"from_step": "one"}}, output_schema={"type": "object", "additionalProperties": True})
                await register(service, root)
                sid = "custom"
            plan = await service.plan(sid, {"path": "."}, *identities())
            calls = []
            async def dispatch(tool, arguments):
                calls.append(tool)
                if failure == "tool":
                    raise ToolError("PERMISSION_DENIED", "未授权")
                if failure == "revoked":
                    await service.set_enabled(sid, False)
                return {"complete": failure != "limited", "truncated": False, "errors": [], "data": "x" * 32768 if failure == "oversize" else {}}
            result = await execute(service, plan, dispatch)
            assert result["status"] in ("failed", "limited")
            assert len(calls) == 1
            assert len(result["steps"]) == 1
            assert result == await service.get_execution(plan["plan_id"])
            assert _size(result) <= 32 * 1024
        finally:
            await store.close()
    asyncio.run(run())


def test_cancellation_and_restart_never_replay(tmp_path):
    async def run():
        store, service = await setup(tmp_path)
        try:
            plan = await service.plan("file-organize", {"path": "."}, *identities())
            entered = asyncio.Event()
            async def dispatch(*_):
                entered.set()
                await asyncio.Event().wait()
            task = asyncio.create_task(execute(service, plan, dispatch))
            await entered.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            result = await service.get_execution(plan["plan_id"])
            assert result["status"] == "interrupted"
            assert result["steps"][0]["status"] == "unknown"
            await store._db().execute("UPDATE skills_executions SET status='running',result_json=? WHERE plan_id=?", (json.dumps({**result, "status": "running"}), plan["plan_id"]))
            reopened = SkillsService(store)
            await reopened.open()
            assert (await reopened.get_execution(plan["plan_id"]))["status"] == "interrupted"
        finally:
            await store.close()
    asyncio.run(run())


def test_import_registry_budget_and_flatten_step_budget(tmp_path):
    async def run():
        store, service = await setup(tmp_path)
        try:
            for i in range(32):
                root, _ = package(tmp_path, "custom" + str(i))
                await register(service, root)
            root, _ = package(tmp_path, "overflow")
            with pytest.raises(SkillError, match="32"):
                await service.preview_import(str(root))
        finally:
            await store.close()
        nested_path = tmp_path / "nesteddb"
        nested_path.mkdir()
        store, service = await setup(nested_path)
        try:
            schema = {"type": "object", "additionalProperties": True}
            root, _ = package(tmp_path, "many", steps=[{"id": "item" + str(i), "tool": "get_file_metadata", "arguments": {"path": {"from_input": "path"}}, "output_schema": schema} for i in range(16)], output={"last": {"from_step": "item15"}}, output_schema=schema)
            await register(service, root)
            outer, _ = package(tmp_path, "combined", dependencies=["many"], steps=[{"id": "nested" + str(i), "skill": "many", "arguments": {"path": {"from_input": "path"}}, "output_schema": schema} for i in range(3)], output={"last": {"from_step": "nested2"}}, output_schema=schema)
            await register(service, outer)
            with pytest.raises(SkillError, match="32个"):
                await service.plan("combined", {"path": "."}, *identities())
        finally:
            await store.close()
    asyncio.run(run())


def test_maximum_chinese_list_pagination_frame_budget_and_single_letter_rejected(tmp_path):
    async def run():
        store, service = await setup(tmp_path)
        try:
            root, _ = package(tmp_path, "a")
            with pytest.raises(SkillError, match="ID"):
                await service.preview_import(str(root))
            for i in range(32):
                root, _ = package(tmp_path, "entry" + str(i), name="名" * 100, description="说" * 1000)
                await register(service, root)
            seen = []
            for offset in (0, 10, 20, 30):
                page = await service.list(offset)
                assert page["offset"] == offset and page["total"] == 37
                assert len(page["skills"]) <= 10 and _size(page) < 48 * 1024
                seen.extend(item["id"] for item in page["skills"])
            assert len(set(seen)) == 37
        finally:
            await store.close()
    asyncio.run(run())


def test_repeat_output_expansion_budget_rejected_before_exponential_copy(tmp_path):
    async def run():
        store, service = await setup(tmp_path)
        try:
            schema = {"type": "object", "additionalProperties": True}
            leaf, _ = package(tmp_path, "leaf", steps=[{"id": "observe", "tool": "get_file_metadata", "arguments": {"path": {"from_input": "path"}}, "output_schema": schema}], output={"result": {"from_step": "observe"}}, output_schema=schema)
            await register(service, leaf)
            previous = "leaf"
            for sid in ("levelone", "leveltwo", "levelthree"):
                root, _ = package(tmp_path, sid, dependencies=[previous], steps=[{"id": "child", "skill": previous, "arguments": {"path": {"from_input": "path"}}, "output_schema": schema}], output={"repeat" + str(i): {"from_step": "child"} for i in range(50)}, output_schema=schema)
                await register(service, root)
                previous = sid
            with pytest.raises(SkillError, match="预算"):
                await service.plan(previous, {"path": "."}, *identities())
        finally:
            await store.close()
    asyncio.run(run())


def test_runtime_repeat_result_budget_refuses_completed(tmp_path):
    async def run():
        store, service = await setup(tmp_path)
        try:
            schema = {"type": "object", "additionalProperties": True}
            root, _ = package(tmp_path, output_schema=schema, output={"repeat" + str(i): {"from_step": "inventory"} for i in range(20)})
            await register(service, root)
            plan = await service.plan("custom", {"path": "."}, *identities())
            calls = []
            async def dispatch(tool, arguments):
                calls.append(tool)
                return {"complete": True, "truncated": False, "errors": [], "data": "x" * 2000}
            result = await execute(service, plan, dispatch)
            assert result["status"] == "failed"
            assert result["error"]["code"] == "SKILL_LIMIT"
            assert _size(result) < 32 * 1024
        finally:
            await store.close()
    asyncio.run(run())


def test_timeout_unknown_no_retry_with_synthetic_clock(tmp_path, monkeypatch):
    async def run():
        store, service = await setup(tmp_path)
        try:
            elapsed = [0.0]
            monkeypatch.setattr(skills_module, "monotonic", lambda: elapsed[0])
            plan = await service.plan("file-organize", {"path": "."}, *identities())
            calls = []
            async def dispatch(tool, arguments):
                calls.append(tool)
                elapsed[0] = 11.0
                return {"complete": True, "truncated": False, "errors": [], "data": {}}
            result = await execute(service, plan, dispatch)
            assert result["status"] == "interrupted" and len(calls) == 1
            assert result["steps"][0]["status"] == "unknown"
            assert result["steps"][0]["result"] is None
        finally:
            await store.close()
    asyncio.run(run())


def test_cancel_history_restart_planned_and_preflight_failure_recorded(tmp_path):
    async def run():
        store, service = await setup(tmp_path)
        try:
            plan = await service.plan("file-organize", {"path": "."}, *identities())
            result = await service.cancel(plan["plan_id"], plan["revision"], plan["mission_id"], plan["grant_id"])
            assert result["status"] == "interrupted" and result["steps"] == []
            assert (await service.history())["executions"][0] == {"plan_id": plan["plan_id"], "skill_id": "file-organize", "version": "1.0.0", "status": "interrupted"}
            plan = await service.plan("file-organize", {"path": "."}, *identities())
            await service.set_enabled("file-organize", False)
            async def never(*_):
                raise AssertionError("不能执行旧计划")
            with pytest.raises(SkillError):
                await execute(service, plan, never)
            assert (await service.get_execution(plan["plan_id"]))["status"] == "failed"
            await service.set_enabled("file-organize", True)
            plan = await service.plan("file-organize", {"path": "."}, *identities())
            reopened = SkillsService(store)
            await reopened.open()
            assert (await reopened.get_execution(plan["plan_id"]))["status"] == "interrupted"
        finally:
            await store.close()
    asyncio.run(run())


@pytest.mark.parametrize("field,value", [("name", "\0" * 100), ("description", "\0" * 1000), ("name", "😀" * 100), ("description", "😀" * 1000), ("name", "line\nname")])
def test_human_summary_control_characters_and_utf16_limits(tmp_path, field, value):
    async def run():
        store, service = await setup(tmp_path)
        try:
            root, _ = package(tmp_path, **{field: value})
            with pytest.raises(SkillError):
                await service.preview_import(str(root))
            assert (await service.list(36))["offset"] == 36
        finally:
            await store.close()
    asyncio.run(run())


@pytest.mark.skipif(os.name != "nt", reason="仅Windows提供目录联接")
def test_real_windows_junction_package_rejected_without_elevation(tmp_path):
    async def run():
        store, service = await setup(tmp_path)
        try:
            root, _ = package(tmp_path)
            link = tmp_path / "junction"
            created = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(root)], capture_output=True, timeout=5)
            if created.returncode:
                pytest.skip("当前环境拒绝创建合成目录联接")
            try:
                with pytest.raises(SkillError, match="重解析"):
                    await service.preview_import(str(link))
            finally:
                # rmdir 只解除已验证的联接本身，不递归操作联接指向的目录。
                assert link.parent == tmp_path and link.lstat().st_file_attributes & 0x400
                os.rmdir(link)
        finally:
            await store.close()
    asyncio.run(run())


def test_disabled_dependency_cannot_hide_cycle_and_invalid_unicode_refused(tmp_path):
    async def run():
        store, service = await setup(tmp_path)
        try:
            root, _ = package(tmp_path, "alpha", dependencies=["beta"])
            await register(service, root)
            await service.set_enabled("alpha", False)
            root, _ = package(tmp_path, "beta", dependencies=["alpha"])
            with pytest.raises(SkillError, match="循环"):
                await service.preview_import(str(root))
            with pytest.raises(SkillError, match="Unicode"):
                _size({"text": "\ud800"})
        finally:
            await store.close()
    asyncio.run(run())
