"""V4-007真实SQLite批准事实与合成Session；真实传输由独立transport测试验证。"""

import asyncio
import copy
import json
from pathlib import Path
import sys
from uuid import uuid4

import pytest
from test_v4_mcp_transport import tls_files

from orvia_backend.mcp import McpService, McpError
from orvia_backend.memory.service import encoded, digest, size
from test_chat import setup, create


INPUT = {"type": "object", "properties": {"query": {"type": "string", "minLength": 1, "maxLength": 100}}, "required": ["query"], "additionalProperties": False}
OUTPUT = {"type": "object", "properties": {"count": {"type": "integer", "minimum": 0, "maximum": 10}}, "required": ["count"], "additionalProperties": False}


def tool(name="get_record"):
    return {"name": name, "description": "合成只读查询", "inputSchema": copy.deepcopy(INPUT), "outputSchema": copy.deepcopy(OUTPUT), "annotations": {"readOnlyHint": True, "destructiveHint": False}}


class Session:
    def __init__(self, tools=None, callback=None, result=None):
        self.tools = [tool()] if tools is None else tools
        self.changed, self.closed = False, False
        self.server_info, self.capabilities = {"name": "合成服务", "version": "1"}, {"tools": {"listChanged": True}}
        self.calls, self.discovery, self.close_count = 0, 0, 0
        self.callback = callback
        self.result = result or {"content": [{"type": "text", "text": "合成记录"}], "structuredContent": {"count": 1}, "isError": False}

    async def request(self, method, params=None):
        if self.closed:
            raise McpError("MCP_CLOSED", "合成服务已关闭")
        if method == "tools/list":
            self.discovery += 1
            return {"tools": copy.deepcopy(self.tools)}
        assert method == "tools/call"
        self.calls += 1
        if self.callback:
            await self.callback()
        return copy.deepcopy(self.result)

    async def close(self):
        self.close_count += 1;self.closed = True
        return {"closed": True, "children_reaped": True}


async def prepare(tmp_path, session=None):
    app = await setup(tmp_path)
    cid = (await create(app))["id"]
    session = session or Session()
    async def connector(config, credential=None):
        session.closed = False
        return session
    service = McpService(app.store, app.chat, connector)
    await service.open()
    return app, service, cid, session


async def configure(service, tmp_path, config=None):
    config = config or {"name": "合成HTTPS MCP", "transport": "https", "url": "https://127.0.0.1:8443/mcp", "allowed_tools": ["get_record"]}
    path = tmp_path / "synthetic-mcp.json"
    path.write_text(encoded(config), encoding="utf-8")
    packet = await service.preview_config(str(path))
    summary = await service.configure(packet["review_id"], packet["revision"])
    return summary["id"], path


async def ready(service, tmp_path, config=None):
    sid, _ = await configure(service, tmp_path, config)
    packet = await service.connect_preview(sid)
    review = await service.connect(sid, packet["revision"])
    await service.approve_tools(sid, review["revision"])
    return sid, review


def test_actual_sqlite_single_approved_call_and_no_implicit_calls_on_open(tmp_path):
    async def run():
        app, service, cid, session = await prepare(tmp_path)
        try:
            sid, _ = await configure(service, tmp_path)
            assert session.discovery == session.calls == 0
            packet = await service.connect_preview(sid)
            review = await service.connect(sid, packet["revision"])
            assert session.calls == 0 and (await service.list())["servers"][0]["status"] == "review_required"
            with pytest.raises(McpError, match="MCP_TOOLS_REVIEW"):
                await service.call_preview(cid, sid, "get_record", {"query": "合成"})
            # 失败准备不隐式批准；重新连接并显示新的准确工具清单。
            session.closed = False
            packet = await service.connect_preview(sid)
            review = await service.connect(sid, packet["revision"])
            session.closed = False
            await service.approve_tools(sid, review["revision"])
            call = await service.call_preview(cid, sid, "get_record", {"query": "合成"})
            assert session.calls == 0
            execution = await service.call(cid, sid, call["revision"])
            assert execution["status"] == "completed" and session.calls == 1
            assert (await service.history(cid))["executions"] == [execution]
            rebuilt = await service.call_preview(cid, sid, "get_record", {"query": "合成"})
            assert rebuilt["revision"] == call["revision"]
            with pytest.raises(McpError, match="MCP_ALREADY_ATTEMPTED"):
                await service.call(cid, sid, rebuilt["revision"])
            assert session.calls == 1
        finally:
            await service.close();await app.close()
    asyncio.run(run())


