"""版本化 Skills 注册和 LangGraph 顺序执行，SQLite 保存执行事实。"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from time import monotonic
from typing import TypedDict
from uuid import UUID, uuid4

from langgraph.graph import END, START, StateGraph

from ..computer.contracts import DirectoryArgs, PathArgs, ReadArgs, SearchArgs, SpaceArgs
from ..computer.paths import PathPolicy, ToolError
from ..storage import Store


TOOLS = {"list_directory": DirectoryArgs, "search_files": SearchArgs,
         "get_file_metadata": PathArgs, "analyze_directory_space": SpaceArgs,
         "read_text_file": ReadArgs}
RESERVED = {"mission_id", "grant_id", "role", "approval", "approved", "token", "permissions",
            "model", "base_url", "api_key", "command", "script", "expression"}
IDENTIFIER = re.compile(r"[a-z][a-z0-9-]{1,63}\Z")
VERSION = re.compile(r"[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}\Z")
OPEN_OBJECT = {"type": "object", "additionalProperties": True}
OUTPUT_LIMIT = 32 * 1024


class SkillError(ValueError):
    """稳定错误代码供受限 IPC 映射；消息不带包正文或系统异常细节。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def _fail(code, message):
    raise SkillError(code, message)


def _json(value):
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError, RecursionError):
        _fail("SKILL_CONTRACT", "工作流或结果必须为有限 JSON 数据")


def _size(value):
    try:
        return len(_json(value).encode("utf-8"))
    except UnicodeEncodeError:
        _fail("SKILL_CONTRACT", "结构化内容包含无效 Unicode 字符")


def _strict_json(payload):
    """拒绝重复键及 NaN，防止预览和执行对同一声明产生不同解释。"""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                _fail("SKILL_CONTRACT", "工作流 JSON 不允许重复字段")
            result[key] = value
        return result

    try:
        return json.loads(payload, object_pairs_hook=pairs,
                          parse_constant=lambda _: _fail("SKILL_CONTRACT", "工作流不允许非有限数字"))
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError):
        _fail("SKILL_CONTRACT", "工作流不是有效的 UTF-8 JSON")


def _schema(schema, depth=0):
    """Orvia v1 只支持有界 object/string/integer/boolean；不接受引用或执行表达式。"""
    if depth > 6 or not isinstance(schema, dict):
        _fail("SKILL_SCHEMA", "schema 嵌套超过6层或类型无效")
    kind = schema.get("type")
    allowed = {"type", "description"}
    if kind == "object":
        allowed |= {"properties", "required", "additionalProperties"}
        properties, required = schema.get("properties", {}), schema.get("required", [])
        if (not isinstance(properties, dict) or len(properties) > 32 or not isinstance(required, list)
                or any(not isinstance(k, str) or k not in properties for k in required)
                or len(set(required)) != len(required)
                or type(schema.get("additionalProperties", False)) is not bool):
            _fail("SKILL_SCHEMA", "object schema 字段、必填项或额外字段约束无效")
        for key, child in properties.items():
            if not isinstance(key, str) or not 1 <= len(key) <= 100 or key.lower() in RESERVED:
                _fail("SKILL_SCHEMA", "schema 不能声明权限、模型或脚本字段")
            _schema(child, depth + 1)
    elif kind == "string":
        allowed |= {"minLength", "maxLength", "enum"}
        for key in ("minLength", "maxLength"):
            if key in schema and (type(schema[key]) is not int or not 0 <= schema[key] <= 8000):
                _fail("SKILL_SCHEMA", "字符串长度约束无效")
        if schema.get("minLength", 0) > schema.get("maxLength", 8000):
            _fail("SKILL_SCHEMA", "字符串长度上下限不匹配")
    elif kind == "integer":
        allowed |= {"minimum", "maximum", "enum"}
        for key in ("minimum", "maximum"):
            if key in schema and (type(schema[key]) is not int or abs(schema[key]) > 2**53 - 1):
                _fail("SKILL_SCHEMA", "整数范围无效")
        if schema.get("minimum", -(2**53 - 1)) > schema.get("maximum", 2**53 - 1):
            _fail("SKILL_SCHEMA", "整数上下限不匹配")
    elif kind == "boolean":
        allowed |= {"enum"}
    else:
        _fail("SKILL_SCHEMA", "仅支持 object/string/integer/boolean schema")
    if set(schema) - allowed or ("description" in schema and (not isinstance(schema["description"], str) or len(schema["description"]) > 500)):
        _fail("SKILL_SCHEMA", "schema 含不支持的字段")
    if "enum" in schema:
        enum = schema["enum"]
        expected = {"string": str, "integer": int, "boolean": bool}.get(kind)
        if not isinstance(enum, list) or not 1 <= len(enum) <= 32 or any(type(x) is not expected for x in enum):
            _fail("SKILL_SCHEMA", "枚举约束无效")


