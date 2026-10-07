"""MCP 配置、连接、工具批准与调用分离；SQLite 保存真实尝试及结果。"""

import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from urllib.parse import urlsplit
from uuid import uuid4

from ..memory.service import SENSITIVE, digest, encoded, size
from .protocol import McpError, VERSION, decode, encode
from . import schema

TABLES = ("mcp_attempts", "mcp_executions")
READ_NAME = re.compile(r"^(?:get|read|search|list|query|lookup)_[A-Za-z0-9_.-]{1,95}$")
WRITE_NAME = re.compile(r"(?:write|delete|remove|update|create|insert|execute|exec|command|shell|upload|download|send|publish|install|pay|trade|transfer|rename|move|eval)", re.I)
FORBIDDEN_ARG = re.compile(r"(?:^|[\s=])(?:--?(?:env|key|token|secret|password|pass|headers?|auth|authorization|bearer|credentials?|cookie|api[_-]?key))(?:=|$)|\bBearer\s", re.I)
CALL_SECONDS = 60


def _fail(code, message):
    raise McpError(code, message)


def _json(value, limit=32768):
    """有限 JSON 和实际 UTF8 大小先校验，任何返回正文都不能充当指令或授权。"""
    payload = encode(value)
    if len(payload) > limit:
        _fail("MCP_LIMIT", "MCP 正文超过当前预算")
    return decode(payload)