@pytest.mark.parametrize("patch", [{"env": {"SYNTHETIC": "x"}}, {"url": "http://localhost/mcp"}, {"url": "https://a.invalid/mcp?value=1"}, {"url": "https://a.invalid/mcp#x"}, {"url": "https://user:pass@a.invalid/mcp"}, {"allowed_tools": ["get_record"] * 2}, {"extra": "x"}])
def test_configuration_rejects_unknown_fields_and_insecure_endpoints(tmp_path, patch):
    async def run():
        app, service, _, session = await prepare(tmp_path)
        try:
            config = {"name": "合成HTTPS MCP", "transport": "https", "url": "https://a.invalid/mcp", "allowed_tools": ["get_record"], **patch}
            with pytest.raises(McpError):
                await configure(service, tmp_path, config)
            assert session.discovery == session.calls == 0 and not (await service.list())["servers"]
        finally:
            await service.close();await app.close()
    asyncio.run(run())


@pytest.mark.parametrize("bad", ["duplicate", "change", "limit"])
def test_configuration_review_rechecks_file_and_server_limit(tmp_path, bad):
    async def run():
        app, service, _, _ = await prepare(tmp_path)
        try:
            path = tmp_path / "synthetic-mcp.json"
            config = {"name": "合成", "transport": "https", "url": "https://a.invalid/mcp", "allowed_tools": ["get_record"]}
            path.write_text(encoded(config), encoding="utf-8")
            if bad == "duplicate":
                path.write_text('{"name":"a","name":"b"}', encoding="utf-8")
                with pytest.raises(McpError, match="MCP_JSON"):
                    await service.preview_config(str(path))
            elif bad == "change":
                packet = await service.preview_config(str(path))
                path.write_text(encoded({**config, "name": "变化"}), encoding="utf-8")
                with pytest.raises(McpError, match="MCP_CONFIG_CHANGED"):
                    await service.configure(packet["review_id"], packet["revision"])
            else:
                for _ in range(5):
                    await configure(service, tmp_path, config)
                with pytest.raises(McpError, match="MCP_SERVER_LIMIT"):
                    await configure(service, tmp_path, config)
                assert len((await service.list())["servers"]) == 5
        finally:
            await service.close();await app.close()
    asyncio.run(run())


@pytest.mark.parametrize("kind", ["mutating_name", "hint_false", "destructive", "schema", "unknown_metadata", "unknown_annotation", "not_configured"])
def test_non_readonly_or_unsupported_tools_visible_blocked_and_never_called(tmp_path, kind):
    async def run():
        raw = tool()
        if kind == "mutating_name":raw["name"] = "get_delete_record"
        elif kind == "hint_false":raw["annotations"]["readOnlyHint"] = False
        elif kind == "destructive":raw["annotations"]["destructiveHint"] = True
        elif kind == "schema":raw["inputSchema"] = {"$ref": "https://a.invalid/schema"}
        elif kind == "unknown_metadata":raw["futureCapability"] = True
        elif kind == "unknown_annotation":raw["annotations"]["autoGrant"] = True
        elif kind == "not_configured":raw["name"] = "get_other"
        session = Session([raw])
        app, service, cid, _ = await prepare(tmp_path, session)
        try:
            sid, review = await ready(service, tmp_path)
            assert review["tools"][0]["allowed"] is False and review["tools"][0]["blocked_reason"]
            assert (await service.list())["servers"][0]["blocked_count"] == 1
            with pytest.raises(McpError, match="MCP_TOOL_DENIED"):
                await service.call_preview(cid, sid, raw["name"], {"query": "合成"})
            assert session.calls == 0
        finally:
            await service.close();await app.close()
    asyncio.run(run())