def _validate(schema, value):
    kind = schema["type"]
    expected = {"object": dict, "string": str, "integer": int, "boolean": bool}[kind]
    if type(value) is not expected:
        _fail("SKILL_CONTRACT", "输入或输出类型不符合已批准 schema")
    if kind == "object":
        props = schema.get("properties", {})
        if any(k not in value for k in schema.get("required", [])):
            _fail("SKILL_CONTRACT", "输入或输出缺少必填字段")
        if not schema.get("additionalProperties", False) and set(value) - set(props):
            _fail("SKILL_CONTRACT", "输入或输出包含未声明字段")
        for key in set(value) & set(props):
            _validate(props[key], value[key])
    if kind == "string" and not schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", 8000):
        _fail("SKILL_CONTRACT", "字符串超出 schema 长度预算")
    if kind == "integer" and not schema.get("minimum", -(2**53 - 1)) <= value <= schema.get("maximum", 2**53 - 1):
        _fail("SKILL_CONTRACT", "整数超出 schema 范围")
    if "enum" in schema and value not in schema["enum"]:
        _fail("SKILL_CONTRACT", "值不在 schema 枚举范围内")


def _binding(value, input_names, previous, depth=0):
    """结构化引用只有已声明输入和先前步骤；不能引用将来节点或执行任意表达式。"""
    if depth > 8:
        _fail("SKILL_CONTRACT", "参数结构超过8层")
    if isinstance(value, dict):
        if "from_input" in value:
            if set(value) != {"from_input"} or not isinstance(value["from_input"], str) or value["from_input"] not in input_names:
                _fail("SKILL_CONTRACT", "输入引用不存在或包含额外字段")
            return
        if "from_step" in value:
            path = value.get("path", [])
            if (set(value) - {"from_step", "path"} or not isinstance(value["from_step"], str) or value["from_step"] not in previous
                    or not isinstance(path, list) or len(path) > 8
                    or any(type(p) not in (str, int) or isinstance(p, int) and p < 0 for p in path)):
                _fail("SKILL_CONTRACT", "步骤引用必须指向先前节点及有界路径")
            return
        for key, child in value.items():
            if key.lower() in RESERVED:
                _fail("SKILL_PERMISSION", "工作流参数不能提供权限、模型或可执行代码")
            _binding(child, input_names, previous, depth + 1)
    elif type(value) not in (str, int, bool) and value is not None:
        _fail("SKILL_CONTRACT", "参数只允许结构化 object 与标量")
    if isinstance(value, str) and len(value) > 8000:
        _fail("SKILL_CONTRACT", "参数字符串超过预算")


def _manifest(value):
    fields = {"schema_version", "id", "name", "version", "description", "input_schema", "output_schema", "dependencies", "steps", "output"}
    if not isinstance(value, dict) or set(value) != fields or type(value["schema_version"]) is not int or value["schema_version"] != 1:
        _fail("SKILL_CONTRACT", "包必须提供 Orvia workflow schema_version=1 的全部固定字段")
    if (not isinstance(value["id"], str) or not IDENTIFIER.fullmatch(value["id"])
            or not isinstance(value["version"], str) or not VERSION.fullmatch(value["version"])):
        _fail("SKILL_CONTRACT", "Skill ID 或版本格式无效")
    for key, maximum in (("name", 100), ("description", 1000)):
        text = value[key]
        if (not isinstance(text, str) or not 1 <= len(text.encode("utf-16-le", errors="surrogatepass")) // 2 <= maximum
                or any(ord(char) < 32 or ord(char) == 127 or 0xD800 <= ord(char) <= 0xDFFF for char in text)):
            _fail("SKILL_CONTRACT", "名称或说明超过预算")
    for key in ("input_schema", "output_schema"):
        _schema(value[key])
        if value[key]["type"] != "object":
            _fail("SKILL_SCHEMA", "Skill 输入输出必须为 object")
    if value["input_schema"].get("additionalProperties", False):
        _fail("SKILL_SCHEMA", "Skill 输入不允许额外字段")
    deps, steps = value["dependencies"], value["steps"]
    if (not isinstance(deps, list) or len(deps) > 16 or any(not isinstance(x, str) or not IDENTIFIER.fullmatch(x) for x in deps)
            or len(set(deps)) != len(deps) or value["id"] in deps):
        _fail("SKILL_DEPENDENCY", "依赖必须为最多16个不同 Skill ID，不能依赖自身")
    if not isinstance(steps, list) or not 1 <= len(steps) <= 16:
        _fail("SKILL_CONTRACT", "工作流必须为1～16个声明式节点")
    previous = set()
    for step in steps:
        if not isinstance(step, dict) or set(step) not in ({"id", "tool", "arguments", "output_schema"}, {"id", "skill", "arguments", "output_schema"}):
            _fail("SKILL_CONTRACT", "节点只允许 tool 或 skill 及固定声明字段")
        sid = step["id"]
        if not isinstance(sid, str) or not IDENTIFIER.fullmatch(sid) or sid in previous:
            _fail("SKILL_CONTRACT", "节点 ID 无效或重复")
        if "tool" in step and (not isinstance(step["tool"], str) or step["tool"] not in TOOLS):
            _fail("SKILL_TOOL", "该工具未在 V4-002 只读允许清单中")
        if "skill" in step and (not isinstance(step["skill"], str) or step["skill"] not in deps):
            _fail("SKILL_DEPENDENCY", "组合 Skill 必须先声明依赖")
        if not isinstance(step["arguments"], dict):
            _fail("SKILL_CONTRACT", "节点参数必须为 object")
        _binding(step["arguments"], value["input_schema"].get("properties", {}), previous)
        _schema(step["output_schema"])
        previous.add(sid)
    if not isinstance(value["output"], dict):
        _fail("SKILL_CONTRACT", "输出映射必须为 object")
    _binding(value["output"], value["input_schema"].get("properties", {}), previous)
    return value