class McpService:
    """只有可信主进程完成对应原生确认后才调用配置、连接、批准及执行入口。"""

    def __init__(self, store, chat, connector=None):
        self.store, self.chat, self.connector = store, chat, connector
        self._reviews, self._sessions, self._credentials, self._approved = {}, {}, {}, {}
        self._lock, self._connect_locks, self._call_locks = asyncio.Lock(), {}, {}
        self._states = {}
        self._epochs = {}

    async def _rows(self, db, sql, args=()):
        async with db.execute(sql, args) as cursor:
            return await cursor.fetchall()

    async def open(self):
        """启动只迁移事实表，不启动程序、不联网、不恢复连接或调用批准。"""
        async with self.store._lock:
            db = self.store._db()
            await db.execute("CREATE TABLE IF NOT EXISTS mcp_servers(sid TEXT PRIMARY KEY,config_json TEXT NOT NULL CHECK(json_valid(config_json)),revision TEXT NOT NULL,identity_json TEXT NOT NULL CHECK(json_valid(identity_json)))")
            await db.execute("CREATE TABLE IF NOT EXISTS mcp_tool_reviews(sid TEXT NOT NULL,revision TEXT NOT NULL,body_json TEXT NOT NULL CHECK(json_valid(body_json)),state TEXT NOT NULL,PRIMARY KEY(sid,revision))")
            await db.execute("CREATE TABLE IF NOT EXISTS mcp_attempts(cid TEXT NOT NULL,revision TEXT NOT NULL,state TEXT NOT NULL,PRIMARY KEY(cid,revision))")
            await db.execute("CREATE TABLE IF NOT EXISTS mcp_executions(cid TEXT NOT NULL,revision TEXT NOT NULL,data_json TEXT NOT NULL CHECK(json_valid(data_json)),PRIMARY KEY(cid,revision))")
            await db.execute("UPDATE mcp_attempts SET state='unknown' WHERE state='running'")
            # 不确定中断只追加无正文状态；重启不能把保存的服务器元数据当连接许可。
            for cid, revision in await self._rows(db, "SELECT cid,revision FROM mcp_attempts WHERE state='unknown'"):
                rows = await self._rows(db, "SELECT data_json FROM mcp_executions WHERE cid=? AND revision=?", (cid, revision))
                if rows:
                    value = json.loads(rows[0][0])
                    if value["status"] == "unknown":
                        value["error"] = {"code": "MCP_INTERRUPTED", "message": "上次请求结果未知；未自动恢复或重发"}
                        await db.execute("UPDATE mcp_executions SET data_json=? WHERE cid=? AND revision=?", (encoded(value), cid, revision))
            await db.execute("UPDATE mcp_tool_reviews SET state='expired'")

    async def _alive(self, db, cid):
        if not await self._rows(db, "SELECT 1 FROM chat_conversations WHERE id=? AND id NOT IN(SELECT id FROM chat_deletions)", (cid,)):
            _fail("MCP_CONVERSATION", "所属会话不存在或正在删除")

    async def _server(self, sid):
        async with self.store._lock:
            rows = await self._rows(self.store._db(), "SELECT config_json,revision,identity_json FROM mcp_servers WHERE sid=?", (sid,))
        if not rows:
            _fail("MCP_SERVER", "MCP 服务配置不存在")
        return json.loads(rows[0][0]), rows[0][1], json.loads(rows[0][2])

    def _remember(self, kind, value):
        while len(self._reviews) >= 20:
            del self._reviews[next(iter(self._reviews))]
        rid = str(uuid4())
        self._reviews[rid] = {"kind": kind, "value": copy.deepcopy(value)}
        return rid

    def _find(self, kind, sid, revision):
        for rid, review in self._reviews.items():
            if review["kind"] == kind and review["value"].get("server_id") == sid and review["value"].get("revision") == revision:
                return rid, copy.deepcopy(review["value"])
        _fail("MCP_REVIEW", "准确审查不存在或已消费，请重新准备")

    def _invalidate(self, sid):
        self._approved.pop(sid, None)
        for rid, review in list(self._reviews.items()):
            if review["value"].get("server_id") == sid:
                del self._reviews[rid]

    @staticmethod
    def _config(value):
        value = _json(value, 16384)
        common = {"name", "transport", "allowed_tools"}
        if value.get("transport") == "stdio":
            if set(value) not in (common | {"executable", "args"}, common | {"executable", "args", "cwd"}):
                _fail("MCP_CONFIG", "stdio 配置仅允许名称、准确程序、参数、可选目录和工具清单")
            path = value["executable"]
            if not isinstance(path, str) or len(path) > 1000 or not Path(path).is_absolute() or Path(path).suffix.lower() != ".exe" or path.startswith("\\\\"):
                _fail("MCP_CONFIG", "stdio 程序须为本地绝对 .exe 路径")
            args = value["args"]
            if not isinstance(args, list) or len(args) > 16 or any(not isinstance(arg, str) or "\x00" in arg or len(arg) > 1000 or FORBIDDEN_ARG.search(arg) for arg in args) or size({"args": args}) > 8192:
                _fail("MCP_CONFIG", "stdio 参数超过预算或包含凭据/环境字段")
            cwd = value.get("cwd")
            if cwd is not None and (not isinstance(cwd, str) or len(cwd) > 1000 or not Path(cwd).is_absolute() or cwd.startswith("\\\\")):
                _fail("MCP_CONFIG", "工作目录须为本地绝对目录")
        elif value.get("transport") == "https":
            if set(value) != common | {"url"} or not isinstance(value.get("url"), str) or len(value["url"]) > 2048:
                _fail("MCP_CONFIG", "HTTPS 配置仅允许名称、准确 endpoint 和工具清单")
            try:
                parsed = urlsplit(value["url"])
                port = parsed.port
            except ValueError:
                _fail("MCP_CONFIG", "HTTPS endpoint 无效")
            if parsed.scheme != "https" or not parsed.hostname or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment or (port is not None and not 1 <= port <= 65535) or any(ord(c) < 33 for c in value["url"]):
                _fail("MCP_CONFIG", "只支持无userinfo/query/fragment的准确HTTPS endpoint")
            from .transport import endpoint
            endpoint(value["url"])
        else:
            _fail("MCP_CONFIG", "只支持 stdio 或 HTTPS MCP 服务")
        if not isinstance(value.get("name"), str) or not 1 <= len(value["name"]) <= 80 or any(ord(c) < 32 for c in value["name"]):
            _fail("MCP_CONFIG", "服务名称须为1～80个普通字符")
        names = value.get("allowed_tools")
        if not isinstance(names, list) or len(names) > 16 or any(not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", name) for name in names) or len(set(names)) != len(names):
            _fail("MCP_CONFIG", "明确工具清单最多16个不同准确名称")
        if SENSITIVE.search(encoded(value)):
            _fail("MCP_CONFIG_SECRET", "配置不能包含凭据、密钥或敏感字段；使用独立私有凭据入口")
        return value

    @staticmethod
    def _read_config(path):
        file = Path(path)
        try:
            info = file.lstat()
            if not file.is_absolute() or file.suffix.lower() != ".json" or not stat.S_ISREG(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400 or file.is_symlink() or info.st_size > 16384:
                _fail("MCP_CONFIG_FILE", "配置须为最多16KiB的普通绝对JSON文件")
            with file.open("rb") as handle:
                data = handle.read(16385)
            return McpService._config(decode(data))
        except OSError:
            _fail("MCP_CONFIG_FILE", "无法读取所选配置文件")

    @staticmethod
    def _identity(config):
        """程序与现有文件参数逐个哈希；隐式模块依赖仍需用户信任服务供应方。"""
        if config["transport"] == "https":
            return {"executable_hash": None, "cwd": None, "args_files": []}
        def plain(path, directory=False):
            try:
                info = path.lstat()
                if path.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400 or (not stat.S_ISDIR(info.st_mode) if directory else not stat.S_ISREG(info.st_mode)):
                    _fail("MCP_PROGRAM", "程序、工作目录和文件参数须为普通本地对象")
                return info
            except OSError:
                _fail("MCP_PROGRAM", "无法核验程序或工作目录")
        executable = Path(config["executable"])
        cwd = Path(config.get("cwd") or executable.parent)
        plain(cwd, True)
        budget = [0]
        def hashed(path):
            info = plain(path)
            budget[0] += info.st_size
            if info.st_size > 256 * 1024 * 1024 or budget[0] > 512 * 1024 * 1024:
                _fail("MCP_PROGRAM_LIMIT", "程序身份哈希单文件256MiB/合计512MiB预算已超出")
            result = hashlib.sha256()
            try:
                with path.open("rb") as handle:
                    while data := handle.read(64 * 1024):
                        result.update(data)
                after = plain(path)
            except OSError:
                _fail("MCP_PROGRAM", "程序或文件参数读取失败")
            if (info.st_size, info.st_mtime_ns, info.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
                _fail("MCP_PROGRAM_CHANGED", "身份哈希期间程序或文件参数发生变化")
            return {"path": str(path.resolve()), "sha256": result.hexdigest(), "bytes": info.st_size}
        executable_hash = hashed(executable)["sha256"]
        files, seen = [], set()
        for arg in config["args"]:
            token = arg.split("=", 1)[1] if arg.startswith("-") and "=" in arg else arg
            candidate = Path(token)
            candidate = candidate if candidate.is_absolute() else cwd / candidate
            if token and candidate.is_file():
                resolved = str(candidate.resolve())
                if resolved not in seen:
                    files.append(hashed(candidate));seen.add(resolved)
        return {"executable_hash": executable_hash, "cwd": str(cwd.resolve()), "args_files": files}

    async def _checked_identity(self, config, expected):
        try:
            actual = await asyncio.wait_for(asyncio.to_thread(self._identity, config), 10)
        except asyncio.TimeoutError:
            _fail("MCP_PROGRAM_LIMIT", "程序身份核验10秒预算已耗尽")
        if actual != expected:
            _fail("MCP_PROGRAM_CHANGED", "程序、文件参数或工作目录已变化，请重新配置审查")

    def _no_echo(self, sid, value):
        """恶意服务回显当前独立凭据时整包拒绝，不能落库、展示或写异常正文。"""
        credential = self._credentials.get(sid)
        value = _json(value, 65536)
        def includes(item):
            if isinstance(item, str):
                return credential in item
            if isinstance(item, dict):
                return any(includes(key) or includes(child) for key, child in item.items())
            if isinstance(item, list):
                return any(includes(child) for child in item)
            return False
        if credential and includes(value):
            _fail("MCP_CREDENTIAL_ECHO", "MCP 服务返回内容包含私有凭据，已拒绝展示与保存")

    async def preview_config(self, path):
        """路径只来自原生文件选择，解析阶段不执行程序或连接服务。"""
        value = await asyncio.to_thread(self._read_config, path)
        revision = digest(value)
        async with self._lock:
            rid = self._remember("config", {"config": value, "revision": revision, "path": path})
        return {"review_id": rid, "revision": revision, "config": value}

    async def configure(self, review_id, revision):
        """准确原生配置确认后登记，重新读配置以拒绝选择后内容变化。"""
        async with self._lock:
            review = self._reviews.pop(review_id, None)
            if review is None or review["kind"] != "config" or review["value"]["revision"] != revision:
                _fail("MCP_REVIEW", "配置审查已失效")
            value = review["value"]
            config = await asyncio.to_thread(self._read_config, value["path"])
            if config != value["config"]:
                _fail("MCP_CONFIG_CHANGED", "配置正文已变化，旧确认失效")
            identity = await asyncio.wait_for(asyncio.to_thread(self._identity, config), 10)
            sid = str(uuid4())
            async with self.store._lock:
                db = self.store._db()
                if (await self._rows(db, "SELECT count(*) FROM mcp_servers"))[0][0] >= 5:
                    _fail("MCP_SERVER_LIMIT", "最多配置5个 MCP 服务")
                await db.execute("INSERT INTO mcp_servers VALUES(?,?,?,?)", (sid, encoded(config), revision, encoded(identity)))
            self._states[sid] = ("configured", None)
        return await self._summary(sid)

    async def _summary(self, sid):
        config, revision, _ = await self._server(sid)
        approved = self._approved.get(sid)
        review = approved or next((item["value"] for item in reversed(list(self._reviews.values())) if item["kind"] == "tools" and item["value"]["server_id"] == sid), None)
        state, reason = self._states.get(sid, ("disconnected", None))
        session = self._sessions.get(sid)
        if not session and state == "ready":
            state = "disconnected"
        elif session and getattr(session["session"], "closed", False):
            state, reason = "error", "MCP_DISCONNECTED"
            self._approved.pop(sid, None)
        elif session and session["session"].changed:
            state, reason = "review_required", "MCP_TOOLS_CHANGED"
            self._approved.pop(sid, None)
        tools = review["tools"] if review else []
        return {"id": sid, "name": config["name"], "transport": config["transport"], "revision": revision, "status": state,
                "tools_count": len(tools), "blocked_count": sum(not tool["allowed"] for tool in tools), "reason": reason, "credential_configured": sid in self._credentials}

    async def list(self):
        """配置事实和当前连接状态分开展示，保存的审查记录不能恢复运行授权。"""
        async with self.store._lock:
            ids = [row[0] for row in await self._rows(self.store._db(), "SELECT sid FROM mcp_servers ORDER BY rowid LIMIT 5")]
        return {"servers": [await self._summary(sid) for sid in ids]}

    async def connect_preview(self, server_id):
        """显示准确程序/参数/目录或HTTPS endpoint，首次连接仍须单独原生确认。"""
        config, revision, identity = await self._server(server_id)
        await self._checked_identity(config, identity)
        packet = {"server_id": server_id, "config": config, "identity": identity, "credential_configured": server_id in self._credentials, "purpose": "连接并发现 MCP 工具"}
        packet["revision"] = digest([revision, packet, self._epochs.get(server_id)])
        async with self._lock:
            self._remember("connect", packet)
        return packet

    def _tool(self, sid, config, raw):
        if not isinstance(raw, dict):
            _fail("MCP_TOOLS", "工具元数据须为JSON对象")
        self._no_echo(sid, raw)
        raw = _json(raw)
        name = raw.get("name")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", name):
            _fail("MCP_TOOLS", "工具名称无效")
        reason = None
        fields = {"name", "title", "description", "inputSchema", "outputSchema", "annotations", "_meta"}
        if set(raw) - fields:
            reason = "工具元数据存在当前不支持的字段"
        elif any(key in raw and (not isinstance(raw[key], str) or len(raw[key]) > maximum) for key, maximum in (("title", 100), ("description", 4096))):
            reason = "工具名称或描述超过预算"
        elif name not in config["allowed_tools"]:
            reason = "该准确名称不在用户原生配置的工具清单"
        elif not READ_NAME.fullmatch(name) or WRITE_NAME.search(name):
            reason = "当前仅支持程序允许的明确只读工具名称"
        annotations = raw.get("annotations", {})
        if not isinstance(annotations, dict) or set(annotations) - {"title", "readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint"} or any(type(annotations[key]) is not bool for key in annotations if key != "title") or ("title" in annotations and (not isinstance(annotations["title"], str) or len(annotations["title"]) > 100)):
            reason = "工具 annotations 包含未知字段或类型"
        elif annotations.get("destructiveHint") is True or annotations.get("readOnlyHint") is False:
            reason = "工具声明存在破坏能力或明确不是只读"
        try:
            schema.validate_schema(raw.get("inputSchema"))
            if raw.get("inputSchema", {}).get("type") != "object":
                _fail("MCP_SCHEMA", "工具输入必须是 object schema")
            if "outputSchema" in raw:
                schema.validate_schema(raw["outputSchema"])
            if "_meta" in raw and (not isinstance(raw["_meta"], dict) or size(raw["_meta"]) > 4096):
                reason = "工具附加元数据超过预算"
        except McpError:
            reason = "工具 JSON Schema 超出当前支持子集"
        return {"name": name, "metadata": raw, "allowed": reason is None, "blocked_reason": reason}

    async def _discover(self, sid, handle, config, revision):
        """最多8页/32工具/30秒，游标循环、重复名称、未知分页字段都不静默忽略。"""
        async def collect():
            tools, cursors, cursor = [], set(), None
            for _ in range(8):
                result = await handle["session"].request("tools/list", {} if cursor is None else {"cursor": cursor})
                self._no_echo(sid, result)
                result = _json(result)
                if set(result) - {"tools", "nextCursor", "_meta"} or not isinstance(result.get("tools"), list) or len(result["tools"]) > 32:
                    _fail("MCP_TOOLS", "工具分页结构无效或超过32项")
                tools.extend(self._tool(sid, config, item) for item in result["tools"])
                if len(tools) > 32 or len({tool["name"] for tool in tools}) != len(tools):
                    _fail("MCP_TOOLS", "工具总数超过32项或准确名称重复")
                cursor = result.get("nextCursor")
                if cursor is None:
                    break
                if not isinstance(cursor, str) or not 1 <= len(cursor) <= 256 or cursor in cursors:
                    _fail("MCP_TOOLS", "工具分页游标无效或循环")
                cursors.add(cursor)
            else:
                _fail("MCP_TOOL_LIMIT", "工具分页超过8页")
            session = handle["session"]
            self._no_echo(sid, session.server_info)
            self._no_echo(sid, session.capabilities)
            packet = {"server_id": sid, "server_revision": revision, "session_id": handle["id"], "server_info": session.server_info, "capabilities": session.capabilities, "tools": tools}
            packet["revision"] = digest(packet)
            return _json(packet)
        try:
            return await asyncio.wait_for(collect(), 30)
        except asyncio.TimeoutError:
            _fail("MCP_TOOL_TIMEOUT", "工具发现30秒预算已耗尽")

    async def connect(self, server_id, revision):
        """准确原生连接确认后实际握手/发现；工具还需另一份完整原生清单批准。"""
        async with self._connect_locks.setdefault(server_id, asyncio.Lock()):
            async with self._lock:
                rid, old = self._find("connect", server_id, revision)
                del self._reviews[rid]
            config, server_revision, identity = await self._server(server_id)
            expected = {"server_id": server_id, "config": config, "identity": identity, "credential_configured": server_id in self._credentials, "purpose": "连接并发现 MCP 工具"}
            expected["revision"] = digest([server_revision, expected, self._epochs.get(server_id)])
            if expected != old:
                _fail("MCP_CHANGED", "配置或凭据状态已变化，旧连接确认失效")
            await self._checked_identity(config, identity)
            if server_id in self._sessions:
                report = await self.disconnect(server_id)
                if not report["closed"] or not report["children_reaped"]:
                    _fail("MCP_CLOSE_UNCERTAIN", "上次连接或后代回收不确定，不能另启服务")
            epoch = self._epochs.get(server_id)
            if self.connector is None:
                from .transport import connect
                connector = connect
            else:
                connector = self.connector
            handle = None
            try:
                transport_config = {key: value for key, value in config.items() if key in {"transport", "executable", "args", "cwd", "url"}}
                session = await asyncio.wait_for(connector(transport_config, self._credentials.get(server_id)), 30)
                handle = {"id": str(uuid4()), "session": session}
                if epoch != self._epochs.get(server_id) or (await self._server(server_id))[1] != server_revision:
                    _fail("MCP_CHANGED", "连接期间配置或凭据许可已变化")
                self._sessions[server_id] = handle
                review = await self._discover(server_id, handle, config, server_revision)
                if session.changed or epoch != self._epochs.get(server_id) or self._sessions.get(server_id) is not handle:
                    _fail("MCP_TOOLS_CHANGED", "发现期间工具变化，请重新连接审查")
                async with self._lock:
                    self._remember("tools", review)
                self._states[server_id] = ("review_required", None)
                return review
            except BaseException:
                self._invalidate(server_id)
                self._sessions.pop(server_id, None)
                self._states[server_id] = ("error", "MCP_CONNECT_FAILED")
                if handle:
                    await asyncio.shield(handle["session"].close())
                raise

    async def _fresh(self, server_id):
        handle = self._sessions.get(server_id)
        if not handle:
            _fail("MCP_DISCONNECTED", "服务未连接，请原生确认连接及工具清单")
        if getattr(handle["session"], "closed", False):
            self._invalidate(server_id)
            _fail("MCP_DISCONNECTED", "服务连接已关闭，旧审批失效")
        config, revision, identity = await self._server(server_id)
        await self._checked_identity(config, identity)
        if handle["session"].changed:
            self._invalidate(server_id)
            self._states[server_id] = ("review_required", "MCP_TOOLS_CHANGED")
            _fail("MCP_TOOLS_CHANGED", "服务通知工具清单变化，旧审批失效")
        review = await self._discover(server_id, handle, config, revision)
        if handle is not self._sessions.get(server_id) or handle["session"].changed:
            self._invalidate(server_id)
            _fail("MCP_TOOLS_CHANGED", "连接或工具发现期间已变化")
        return review

    async def approve_tools(self, server_id, revision):
        """原生工具清单确认后再次逐页核验完整原元数据，hint 不等于能力保证。"""
        async with self._lock:
            rid, old = self._find("tools", server_id, revision)
            del self._reviews[rid]
        fresh = await self._fresh(server_id)
        if fresh != old:
            self._invalidate(server_id)
            _fail("MCP_TOOLS_CHANGED", "准确工具元数据已变化，请重新连接与审查")
        self._approved[server_id] = copy.deepcopy(fresh)
        async with self.store._lock:
            db = self.store._db()
            await db.execute("INSERT OR REPLACE INTO mcp_tool_reviews VALUES(?,?,?,'approved')", (server_id, revision, encoded(fresh)))
            await db.execute("DELETE FROM mcp_tool_reviews WHERE sid=? AND rowid NOT IN(SELECT rowid FROM mcp_tool_reviews WHERE sid=? ORDER BY rowid DESC LIMIT 20)", (server_id, server_id))
        self._states[server_id] = ("ready", None)
        return await self._summary(server_id)

    async def _call_packet(self, cid, server_id, tool, arguments):
        async with self.store._lock:
            await self._alive(self.store._db(), cid)
        arguments = _json(arguments, 8192)
        fresh = await self._fresh(server_id)
        approved = self._approved.get(server_id)
        if approved != fresh:
            self._invalidate(server_id)
            _fail("MCP_TOOLS_REVIEW", "工具元数据尚未准确批准或已变化")
        item = next((item for item in fresh["tools"] if item["name"] == tool), None)
        if item is None or not item["allowed"]:
            _fail("MCP_TOOL_DENIED", "该工具不在准确批准的程序只读清单")
        schema.validate(item["metadata"]["inputSchema"], arguments)
        packet = {"id": cid, "server_id": server_id, "server_revision": fresh["server_revision"], "session_id": fresh["session_id"],
                  "server_name": (await self._server(server_id))[0]["name"], "tool": tool, "arguments": arguments, "metadata": item["metadata"], "purpose": "调用已审查的只读 MCP 工具"}
        packet["revision"] = digest(packet)
        return _json(packet)

    async def call_preview(self, cid, server_id, tool, arguments):
        """准备准确参数、程序/会话和工具schema的预览，不执行 tools/call。"""
        packet = await self._call_packet(cid, server_id, tool, arguments)
        async with self._lock:
            async with self.store._lock:
                await self._alive(self.store._db(), cid)
                self._remember("call", packet)
        return packet

    def _result(self, sid, metadata, raw):
        self._no_echo(sid, raw)
        raw = _json(raw)
        if set(raw) - {"content", "structuredContent", "isError", "_meta"} or not isinstance(raw.get("content"), list) or len(raw["content"]) > 32 or ("isError" in raw and type(raw["isError"]) is not bool):
            _fail("MCP_RESULT", "工具结果结构包含未知字段或无效类型")
        if "structuredContent" in raw and not isinstance(raw["structuredContent"], dict):
            _fail("MCP_RESULT", "structuredContent 必须为JSON对象")
        if "_meta" in raw and not isinstance(raw["_meta"], dict):
            _fail("MCP_RESULT", "结果附加元数据须为JSON对象")
        for item in raw["content"]:
            if not isinstance(item, dict):
                _fail("MCP_RESULT", "内容项必须为JSON对象")
            annotations = item.get("annotations", {})
            if not isinstance(annotations, dict) or set(annotations) - {"audience", "priority", "lastModified"}:
                _fail("MCP_RESULT", "内容 annotations 包含未知字段或类型")
            if "audience" in annotations and (not isinstance(annotations["audience"], list) or len(annotations["audience"]) > 2 or any(role not in {"user", "assistant"} for role in annotations["audience"])):
                _fail("MCP_RESULT", "内容受众声明无效")
            if "priority" in annotations and (type(annotations["priority"]) not in (int, float) or not 0 <= annotations["priority"] <= 1):
                _fail("MCP_RESULT", "内容优先级声明无效")
            if "lastModified" in annotations and (not isinstance(annotations["lastModified"], str) or len(annotations["lastModified"]) > 100):
                _fail("MCP_RESULT", "内容修改时间声明无效")
            if "_meta" in item and not isinstance(item["_meta"], dict):
                _fail("MCP_RESULT", "内容附加元数据须为JSON对象")
            if item.get("type") == "text":
                if set(item) - {"type", "text", "annotations", "_meta"} or not isinstance(item.get("text"), str):
                    _fail("MCP_RESULT", "文本内容结构无效")
            elif item.get("type") == "resource_link":
                if set(item) - {"type", "uri", "name", "title", "description", "mimeType", "size", "annotations", "_meta"} or not isinstance(item.get("uri"), str) or not 1 <= len(item["uri"]) <= 2048 or not isinstance(item.get("name"), str):
                    _fail("MCP_RESULT", "资源链接结构无效")
                if urlsplit(item["uri"]).scheme.lower() in {"javascript", "data", "vbscript"}:
                    _fail("MCP_RESULT", "资源链接协议当前不支持")
                if len(item["name"]) > 100 or any(key in item and (not isinstance(item[key], str) or len(item[key]) > 4096) for key in ("title", "description", "mimeType")) or ("size" in item and (type(item["size"]) is not int or not 0 <= item["size"] <= 2**53 - 1)):
                    _fail("MCP_RESULT", "资源链接字段或长度无效")
            else:
                _fail("MCP_UNSUPPORTED_CONTENT", "image/audio/embedded 等结果当前不支持，未保存正文")
        if "outputSchema" in metadata:
            if "structuredContent" not in raw:
                _fail("MCP_RESULT_SCHEMA", "声明outputSchema的工具未返回structuredContent")
            schema.validate(metadata["outputSchema"], raw["structuredContent"])
        return raw

    @staticmethod
    def _execution(packet):
        return {"id": packet["id"], "server_id": packet["server_id"], "revision": packet["revision"], "server_name": packet["server_name"], "tool": packet["tool"], "status": "unknown", "result": None, "error": None}

    async def _save(self, cid, revision, execution):
        value = _json(execution)
        async with self.store._lock:
            db = self.store._db()
            await db.execute("BEGIN IMMEDIATE")
            try:
                await self._alive(db, cid)
                await db.execute("UPDATE mcp_attempts SET state=? WHERE cid=? AND revision=?", (execution["status"], cid, revision))
                await db.execute("INSERT OR REPLACE INTO mcp_executions VALUES(?,?,?)", (cid, revision, encoded(value)))
                await db.execute("DELETE FROM mcp_executions WHERE cid=? AND rowid NOT IN(SELECT rowid FROM mcp_executions WHERE cid=? ORDER BY rowid DESC LIMIT 32)", (cid, cid))
                await db.commit()
            except BaseException:
                await db.rollback();raise

    async def call(self, cid, server_id, revision):
        """60秒总预算包含前后工具重核，单个 tools/call 仍为20秒且不重试。"""
        try:
            return await asyncio.wait_for(self._call(cid, server_id, revision), CALL_SECONDS)
        except asyncio.TimeoutError:
            _fail("MCP_CALL_TIMEOUT", "MCP 调用60秒总预算已耗尽；网络后未知事实已保留，不自动重试")

    async def _call(self, cid, server_id, revision):
        """原生准确参数批准后一次调用；网络前落盘尝试，未知结果不自动重试。"""
        async with self._call_locks.setdefault((cid, revision), asyncio.Lock()):
            async with self.store._lock:
                db = self.store._db()
                await self._alive(db, cid)
                if await self._rows(db, "SELECT 1 FROM mcp_attempts WHERE cid=? AND revision=?", (cid, revision)):
                    _fail("MCP_ALREADY_ATTEMPTED", "本批已有调用事实，缓存或连接失效都不能授权重发")
            async with self._lock:
                rid, packet = self._find("call", server_id, revision)
                del self._reviews[rid]
            if packet["id"] != cid:
                _fail("MCP_CONVERSATION", "调用审批与会话身份不匹配")
            fresh = await self._call_packet(cid, server_id, packet["tool"], packet["arguments"])
            if fresh != packet:
                _fail("MCP_CHANGED", "调用参数、服务或工具准确版本已变化")
            execution = self._execution(packet)
            async with self.store._lock:
                db = self.store._db();await db.execute("BEGIN IMMEDIATE")
                try:
                    await self._alive(db, cid)
                    if await self._rows(db, "SELECT 1 FROM mcp_attempts WHERE cid=? AND revision=?", (cid, revision)):
                        _fail("MCP_ALREADY_ATTEMPTED", "本批已有调用事实，禁止重发")
                    if (await self._rows(db, "SELECT count(*) FROM mcp_attempts WHERE cid=?", (cid,)))[0][0] >= 128:
                        _fail("MCP_ATTEMPT_LIMIT", "本会话128次 MCP 尝试预算已用完")
                    await db.execute("INSERT INTO mcp_attempts VALUES(?,?,'running')", (cid, revision))
                    await db.execute("INSERT INTO mcp_executions VALUES(?,?,?)", (cid, revision, encoded(execution)))
                    await db.commit()
                except BaseException:
                    await db.rollback();raise
            handle = self._sessions.get(server_id)
            received = False
            try:
                if handle is None or handle["id"] != packet["session_id"]:
                    _fail("MCP_DISCONNECTED", "执行前连接已失效")
                raw = await asyncio.wait_for(handle["session"].request("tools/call", {"name": packet["tool"], "arguments": packet["arguments"]}), 20)
                received = True
                result = self._result(server_id, packet["metadata"], raw)
                current = await self._fresh(server_id)
                if current != self._approved.get(server_id) or current["session_id"] != packet["session_id"]:
                    _fail("MCP_TOOLS_CHANGED", "调用期间工具或连接变化，结果不能确认")
                execution.update(status="failed" if result.get("isError") else "completed", result=result,
                                 error={"code": "MCP_TOOL_ERROR", "message": "工具实际返回isError，未视为成功"} if result.get("isError") else None)
                if size(execution) > 32768:
                    _fail("MCP_LIMIT", "结果与事实信封合计超过32KiB")
            except asyncio.TimeoutError:
                execution.update(status="unknown", error={"code": "MCP_TIMEOUT", "message": "工具响应20秒超时，结果未知；不会自动重试"})
            except McpError as exc:
                status = "limited" if exc.code == "MCP_UNSUPPORTED_CONTENT" else ("unknown" if not received or exc.code in {"MCP_DISCONNECTED", "MCP_TOOLS_CHANGED", "MCP_CLOSED", "MCP_REQUEST", "MCP_TIMEOUT", "MCP_CANCELLED", "MCP_SESSION_EXPIRED", "MCP_SERVER_REQUEST", "MCP_TOOL_TIMEOUT", "MCP_PROGRAM_CHANGED", "MCP_SERVER"} else "failed")
                code = exc.code if isinstance(exc.code, str) and re.fullmatch(r"MCP_[A-Z_]{1,50}", exc.code) else "MCP_REQUEST"
                execution.update(status=status, result=None, error={"code": code, "message": "MCP 工具响应未通过当前协议、内容、来源或凭据保护核验；未确认成功"})
            except asyncio.CancelledError:
                execution.update(status="unknown", error={"code": "MCP_CANCELLED", "message": "调用已取消，结果未知；不会自动重试"})
                try:
                    await asyncio.shield(self._save(cid, revision, execution))
                except McpError:
                    pass
                try:
                    await asyncio.shield(self.disconnect(server_id))
                except (McpError, OSError, RuntimeError):
                    pass
                raise
            except (OSError, ValueError, RuntimeError):
                execution.update(status="unknown", result=None, error={"code": "MCP_REQUEST", "message": "工具连接异常，结果未知；不会自动重试"})
            if execution["status"] == "unknown":
                try:
                    await self.disconnect(server_id)
                except (McpError, OSError, RuntimeError):
                    pass
            await self._save(cid, revision, execution)
            return execution

    async def history(self, cid):
        """最近16条/32KiB实际调用事实；不读取远端、不恢复调用许可。"""
        async with self.store._lock:
            db = self.store._db();await self._alive(db, cid)
            rows = await self._rows(db, "SELECT data_json FROM mcp_executions WHERE cid=? ORDER BY rowid DESC LIMIT 16", (cid,))
        result = {"executions": []}
        for row in rows:
            value = json.loads(row[0])
            if size({"executions": [*result["executions"], value]}) > 32768:
                break
            result["executions"].append(value)
        return result

    async def disconnect(self, server_id):
        """先失效全部许可再关闭连接；stdio 后代回收事实来自传输 Job，不能猜成功。"""
        await self._server(server_id)
        self._epochs[server_id] = str(uuid4())
        self._invalidate(server_id)
        handle = self._sessions.pop(server_id, None)
        self._states[server_id] = ("disconnected", None)
        result = await handle["session"].close() if handle else {"closed": True, "children_reaped": True}
        if not result.get("closed") or not result.get("children_reaped"):
            self._states[server_id] = ("error", "MCP_CLOSE_UNCERTAIN")
            if handle:
                self._sessions[server_id] = handle
        async with self.store._lock:
            await self.store._db().execute("UPDATE mcp_tool_reviews SET state='expired' WHERE sid=?", (server_id,))
        return {"server_id": server_id, "closed": bool(result.get("closed")), "children_reaped": bool(result.get("children_reaped"))}

    async def remove(self, server_id):
        """明确移除配置前先关闭连接，不删除所属会话的真实调用历史。"""
        closed = await self.disconnect(server_id)
        if not closed["closed"] or not closed["children_reaped"]:
            _fail("MCP_CLOSE_UNCERTAIN", "连接或后代回收未确认，配置未移除")
        async with self.store._lock:
            db = self.store._db()
            await db.execute("DELETE FROM mcp_tool_reviews WHERE sid=?", (server_id,))
            await db.execute("DELETE FROM mcp_servers WHERE sid=?", (server_id,))
        self._credentials.pop(server_id, None);self._states.pop(server_id, None)
        return {"server_id": server_id, "removed": True}

    async def replace_credential(self, server_id, credential):
        """独立HTTPS Bearer仅内存；更新先断连撤销旧审批，绝不复用角色Key或写SQLite。"""
        config, _, _ = await self._server(server_id)
        if config["transport"] != "https":
            _fail("MCP_CREDENTIAL", "stdio 不接受凭据或环境注入")
        if credential is not None and (not isinstance(credential, str) or not 1 <= len(credential) <= 4096 or any(ord(c) < 33 or ord(c) > 126 for c in credential)):
            _fail("MCP_CREDENTIAL", "独立Bearer须为最多4096字节的单行普通ASCII值")
        await self.disconnect(server_id)
        if credential is None:
            self._credentials.pop(server_id, None)
        else:
            self._credentials[server_id] = credential
        return await self._summary(server_id)

    def forget_previews(self, cid):
        """会话撤回仅清正文准备许可，不把缓存清理当调用完成或允许未知重发。"""
        for rid, review in list(self._reviews.items()):
            if review["value"].get("id") == cid:
                del self._reviews[rid]

    async def close(self):
        """应用关闭时回收所有已启动连接与凭据，只汇总传输实际关闭事实。"""
        reports = []
        for sid in list(self._sessions):
            reports.append(await self.disconnect(sid))
        self._credentials.clear();self._reviews.clear();self._approved.clear()
        return {"closed": all(report["closed"] for report in reports), "children_reaped": all(report["children_reaped"] for report in reports)}