def test_tool_changes_without_notification_and_notification_both_revoke_approval(tmp_path):
    async def run():
        app, service, cid, session = await prepare(tmp_path)
        try:
            sid, _ = await ready(service, tmp_path)
            packet = await service.call_preview(cid, sid, "get_record", {"query": "合成"})
            session.tools[0]["description"] = "元数据实际变化"
            with pytest.raises(McpError, match="MCP_TOOLS_REVIEW"):
                await service.call(cid, sid, packet["revision"])
            assert session.calls == 0
            session.changed = True
            with pytest.raises(McpError, match="MCP_TOOLS_CHANGED"):
                await service.call_preview(cid, sid, "get_record", {"query": "合成"})
            assert (await service.list())["servers"][0]["status"] == "review_required"
        finally:
            await service.close();await app.close()
    asyncio.run(run())


@pytest.mark.parametrize("where", ["input", "output", "content", "error", "large"])
def test_input_output_and_content_contracts_are_actual_and_not_success(tmp_path, where):
    async def run():
        session = Session()
        if where == "output":session.result["structuredContent"] = {"count": -1}
        elif where == "content":session.result["content"] = [{"type": "image", "data": "synthetic", "mimeType": "image/png"}]
        elif where == "error":session.result["isError"] = True
        elif where == "large":session.result["content"] = [{"type": "text", "text": "合成" * 6000}]
        app, service, cid, _ = await prepare(tmp_path, session)
        try:
            sid, _ = await ready(service, tmp_path)
            if where == "input":
                with pytest.raises(McpError, match="MCP_SCHEMA"):
                    await service.call_preview(cid, sid, "get_record", {"query": "合成", "approved": True})
                assert session.calls == 0
            else:
                packet = await service.call_preview(cid, sid, "get_record", {"query": "合成"})
                execution = await service.call(cid, sid, packet["revision"])
                assert execution["status"] == ("limited" if where == "content" else "failed")
                assert session.calls == 1 and size(execution) <= 32768
                if where != "error":assert execution["result"] is None
        finally:
            await service.close();await app.close()
    asyncio.run(run())


@pytest.mark.parametrize("where", ["tools", "result", "server_info"])
@pytest.mark.parametrize("credential", ["synthetic-private-bearer-ONLY", 'synthetic-"quoted-bearer', 'synthetic-\\escaped-bearer'])
def test_remote_echo_of_private_credential_never_saved_or_returned(tmp_path, where, credential):
    async def run():
        app, service, cid, session = await prepare(tmp_path)
        try:
            sid, _ = await configure(service, tmp_path)
            await service.replace_credential(sid, credential)
            if where == "tools":session.tools[0]["description"] = credential
            elif where == "server_info":session.server_info["name"] = credential
            packet = await service.connect_preview(sid)
            if where != "result":
                with pytest.raises(McpError, match="MCP_CREDENTIAL_ECHO"):
                    await service.connect(sid, packet["revision"])
            else:
                review = await service.connect(sid, packet["revision"])
                await service.approve_tools(sid, review["revision"])
                session.result["content"][0]["text"] = credential
                packet = await service.call_preview(cid, sid, "get_record", {"query": "合成"})
                execution = await service.call(cid, sid, packet["revision"])
                assert execution["error"]["code"] == "MCP_CREDENTIAL_ECHO" and execution["result"] is None
                assert credential not in encoded(execution)
            async with app.store._lock:
                db = app.store._db()
                for table, column in (("mcp_servers", "config_json"), ("mcp_tool_reviews", "body_json"), ("mcp_executions", "data_json")):
                    assert all(credential not in row[0] for row in await service._rows(db, f"SELECT {column} FROM {table}"))
        finally:
            await service.close();await app.close()
    asyncio.run(run())