def _get(value, path, clone=True):
    for token in path:
        try:
            if isinstance(value, dict) and isinstance(token, str):
                value = value[token]
            elif isinstance(value, list) and type(token) is int:
                value = value[token]
            else:
                _fail("SKILL_REFERENCE", "引用路径类型不匹配")
        except (KeyError, IndexError):
            _fail("SKILL_REFERENCE", "引用结果缺少已声明路径")
    return copy.deepcopy(value) if clone else value


def _reserve(value, budget, limit):
    """复制引用之前扣统一字节预算，阻止少量叶节点的重复输出映射指数展开。"""
    size = _size(value)
    if budget[0] + size > limit:
        _fail("SKILL_LIMIT", "组合引用展开超过结构字节预算")
    budget[0] += size


def _resolve(value, inputs, results, budget=None):
    budget = [0] if budget is None else budget
    if isinstance(value, dict):
        if "from_input" in value:
            if value["from_input"] not in inputs:
                _fail("SKILL_REFERENCE", "可选输入未提供，不能解析节点引用")
            source = inputs[value["from_input"]]
            _reserve(source, budget, OUTPUT_LIMIT)
            return copy.deepcopy(source)
        if "from_step" in value:
            if value["from_step"] not in results:
                _fail("SKILL_REFERENCE", "步骤结果尚未存在")
            source = _get(results[value["from_step"]], value.get("path", []), clone=False)
            _reserve(source, budget, OUTPUT_LIMIT)
            return copy.deepcopy(source)
        _reserve({k: None for k in value}, budget, OUTPUT_LIMIT)
        return {k: _resolve(v, inputs, results, budget) for k, v in value.items()}
    _reserve(value, budget, OUTPUT_LIMIT)
    return copy.deepcopy(value)


def _expand_binding(value, inputs, previous, budget=None):
    """组合计划将局部引用转换为唯一叶节点引用，批准后不再读取包文件。"""
    budget = [0] if budget is None else budget
    if isinstance(value, dict):
        if "from_input" in value:
            if value["from_input"] not in inputs:
                _fail("SKILL_REFERENCE", "计划需要的可选输入未提供")
            _reserve(inputs[value["from_input"]], budget, 16 * 1024)
            return copy.deepcopy(inputs[value["from_input"]])
        if "from_step" in value:
            _reserve(previous[value["from_step"]], budget, 16 * 1024)
            source = copy.deepcopy(previous[value["from_step"]])
            path = value.get("path", [])
            while path and isinstance(source, dict) and "from_step" not in source:
                source = _get(source, path[:1])
                path = path[1:]
            if path:
                if not isinstance(source, dict) or "from_step" not in source:
                    return _get(source, path)
                source["path"] = source.get("path", []) + path
            return source
        _reserve({k: None for k in value}, budget, 16 * 1024)
        return {k: _expand_binding(v, inputs, previous, budget) for k, v in value.items()}
    _reserve(value, budget, 16 * 1024)
    return copy.deepcopy(value)


def _builtin():
    inputs = {"type": "object", "properties": {"path": {"type": "string", "minLength": 1, "maxLength": 1000}}, "required": ["path"]}
    manifest = {"schema_version": 1, "id": "file-organize", "name": "File Organize", "version": "1.0.0",
                "description": "读取一级文件清单和空间统计；此工作流不移动、重命名或删除文件。", "input_schema": inputs,
                "output_schema": {"type": "object", "properties": {"inventory": OPEN_OBJECT, "space": OPEN_OBJECT}, "required": ["inventory", "space"]},
                "dependencies": [], "steps": [
                    {"id": "inventory", "tool": "list_directory", "arguments": {"path": {"from_input": "path"}, "limit": 40}, "output_schema": OPEN_OBJECT},
                    {"id": "space", "tool": "analyze_directory_space", "arguments": {"path": {"from_input": "path"}, "top_n": 5}, "output_schema": OPEN_OBJECT}],
                "output": {"inventory": {"from_step": "inventory"}, "space": {"from_step": "space"}}}
    yield manifest, None
    for sid, name, reason in (("memory-context", "Memory Context", "V4-003本地记忆已实现；声明式组合入口待V4-006接入"),
                              ("query-rewrite", "Query Rewrite", "等待 V4-006 查询改写实现"),
                              ("web-research", "Web Research", "等待 V4-010 多来源调研实现"),
                              ("report-build", "Report Build", "等待 V4-010 简报组合实现")):
        yield {**manifest, "id": sid, "name": name, "description": reason}, reason