def test_pending_chat_deletion_blocks_preview_and_late_result_cannot_restore_rows(tmp_path):
    async def run():
        app, service, cid, session = await prepare(tmp_path)
        try:
            sid, _ = await ready(service, tmp_path)
            packet = await service.call_preview(cid, sid, "get_record", {"query": "合成"})
            async def deleted():
                async with app.store._lock:
                    db = app.store._db()
                    await db.execute("INSERT INTO chat_deletions VALUES(?,'pending')", (cid,))
                    await db.execute("DELETE FROM mcp_attempts WHERE cid=?", (cid,))
                    await db.execute("DELETE FROM mcp_executions WHERE cid=?", (cid,))
            session.callback = deleted
            with pytest.raises(McpError, match="MCP_CONVERSATION"):
                await service.call(cid, sid, packet["revision"])
            with pytest.raises(McpError, match="MCP_CONVERSATION"):
                await service.call_preview(cid, sid, "get_record", {"query": "合成"})
            async with app.store._lock:
                assert not await service._rows(app.store._db(), "SELECT 1 FROM mcp_executions WHERE cid=?", (cid,))
                assert not await service._rows(app.store._db(), "SELECT 1 FROM mcp_attempts WHERE cid=?", (cid,))
            assert session.calls == 1
        finally:
            await service.close();await app.close()
    asyncio.run(run())


def test_unknown_attempt_survives_rebuilt_preview_and_restart_without_replay(tmp_path):
    async def run():
        async def unknown():raise asyncio.TimeoutError("合成未知响应")
        app, service, cid, session = await prepare(tmp_path, Session(callback=unknown))
        try:
            sid, _ = await ready(service, tmp_path)
            packet = await service.call_preview(cid, sid, "get_record", {"query": "合成"})
            result = await service.call(cid, sid, packet["revision"])
            assert result["status"] == "unknown"
            service._reviews.clear()
            with pytest.raises(McpError, match="MCP_ALREADY_ATTEMPTED"):
                await service.call(cid, sid, packet["revision"])
            assert session.calls == 1
            restarted = McpService(app.store, app.chat)
            await restarted.open()
            assert (await restarted.list())["servers"][0]["status"] == "disconnected"
            assert (await restarted.history(cid))["executions"][0]["status"] == "unknown"
        finally:
            await service.close();await app.close()
    asyncio.run(run())


def test_attempt_budget_rejects_before_tool_call_and_retains_facts(tmp_path):
    async def run():
        app, service, cid, session = await prepare(tmp_path)
        try:
            sid, _ = await ready(service, tmp_path)
            packet = await service.call_preview(cid, sid, "get_record", {"query": "合成"})
            async with app.store._lock:
                for index in range(128):
                    await app.store._db().execute("INSERT INTO mcp_attempts VALUES(?,?,'unknown')", (cid, digest(index)))
            with pytest.raises(McpError, match="MCP_ATTEMPT_LIMIT"):
                await service.call(cid, sid, packet["revision"])
            assert session.calls == 0
            async with app.store._lock:
                assert (await service._rows(app.store._db(), "SELECT count(*) FROM mcp_attempts"))[0][0] == 128
        finally:
            await service.close();await app.close()
    asyncio.run(run())


def test_stdio_program_and_existing_argument_version_changes_reject_old_configuration(tmp_path):
    async def run():
        app, service, _, session = await prepare(tmp_path)
        try:
            script = tmp_path / "synthetic.py";script.write_text("print('synthetic')", encoding="utf-8")
            config = {"name": "合成stdio", "transport": "stdio", "executable": sys.executable, "args": [str(script)], "cwd": str(tmp_path), "allowed_tools": ["get_record"]}
            sid, _ = await configure(service, tmp_path, config)
            packet = await service.connect_preview(sid)
            assert packet["identity"]["args_files"][0]["sha256"]
            script.write_text("print('changed')", encoding="utf-8")
            with pytest.raises(McpError, match="MCP_PROGRAM_CHANGED"):
                await service.connect(sid, packet["revision"])
            assert session.discovery == session.calls == 0
            with pytest.raises(McpError, match="MCP_CREDENTIAL"):
                await service.replace_credential(sid, "synthetic-only")
        finally:
            await service.close();await app.close()
    asyncio.run(run())


def test_disconnect_remove_and_private_credential_rotation_revoke_all_call_previews(tmp_path):
    async def run():
        app, service, cid, session = await prepare(tmp_path)
        try:
            sid, _ = await ready(service, tmp_path)
            packet = await service.call_preview(cid, sid, "get_record", {"query": "合成"})
            await service.replace_credential(sid, "synthetic-private-new")
            with pytest.raises(McpError, match="MCP_REVIEW"):
                await service.call(cid, sid, packet["revision"])
            assert session.closed and session.calls == 0
            removed = await service.remove(sid)
            assert removed["removed"] and not (await service.list())["servers"]
        finally:
            await service.close();await app.close()
    asyncio.run(run())


@pytest.mark.parametrize("code", ["MCP_TIMEOUT", "MCP_CANCELLED", "MCP_SESSION_EXPIRED", "MCP_SERVER_REQUEST", "MCP_DISCONNECTED"])
def test_actual_transport_error_after_attempt_is_unknown_not_verified_failure(tmp_path, code):
    async def run():
        async def unavailable():raise McpError(code, "合成未知响应")
        app, service, cid, session = await prepare(tmp_path, Session(callback=unavailable))
        try:
            sid, _ = await ready(service, tmp_path)
            packet = await service.call_preview(cid, sid, "get_record", {"query": "合成"})
            value = await service.call(cid, sid, packet["revision"])
            assert value["status"] == "unknown" and value["result"] is None and session.calls == 1
            assert (await service.history(cid))["executions"][0] == value
        finally:
            await service.close();await app.close()
    asyncio.run(run())


def test_whole_call_budget_cancellation_saves_unknown_and_closes_session(tmp_path, monkeypatch):
    async def run():
        from orvia_backend.mcp import service as module
        async def pending():await asyncio.Event().wait()
        app, service, cid, session = await prepare(tmp_path, Session(callback=pending))
        try:
            sid, _ = await ready(service, tmp_path)
            packet = await service.call_preview(cid, sid, "get_record", {"query": "合成"})
            monkeypatch.setattr(module, "CALL_SECONDS", .05)
            with pytest.raises(McpError, match="MCP_CALL_TIMEOUT"):
                await service.call(cid, sid, packet["revision"])
            assert (await service.history(cid))["executions"][0]["status"] == "unknown"
            assert session.calls == 1 and session.closed
        finally:
            await service.close();await app.close()
    asyncio.run(run())


def test_credential_changed_while_connect_pending_cannot_publish_old_connection(tmp_path):
    async def run():
        app, service, _, session = await prepare(tmp_path)
        begun, resume = asyncio.Event(), asyncio.Event()
        async def pending(config, credential=None):
            begun.set();await resume.wait();return session
        service.connector = pending
        try:
            sid, _ = await configure(service, tmp_path)
            await service.replace_credential(sid, "synthetic-first")
            preview = await service.connect_preview(sid)
            running = asyncio.create_task(service.connect(sid, preview["revision"]))
            await begun.wait()
            await service.replace_credential(sid, "synthetic-second")
            resume.set()
            with pytest.raises(McpError, match="MCP_CHANGED"):
                await running
            assert session.closed and session.discovery == 0 and not service._approved
        finally:
            await service.close();await app.close()
    asyncio.run(run())