class GraphState(TypedDict):
    index: int
    stopped: bool


class SkillsService:
    """注册事实持久化，审查和授权只在内存；重启不执行旧计划或恢复旧权限。"""

    def __init__(self, store: Store):
        self.store = store
        self._reviews = {}
        self._plans = {}
        self._lock = asyncio.Lock()

    async def open(self):
        """追加独立表而不改变已有业务 user_version；未知执行一律标为 interrupted。"""
        async with self.store._lock:
            db = self.store._db()
            await db.execute("BEGIN IMMEDIATE")
            try:
                await self._migrate(db)
                await db.commit()
            except BaseException:
                await db.rollback()
                raise

    async def _migrate(self, db):
        await db.execute("""CREATE TABLE IF NOT EXISTS skills_registry(
            id TEXT PRIMARY KEY,version TEXT NOT NULL,revision TEXT NOT NULL,manifest_json TEXT NOT NULL,
            documentation TEXT NOT NULL,enabled INTEGER NOT NULL,builtin INTEGER NOT NULL,reason TEXT,
            generation INTEGER NOT NULL DEFAULT 1)""")
        async with db.execute("PRAGMA table_info(skills_registry)") as cursor:
            columns = {row[1] for row in await cursor.fetchall()}
        if "generation" not in columns:
            await db.execute("ALTER TABLE skills_registry ADD COLUMN generation INTEGER NOT NULL DEFAULT 1")
        await db.execute("""CREATE TABLE IF NOT EXISTS skills_executions(
            plan_id TEXT PRIMARY KEY,mission_id TEXT NOT NULL,revision TEXT NOT NULL,status TEXT NOT NULL,
            plan_json TEXT NOT NULL,result_json TEXT NOT NULL)""")
        for manifest, reason in _builtin():
            content = _json(manifest)
            revision = hashlib.sha256(content.encode()).hexdigest()
            await db.execute("INSERT OR IGNORE INTO skills_registry VALUES(?,?,?,?,?,1,1,?,1)",
                             (manifest["id"], manifest["version"], revision, content, manifest["description"], reason))
        async with db.execute("SELECT plan_id,result_json FROM skills_executions WHERE status IN ('running','planned')") as cursor:
            rows = await cursor.fetchall()
        for pid, result in rows:
            result = json.loads(result)
            result.update(status="interrupted", error={"code": "SKILL_INTERRUPTED", "message": "连接已中断；结果未知，不自动重试或续接"})
            await db.execute("UPDATE skills_executions SET status='interrupted',result_json=? WHERE plan_id=?", (_json(result), pid))

    async def _records(self):
        async with self.store._lock:
            async with self.store._db().execute("SELECT id,version,revision,manifest_json,enabled,builtin,reason,generation FROM skills_registry ORDER BY builtin DESC,id") as cursor:
                rows = await cursor.fetchall()
        return {row[0]: {"id": row[0], "version": row[1], "revision": row[2], "manifest": json.loads(row[3]),
                         "enabled": bool(row[4]), "builtin": bool(row[5]), "reason": row[6], "generation": row[7]} for row in rows}

    @staticmethod
    def _dependency_graph(sid, records, stack=()):
        """登记时检查完整依赖拓扑；已禁用节点不能遮蔽循环或层数越界。"""
        if sid not in records:
            return
        if sid in stack:
            _fail("SKILL_DEPENDENCY", "Skill 依赖存在循环")
        if len(stack) >= 4:
            _fail("SKILL_DEPENDENCY", "Skill 组合超过4层")
        for dep in records[sid]["manifest"]["dependencies"]:
            SkillsService._dependency_graph(dep, records, (*stack, sid))

    @staticmethod
    def _ready(sid, records, stack=()):
        if sid not in records:
            return "依赖 Skill 未登记：" + sid
        if sid in stack:
            return "Skill 依赖存在循环"
        if len(stack) >= 4:
            return "Skill 组合超过4层"
        record = records[sid]
        if not record["enabled"]:
            return "Skill 已禁用：" + sid
        if record["reason"]:
            return record["reason"]
        for dep in record["manifest"]["dependencies"]:
            reason = SkillsService._ready(dep, records, (*stack, sid))
            if reason:
                return reason
        return None

    @classmethod
    def _summary(cls, record, records):
        m = record["manifest"]
        reason = cls._ready(record["id"], records)
        return {"id": record["id"], "name": m["name"], "version": record["version"], "revision": record["revision"],
                "description": m["description"], "enabled": record["enabled"], "builtin": record["builtin"],
                "available": reason is None, "unavailable_reason": reason, "dependencies": m["dependencies"], "step_count": len(m["steps"])}

    async def list(self, offset=0):
        """每页最多10项，完整长中文说明也不会挤破 stdio 单行通信预算。"""
        if type(offset) is not int or not 0 <= offset <= 36:
            _fail("SKILL_CONTRACT", "列表偏移必须为0～36")
        records = await self._records()
        rows = list(records.values())
        return {"skills": [self._summary(r, records) for r in rows[offset:offset + 10]], "offset": offset, "total": len(rows)}

    @staticmethod
    def _package(path):
        """两个普通文件总计64KiB，逐级拒绝链接/重解析点并用打开句柄核对文件身份。"""
        root = Path(path)
        if not root.is_absolute():
            _fail("SKILL_PACKAGE", "包目录必须由原生选择器提供绝对路径")
        def checked(target, directory=False):
            info = target.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                _fail("SKILL_PACKAGE", "包不允许符号链接或重解析点")
            if directory and not stat.S_ISDIR(info.st_mode) or not directory and not stat.S_ISREG(info.st_mode):
                _fail("SKILL_PACKAGE", "包只允许目录和普通文件")
            return info
        def names_bounded():
            names = set()
            with os.scandir(root) as entries:
                for entry in entries:
                    names.add(entry.name)
                    if len(names) > 2:
                        _fail("SKILL_PACKAGE", "包不允许额外文件或子目录")
            return names
        try:
            for parent in (*reversed(root.parents), root):
                checked(parent, True)
            policy = PathPolicy(str(root))
            names = names_bounded()
            if names != {"SKILL.md", "workflow.json"}:
                _fail("SKILL_PACKAGE", "包顶层必须恰好包含 SKILL.md 和 workflow.json；脚本及子目录不允许")
            payloads, total = [], 0
            for name in ("SKILL.md", "workflow.json"):
                target = root / name
                policy.resolve(name, "file")
                before = checked(target)
                limit = 8 * 1024 if name == "SKILL.md" else 16 * 1024
                if before.st_size > limit:
                    _fail("SKILL_PACKAGE", "SKILL.md 最多8KiB，workflow.json 最多16KiB")
                with target.open("rb") as stream:
                    opened = policy.validate_open_file(stream.fileno(), target)
                    if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
                        _fail("SKILL_CHANGED", "包文件在打开时已变化")
                    payload = stream.read(64 * 1024 + 1)
                    after = checked(target)
                    policy.validate_open_file(stream.fileno(), target)
                    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
                        _fail("SKILL_CHANGED", "包在读取期间已变化")
                total += len(payload)
                if total > 64 * 1024:
                    _fail("SKILL_PACKAGE", "包两文件合计超过64KiB预算")
                payloads.append(payload)
            if names_bounded() != names:
                _fail("SKILL_CHANGED", "包目录在读取期间已变化")
            documentation = payloads[0].decode("utf-8-sig")
            if not documentation.strip():
                _fail("SKILL_PACKAGE", "SKILL.md 说明不能为空")
            manifest = _manifest(_strict_json(payloads[1].decode("utf-8-sig")))
            revision = hashlib.sha256(payloads[0] + b"\0" + payloads[1]).hexdigest()
            if _size({"documentation": documentation, "manifest": manifest}) > 32 * 1024:
                _fail("SKILL_PACKAGE", "审查正文与声明超过32KiB通信预算")
            return manifest, documentation, revision
        except (OSError, UnicodeDecodeError, ToolError):
            _fail("SKILL_PACKAGE", "无法安全读取 UTF-8 普通文件包")

    async def preview_import(self, path):
        """审查仅解析声明，不加载模块、不安装依赖、不执行说明中的任何指令。"""
        async with self._lock:
            if len(self._reviews) >= 16:
                self._reviews.pop(next(iter(self._reviews)))
            manifest, documentation, revision = await asyncio.to_thread(self._package, path)
            records = await self._records()
            sid = manifest["id"]
            if sid in records and records[sid]["builtin"]:
                _fail("SKILL_BUILTIN", "导入包不能覆盖内置 Skill")
            if sid not in records and sum(not r["builtin"] for r in records.values()) >= 32:
                _fail("SKILL_LIMIT", "最多登记32个导入 Skill")
            records[sid] = {"id": sid, "manifest": manifest, "enabled": True, "reason": None}
            self._dependency_graph(sid, records)
            reason = self._ready(sid, records)
            if reason and "未登记" not in reason and "等待 V4" not in reason and "已禁用" not in reason:
                _fail("SKILL_DEPENDENCY", reason)
            rid = str(uuid4())
            self._reviews[rid] = {"path": path, "revision": revision, "manifest": manifest, "documentation": documentation,
                                  "prior_revision": (await self._records()).get(sid, {}).get("revision")}
            return {"review_id": rid, "revision": revision, "manifest": copy.deepcopy(manifest), "documentation": documentation,
                    "warnings": [reason] if reason else []}

    async def register(self, review_id, revision):
        """原生确认绑定审查hash，重新读取包并核对登记前版本，防止旧确认批准新内容。"""
        async with self._lock:
            review = self._reviews.pop(review_id, None)
            if review is None or review["revision"] != revision:
                _fail("SKILL_REVIEW", "审查已失效，请重新选择并确认")
            manifest, documentation, current = await asyncio.to_thread(self._package, review["path"])
            if current != revision:
                _fail("SKILL_CHANGED", "包内容已变化，旧审查不可注册")
            records = await self._records()
            sid = manifest["id"]
            existing = records.get(sid)
            if (existing or {}).get("revision") != review["prior_revision"]:
                _fail("SKILL_CHANGED", "登记版本已变化，请重新审查")
            if existing and existing["version"] == manifest["version"] and existing["revision"] != revision:
                _fail("SKILL_VERSION", "更新内容必须使用不同版本")
            if sid not in records and sum(not r["builtin"] for r in records.values()) >= 32:
                _fail("SKILL_LIMIT", "最多登记32个导入 Skill")
            candidate = {"id": sid, "version": manifest["version"], "revision": revision, "manifest": manifest,
                         "enabled": True, "builtin": False, "reason": None, "generation": (existing or {}).get("generation", 0) + 1}
            records[sid] = candidate
            self._dependency_graph(sid, records)
            reason = self._ready(sid, records)
            if reason and ("循环" in reason or "超过" in reason):
                _fail("SKILL_DEPENDENCY", reason)
            async with self.store._lock:
                await self.store._db().execute("""INSERT INTO skills_registry VALUES(?,?,?,?,?,1,0,NULL,1)
                    ON CONFLICT(id) DO UPDATE SET version=excluded.version,revision=excluded.revision,
                    manifest_json=excluded.manifest_json,documentation=excluded.documentation,enabled=1,
                    generation=skills_registry.generation+1""",
                    (sid, manifest["version"], revision, _json(manifest), documentation))
            return self._summary(candidate, records)

    async def set_enabled(self, skill_id, enabled):
        """禁用即时阻止后续叶节点；重新启用不会恢复已消耗的执行审批。"""
        if type(enabled) is not bool:
            _fail("SKILL_CONTRACT", "enabled 必须为布尔值")
        async with self._lock:
            records = await self._records()
            if skill_id not in records:
                _fail("SKILL_NOT_FOUND", "Skill 未登记")
            async with self.store._lock:
                await self.store._db().execute("UPDATE skills_registry SET enabled=?,generation=generation+1 WHERE id=? AND enabled<>?", (int(enabled), skill_id, int(enabled)))
            records[skill_id]["enabled"] = enabled
            return self._summary(records[skill_id], records)

    async def plan(self, skill_id, inputs, mission_id, grant_id):
        """计划绑定版本、任务和授权身份；声明只产生只读调用计划，不产生访问许可。"""
        async with self._lock:
            try:
                mission_id, grant_id = str(UUID(str(mission_id))), str(UUID(str(grant_id)))
            except (ValueError, TypeError):
                _fail("SKILL_PERMISSION", "计划缺少有效任务或授权身份")
            records = await self._records()
            reason = self._ready(skill_id, records)
            if reason:
                _fail("SKILL_UNAVAILABLE", reason)
            _validate(records[skill_id]["manifest"]["input_schema"], inputs)
            if _size(inputs) > 8 * 1024:
                _fail("SKILL_LIMIT", "Skill 输入超过8KiB预算")
            steps, checks, bindings = [], [], {}
            def guard_private():
                if _size({"steps": steps, "checks": checks, "bindings": bindings}) > 40 * 1024:
                    _fail("SKILL_LIMIT", "完整计划含私有契约校验超过40KiB预算")

            def expand(sid, values, prefix, stack=()):
                if len(stack) >= 4 or sid in stack:
                    _fail("SKILL_DEPENDENCY", "组合超过4层或存在循环")
                record, previous = records[sid], {}
                bindings[sid] = {"id": sid, "version": record["version"], "revision": record["revision"], "generation": record["generation"]}
                # 声明但未被调用的依赖也绑定，避免批准后依赖版本变化被忽略。
                def bind_deps(dep):
                    r = records[dep]
                    bindings[dep] = {"id": dep, "version": r["version"], "revision": r["revision"], "generation": r["generation"]}
                    for child in r["manifest"]["dependencies"]:
                        bind_deps(child)
                for dep in record["manifest"]["dependencies"]:
                    bind_deps(dep)
                m = record["manifest"]
                checks.append({"before": len(steps), "schema": m["input_schema"], "value": copy.deepcopy(values)})
                guard_private()
                for node in m["steps"]:
                    nid = prefix + node["id"]
                    args = _expand_binding(node["arguments"], values, previous)
                    if "skill" in node:
                        output = expand(node["skill"], args, nid + "/", (*stack, sid))
                        checks.append({"after": len(steps) - 1, "schema": node["output_schema"], "value": output})
                        previous[node["id"]] = output
                    else:
                        steps.append({"id": nid, "tool": node["tool"], "arguments": args, "output_schema": node["output_schema"]})
                        previous[node["id"]] = {"from_step": nid}
                    if len(steps) > 32:
                        _fail("SKILL_LIMIT", "组合总计超过32个工具步骤")
                    guard_private()
                output = _expand_binding(m["output"], values, previous)
                checks.append({"after": len(steps) - 1, "schema": m["output_schema"], "value": output})
                guard_private()
                return output

            output = expand(skill_id, inputs, "")
            # 结构绑定没有晚到权限；可立即解析的参数在原生确认前按现有网关契约校验。
            for step in steps:
                if "from_step" not in _json(step["arguments"]):
                    try:
                        TOOLS[step["tool"]].model_validate(step["arguments"])
                    except ValueError:
                        _fail("SKILL_CONTRACT", "节点参数不符合现有只读工具契约")
            pid = str(uuid4())
            result = {"plan_id": pid, "skill_id": skill_id, "version": records[skill_id]["version"],
                      "mission_id": mission_id, "grant_id": grant_id, "inputs": copy.deepcopy(inputs), "steps": steps,
                      "bindings": list(bindings.values()), "status": "planned"}
            if _size(result) > 40 * 1024:
                _fail("SKILL_LIMIT", "执行计划超过40KiB通信预算")
            result["revision"] = hashlib.sha256(_json(result).encode()).hexdigest()
            self._plans[pid] = {"public": copy.deepcopy(result), "checks": checks, "output": output}
            if len(self._plans) > 64:
                self._plans.pop(next(iter(self._plans)))
            execution = self._execution(result)
            await self._save(result, execution, insert=True)
            return result

    @staticmethod
    def _execution(plan):
        return {key: plan[key] for key in ("plan_id", "revision", "skill_id", "version", "mission_id", "grant_id")} | {"status": "planned", "steps": [], "output": None, "error": None}

    async def _save(self, plan, result, insert=False):
        async with self.store._lock:
            db = self.store._db()
            if insert:
                await db.execute("INSERT INTO skills_executions VALUES(?,?,?,?,?,?)", (plan["plan_id"], plan["mission_id"], plan["revision"], result["status"], _json(plan), _json(result)))
            else:
                await db.execute("UPDATE skills_executions SET status=?,result_json=? WHERE plan_id=?", (result["status"], _json(result), plan["plan_id"]))

    async def get_execution(self, plan_id):
        """只读返回已落库事实，不恢复计划、重播步骤或重建授权。"""
        async with self.store._lock:
            async with self.store._db().execute("SELECT result_json FROM skills_executions WHERE plan_id=?", (plan_id,)) as cursor:
                row = await cursor.fetchone()
        if not row:
            _fail("SKILL_NOT_FOUND", "执行记录不存在")
        return json.loads(row[0])

    async def history(self):
        """最近20项只返回随机身份与状态，正文和授权token须按准确计划查询。"""
        async with self.store._lock:
            async with self.store._db().execute("SELECT plan_id,status,result_json FROM skills_executions ORDER BY rowid DESC LIMIT 20") as cursor:
                rows = await cursor.fetchall()
        return {"executions": [{"plan_id": pid, "skill_id": json.loads(result)["skill_id"],
                                "version": json.loads(result)["version"], "status": status} for pid, status, result in rows]}

    async def cancel(self, plan_id, revision, mission_id, grant_id):
        """原生审批取消消费一次计划并记录事实；包或结果不能撤销已发生的工具读取。"""
        async with self._lock:
            private = self._plans.pop(plan_id, None)
            if private is None:
                _fail("SKILL_PLAN", "计划不存在、已执行或重启失效")
            plan = private["public"]
            result = self._execution(plan)
            if (revision != plan["revision"] or str(mission_id) != plan["mission_id"] or str(grant_id) != plan["grant_id"]):
                result.update(status="failed", error={"code": "SKILL_PERMISSION", "message": "取消身份与计划不匹配"})
                await self._save(plan, result)
                _fail("SKILL_PERMISSION", "取消身份与计划不匹配")
            result.update(status="interrupted", error={"code": "SKILL_CANCELLED", "message": "原生审批已取消；未调用任何工具"})
            await self._save(plan, result)
            return result

    async def _check_bindings(self, plan):
        records = await self._records()
        for binding in plan["bindings"]:
            current = records.get(binding["id"])
            if (current is None or current["version"] != binding["version"] or current["revision"] != binding["revision"]
                    or current["generation"] != binding["generation"] or self._ready(binding["id"], records)):
                _fail("SKILL_CHANGED", "Skill 或依赖的版本、启用状态已变化，旧计划失效")

    async def execute(self, plan_id, revision, mission_id, grant_id, dispatcher):
        """每个 LangGraph 节点重新核对版本并通过既有授权网关调用；失败/受限立即终止。"""
        async with self._lock:
            private = self._plans.pop(plan_id, None)
            if private is None:
                _fail("SKILL_PLAN", "计划不存在、已执行或重启失效")
            plan = private["public"]
            execution = self._execution(plan)
            try:
                if (revision != plan["revision"] or str(mission_id) != plan["mission_id"] or str(grant_id) != plan["grant_id"]):
                    _fail("SKILL_PERMISSION", "审批与计划、任务或授权不匹配")
                await self._check_bindings(plan)
            except SkillError as exc:
                execution.update(status="failed", error={"code": exc.code, "message": exc.message})
                await self._save(plan, execution)
                raise
            execution["status"] = "running"
            await self._save(plan, execution)
        results, started, output_bytes = {}, monotonic(), 0

        async def step_node(state):
            """一个节点仅尝试一次；响应校验和 SQLite 落库后才能推进下一节点。"""
            nonlocal output_bytes
            index, step = state["index"], plan["steps"][state["index"]]
            evidence = {"id": step["id"], "tool": step["tool"], "status": "failed", "result": None, "error": None}
            invoked = False
            try:
                await self._check_bindings(plan)
                remaining = 10 - (monotonic() - started)
                if remaining <= 0:
                    _fail("SKILL_TIMEOUT", "工作流10秒总预算已耗尽")
                for check in private["checks"]:
                    if check.get("before") == index:
                        _validate(check["schema"], _resolve(check["value"], {}, results))
                args = _resolve(step["arguments"], {}, results)
                try:
                    args = TOOLS[step["tool"]].model_validate(args).model_dump()
                except ValueError:
                    _fail("SKILL_CONTRACT", "节点参数不符合现有只读工具契约")
                invoked = True
                remaining = 10 - (monotonic() - started)
                if remaining <= 0:
                    _fail("SKILL_TIMEOUT", "工作流10秒总预算已耗尽")
                value = await asyncio.wait_for(dispatcher(step["tool"], args), timeout=remaining)
                if monotonic() - started > 10:
                    raise asyncio.TimeoutError
                await self._check_bindings(plan)
                if not isinstance(value, dict):
                    _fail("SKILL_CONTRACT", "工具必须返回结构化结果")
                output_bytes += _size(value)
                if output_bytes > OUTPUT_LIMIT or _size(execution) + _size(value) + 512 > OUTPUT_LIMIT:
                    _fail("SKILL_OUTPUT_LIMIT", "工作流结果合计超过32KiB；不返回超限正文")
                _validate(step["output_schema"], value)
                if (value.get("complete") is not True or value.get("truncated") is True or value.get("errors")):
                    evidence.update(status="limited", result=value)
                    execution.update(status="limited", error={"code": "SKILL_LIMITED", "message": "工具结果未完整核验；后续步骤已停止"})
                else:
                    results[step["id"]] = value
                    for check in private["checks"]:
                        if check.get("after") == index:
                            _validate(check["schema"], _resolve(check["value"], {}, results))
                    evidence.update(status="completed", result=value)
            except asyncio.TimeoutError:
                evidence.update(status="unknown", error={"code": "SKILL_TIMEOUT", "message": "工具响应超时，结果未知；不会重试"})
                execution.update(status="interrupted", error=evidence["error"])
            except SkillError as exc:
                evidence["error"] = {"code": exc.code, "message": exc.message}
                execution.update(status="failed", error=evidence["error"])
            except (ValueError, OSError, ToolError) as exc:
                # 网关稳定错误可展示；未知环境错误不回传系统路径或包正文。
                evidence["error"] = {"code": getattr(exc, "code", "SKILL_TOOL_FAILED"), "message": getattr(exc, "message", "只读工具调用失败；后续步骤已停止")}
                execution.update(status="failed", error=evidence["error"])
            except asyncio.CancelledError:
                evidence.update(status="unknown" if invoked else "failed", error={"code": "SKILL_CANCELLED", "message": "执行已取消，未完成结果不会自动重试"})
                execution.update(status="interrupted", error=evidence["error"])
                execution["steps"].append(evidence)
                await asyncio.shield(self._save(plan, execution))
                raise
            execution["steps"].append(evidence)
            await self._save(plan, execution)
            return {"index": index + 1, "stopped": execution["status"] != "running"}

        graph = StateGraph(GraphState)
        graph.add_node("execute_readonly_step", step_node)
        graph.add_edge(START, "execute_readonly_step")
        graph.add_conditional_edges("execute_readonly_step", lambda s: END if s["stopped"] or s["index"] >= len(plan["steps"]) else "execute_readonly_step")
        try:
            await graph.compile().ainvoke({"index": 0, "stopped": False}, {"recursion_limit": 70})
        except Exception:
            # 非预期执行基础设施故障只记录中断并向上抛出；不降级成功、不继续任何步骤。
            execution.update(status="interrupted", error={"code": "SKILL_INTERRUPTED", "message": "工作流基础设施中断，结果未知；不自动续接"})
            await self._save(plan, execution)
            raise
        if execution["status"] == "running":
            execution["status"] = "completed"
            # 结果只保存一份；output返回映射会重复正文，超预算时返回结构引用而非复制正文。
            output = _resolve(private["output"], {}, results)
            execution["output"] = output if _size(execution) + _size(output) <= OUTPUT_LIMIT else {"step_results": "请读取 steps 内已保存的结果"}
            await self._save(plan, execution)
        return execution