def test_uncertain_child_close_is_retained_and_never_becomes_false_remove_success(tmp_path):
    async def run():
        app, service, _, session = await prepare(tmp_path)
        async def uncertain():
            session.closed = True
            return {"closed": True, "children_reaped": False}
        session.close = uncertain
        try:
            sid, _ = await ready(service, tmp_path)
            for _ in range(2):
                with pytest.raises(McpError, match="MCP_CLOSE_UNCERTAIN"):
                    await service.remove(sid)
            assert len((await service.list())["servers"]) == 1
        finally:
            await service.close();await app.close()
    asyncio.run(run())


@pytest.mark.skipif(sys.platform != "win32", reason="真实stdio Job只支持Windows")
def test_real_service_stdio_pages_schema_call_and_child_reaping(tmp_path):
    """整条服务调用使用真实初始化/分页stdio及Job；不依赖合成Session成功结果。"""
    async def run():
        import psutil
        app = await setup(tmp_path)
        cid = (await create(app))["id"]
        service = McpService(app.store, app.chat)
        await service.open()
        try:
            script = tmp_path / "synthetic-stdio.py"
            script.write_text(Path(__file__).with_name("v4_mcp_stdio_fixture.py").read_text(encoding="utf-8"), encoding="utf-8")
            config = {"name": "合成真实stdio", "transport": "stdio", "executable": sys.executable, "args": ["-I", "-u", str(script), "state"], "cwd": str(tmp_path), "allowed_tools": ["read_echo", "write_delete"]}
            sid, _ = await configure(service, tmp_path, config)
            preview = await service.connect_preview(sid)
            review = await service.connect(sid, preview["revision"])
            assert len(review["tools"]) == 2 and sum(item["allowed"] for item in review["tools"]) == 1
            await service.approve_tools(sid, review["revision"])
            packet = await service.call_preview(cid, sid, "read_echo", {"query": "合成真实调用"})
            result = await service.call(cid, sid, packet["revision"])
            assert result["status"] == "completed" and result["result"]["structuredContent"] == {"query": "合成真实调用"}
            state = json.loads(script.with_suffix(".state.json").read_text(encoding="utf-8"))
            assert state["calls"] == 1 and psutil.pid_exists(state["child_pid"])
            report = await service.disconnect(sid)
            assert report["closed"] and report["children_reaped"] and not psutil.pid_exists(state["child_pid"]) and not psutil.pid_exists(state["parent_pid"])
        finally:
            await service.close();await app.close()
    asyncio.run(run())


@pytest.mark.parametrize("url", ["https://a.invalid/mcp?", "https://a.invalid/mcp#", "https://例子.invalid/mcp", "HTTPS://a.invalid/mcp"])
def test_config_and_transport_share_exact_endpoint_identity_rejection(tmp_path, url):
    async def run():
        app, service, _, _ = await prepare(tmp_path)
        try:
            config = {"name": "合成", "transport": "https", "url": url, "allowed_tools": ["get_record"]}
            with pytest.raises(McpError):
                await configure(service, tmp_path, config)
        finally:
            await service.close();await app.close()
    asyncio.run(run())


def test_real_service_tls_discovery_approval_call_and_private_bearer(tls_files, tmp_path):
    """真实本机TLS与自签测试CA，生产verify仍True；整条服务实际HTTP调用一次。"""
    import ssl
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from orvia_backend.mcp import transport
    cert, key, verify = tls_files
    messages, headers = [], []
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def log_message(self, *args):pass
        def do_DELETE(self):
            self.send_response(204);self.send_header("Content-Length", "0");self.end_headers()
        def do_POST(self):
            value = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            messages.append(value);headers.append(dict(self.headers))
            if "id" not in value:
                self.send_response(202);self.send_header("Content-Length", "0");self.end_headers();return
            if value["method"] == "initialize":
                result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {"listChanged": True}}, "serverInfo": {"name": "synthetic-tls", "version": "1"}}
            elif value["method"] == "tools/list":result = {"tools": [tool()]}
            else:result = {"content": [{"type": "text", "text": "合成TLS记录"}], "structuredContent": {"count": 1}, "isError": False}
            payload = encoded({"jsonrpc": "2.0", "id": value["id"], "result": result}).encode()
            self.send_response(200);self.send_header("Content-Type", "application/json");self.send_header("Content-Length", str(len(payload)));self.send_header("Mcp-Session-Id", "synthetic-service-session");self.end_headers();self.wfile.write(payload)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(str(cert), str(key));server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True);thread.start()
    async def run():
        app = await setup(tmp_path);cid = (await create(app))["id"]
        async def connector(config, credential=None):return await transport.connect(config, credential, verify=verify)
        service = McpService(app.store, app.chat, connector);await service.open()
        try:
            config = {"name": "合成真实TLS", "transport": "https", "url": f"https://localhost:{server.server_address[1]}/mcp", "allowed_tools": ["get_record"]}
            sid, _ = await configure(service, tmp_path, config)
            await service.replace_credential(sid, "synthetic-service-bearer")
            preview = await service.connect_preview(sid);review = await service.connect(sid, preview["revision"]);await service.approve_tools(sid, review["revision"])
            call = await service.call_preview(cid, sid, "get_record", {"query": "合成"})
            actual = await service.call(cid, sid, call["revision"])
            assert actual["status"] == "completed" and actual["result"]["structuredContent"] == {"count": 1}
            assert sum(message["method"] == "tools/call" for message in messages) == 1
            assert all(header.get("Authorization") == "Bearer synthetic-service-bearer" for header in headers)
            assert (await service.disconnect(sid))["closed"]
        finally:
            await service.close();await app.close()
    try:asyncio.run(run())
    finally:server.shutdown();server.server_close();thread.join(2)


@pytest.mark.parametrize("mode", ["cursor_cycle", "duplicate_name", "too_many"])
def test_discovery_budget_rejects_cursor_cycles_and_incomplete_catalogues(tmp_path, mode):
    async def run():
        app, service, _, session = await prepare(tmp_path)
        original = session.request
        async def malformed(method, params=None):
            if method != "tools/list":return await original(method, params)
            session.discovery += 1
            if mode == "cursor_cycle":return {"tools": [], "nextCursor": "same"}
            if mode == "duplicate_name":return {"tools": [tool(), tool()]}
            return {"tools": [tool(f"get_synthetic{index}") for index in range(32)], "nextCursor": str(session.discovery)}
        session.request = malformed
        try:
            sid, _ = await configure(service, tmp_path)
            preview = await service.connect_preview(sid)
            with pytest.raises(McpError, match="MCP_TOOLS"):
                await service.connect(sid, preview["revision"])
            assert session.closed and session.calls == 0 and session.discovery <= 2
        finally:
            await service.close();await app.close()
    asyncio.run(run())


@pytest.mark.parametrize("content", [
    {"type": "text", "text": "合成", "annotations": {"priority": True}},
    {"type": "resource_link", "uri": "https://example.invalid/mcp", "name": "合成", "size": "wrong"},
])
def test_invalid_mcp_content_metadata_does_not_become_completed_evidence(tmp_path, content):
    async def run():
        session = Session(result={"content": [content], "structuredContent": {"count": 1}})
        app, service, cid, _ = await prepare(tmp_path, session)
        try:
            sid, _ = await ready(service, tmp_path)
            preview = await service.call_preview(cid, sid, "get_record", {"query": "合成"})
            result = await service.call(cid, sid, preview["revision"])
            assert result["status"] == "failed" and result["result"] is None
        finally:
            await service.close();await app.close()
    asyncio.run(run())
