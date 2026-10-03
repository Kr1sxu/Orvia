"""M20 统一自然请求：有界复合步骤、原请求暂停/接续、有效资料解绑。"""

import asyncio
import json
import re
import hashlib
from datetime import datetime, timezone
from urllib.parse import urlsplit
from uuid import uuid4

from ..computer.paths import ToolError
from ..configuration.client import ModelUnavailable
from .contracts import BrowserAsk, BrowserRead, BrowserSearch, Send
from .contracts import SynthesisPreview
from .json_stream import AnswerJSONStream, JSONStreamError
from .routing import Route, Step, understand, remaining


class NaturalCoordinator:
    def __init__(self, chat):
        self.chat = chat

    @staticmethod
    def desktop_success_rule(text):
        """只核验本步骤动作和明确输入；下一步必须建立新baseline并另行原生批准。"""
        action = ("set_value" if re.search(r"填写|输入", text) else "invoke" if re.search(r"点击|按钮", text)
                  else "toggle" if "勾选" in text else "select" if "选择选项" in text else "focus")
        rule = {"action": action, "created_after": datetime.now(timezone.utc).isoformat()}
        quoted = re.findall(r'[“"]([^”"]+)[”"]', text)
        if action == "set_value" and quoted:
            rule["value_sha256"] = hashlib.sha256(quoted[-1].encode("utf-8")).hexdigest()
        elif action in {"invoke", "toggle", "select"} and quoted:
            rule["target_name"] = quoted[-1]
        return rule

    async def desktop_step_verified(self, cid, successes, rule):
        for oid in {item["data"].get("operation_id") for item in successes}:
            if not oid:
                continue
            operation = await self.chat.automation.repository.get(cid, oid)
            audit = operation["audit"]
            evidence = audit.get("evidence", {})
            if (operation["kind"] != "desktop" or operation["status"] not in {"verified", "completed"}
                    or operation["created_at"] < rule["created_after"] or evidence.get("verified") is not True
                    or audit.get("action") != rule["action"] or audit.get("category") != "local"):
                continue
            if rule.get("value_sha256") and audit.get("value_sha256") != rule["value_sha256"]:
                continue
            if rule.get("target_name") and audit.get("target_name") != rule["target_name"]:
                continue
            expected = "ui_state_changed" if rule["action"] == "invoke" else "control_state"
            if evidence.get("verification") == expected:
                return True
        return False

    @staticmethod
    def browser_success_rule(text, url):
        """把用户要求固化为有限核验条件；填写控件不能代替消息/上传等外发效果。"""
        categories = []
        for category, words in (("message", ("发送", "消息")), ("upload", ("上传",)),
                                ("delete", ("删除",)), ("transaction", ("交易", "购买")),
                                ("form", ("提交", "登录"))):
            if any(word in text for word in words):
                categories.append(category)
        controls = [action for action, words in (("fill", ("填写", "输入", "填表")),
                                                 ("check", ("勾选",)), ("select", ("选择选项",)))
                    if any(word in text for word in words)]
        parsed = urlsplit(url)
        return {"effect": "external" if categories else "control", "control_actions": controls,
                "categories": categories, "origin": f"{parsed.scheme}://{parsed.netloc}",
                "created_after": datetime.now(timezone.utc).isoformat()}

    async def browser_step_verified(self, cid, messages, successes, rule):
        """只读既有M18账本和原生外发批准摘要；renderer布尔值与HTTP200均不足以完成。"""
        operations = []
        for oid in {item["data"].get("operation_id") for item in successes}:
            if not oid:
                continue
            operation = await self.chat.automation.repository.get(cid, oid)
            audit = operation["audit"]
            evidence = audit.get("evidence", {})
            if (operation["kind"] == "browser" and operation["status"] in {"verified", "completed"}
                    and operation["created_at"] >= rule["created_after"]
                    and audit.get("origin") == rule["origin"] and evidence.get("verified") is True):
                operations.append(operation)
        for action in rule["control_actions"]:
            if not any(item["audit"].get("action") == action
                       and item["audit"]["evidence"].get("action") == action
                       and item["audit"]["evidence"].get("control_matched") is True for item in operations):
                return False
        approvals = [item for item in messages if item["kind"] == "automation"
                     and item.get("data", {}).get("kind") == "browser-request"
                     and item["data"].get("approved") is True]
        for category in rule["categories"]:
            matched = False
            for operation in operations:
                audit = operation["audit"]
                evidence = audit["evidence"]
                if (audit.get("category") != category or evidence.get("matched") is not True
                        or type(evidence.get("http_status")) is not int or not 200 <= evidence["http_status"] < 300
                        or not all(re.fullmatch(r"[0-9a-f]{64}", str(evidence.get(key, "")))
                                   for key in ("request_sha256", "response_sha256", "expected_sha256", "page_sha256"))):
                    continue
                if any(operation["created_at"] <= approval["created_at"] <= operation["updated_at"]
                       and approval["data"].get("request_meta", {}).get("origin") == rule["origin"]
                       and approval["data"]["request_meta"].get("category") == category
                       and approval["data"]["request_meta"].get("body_sha256") == evidence["request_sha256"]
                       for approval in approvals):
                    matched = True
                    break
            if not matched:
                return False
        return bool(operations) if not rule["control_actions"] and not rule["categories"] else True

    async def open(self):
        async with self.chat.store._lock:
            db = self.chat.store._db()
            await db.execute("""CREATE TABLE IF NOT EXISTS m20_workflows (
                conversation_id TEXT NOT NULL,request_id TEXT NOT NULL,text TEXT NOT NULL,
                plan_json TEXT NOT NULL,position INTEGER NOT NULL DEFAULT 0,state TEXT NOT NULL,
                continuation_id TEXT,workflow_json TEXT,baseline INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(conversation_id,request_id))""")
            await db.execute("""CREATE TABLE IF NOT EXISTS m20_removed_sources (
                conversation_id TEXT NOT NULL,kind TEXT NOT NULL,evidence_id TEXT NOT NULL,
                PRIMARY KEY(conversation_id,kind,evidence_id))""")
            await db.execute("""CREATE TABLE IF NOT EXISTS m20_materials (
                conversation_id TEXT NOT NULL,kind TEXT NOT NULL,evidence_id TEXT NOT NULL,
                title TEXT NOT NULL,status TEXT NOT NULL,input_bytes INTEGER NOT NULL,
                PRIMARY KEY(conversation_id,kind,evidence_id))""")
            await db.execute("CREATE TABLE IF NOT EXISTS m20_materials_initialized (conversation_id TEXT PRIMARY KEY)")
            async with db.execute("PRAGMA table_info(m20_workflows)") as cursor:
                columns = {row[1] for row in await cursor.fetchall()}
            if "fallback_used" not in columns:
                await db.execute("ALTER TABLE m20_workflows ADD COLUMN fallback_used INTEGER NOT NULL DEFAULT 0")
            await db.execute("UPDATE m20_workflows SET state='interrupted',continuation_id=NULL,workflow_json=NULL WHERE state IN ('running','waiting_input','waiting_approval')")

    async def row(self, cid, rid=None):
        async with self.chat.store._lock:
            sql = "SELECT * FROM m20_workflows WHERE conversation_id=?"
            args = [cid]
            if rid is not None:
                sql += " AND request_id=?"
                args.append(rid)
            sql += " ORDER BY rowid DESC LIMIT 1"
            async with self.chat.store._db().execute(sql, args) as cursor:
                row = await cursor.fetchone()
        return dict(row) if row else None

    async def workflow(self, cid):
        row = await self.row(cid)
        return json.loads(row["workflow_json"]) if row and row["workflow_json"] and row["state"] in {"waiting_input", "waiting_approval"} else None

    async def materials(self, cid):
        await self._initialize_materials(cid)
        async with self.chat.store._lock:
            async with self.chat.store._db().execute("SELECT kind,evidence_id,title,status FROM m20_materials WHERE conversation_id=? ORDER BY rowid", (cid,)) as cursor:
                return [dict(row) for row in await cursor.fetchall()]

    async def _initialize_materials(self, cid):
        """旧会话只映射最近三份已保存版本；不重读原文件/联网、不恢复目录权限。

        历史证据仍全部可回查。有效集合有独立注册表，之后不因目录20项截断而漏掉
        已选资料；一次性迁移不会在用户移除后把旧版本重新激活。
        """
        async with self.chat.store._lock:
            db = self.chat.store._db()
            async with db.execute("SELECT 1 FROM m20_materials_initialized WHERE conversation_id=?", (cid,)) as cursor:
                if await cursor.fetchone():
                    return
            async with db.execute("SELECT COUNT(*) FROM m20_materials WHERE conversation_id=?", (cid,)) as cursor:
                has_active = (await cursor.fetchone())[0]
            if not has_active:
                candidates = []
                for kind, table in (("document", "document_evidence"), ("browser", "browser_evidence")):
                    async with db.execute(f"SELECT evidence_json FROM {table} WHERE mission_id=? AND NOT EXISTS (SELECT 1 FROM m20_removed_sources WHERE conversation_id=? AND kind=? AND evidence_id={table}.id) ORDER BY rowid DESC LIMIT 4", (cid, cid, kind)) as cursor:
                        for row in await cursor.fetchall():
                            value = json.loads(row[0])
                            candidates.append((value.get("accessed_at", ""), kind, value))
                for _, kind, value in sorted(candidates, key=lambda item: item[0], reverse=True)[:3]:
                    await db.execute("INSERT INTO m20_materials VALUES (?,?,?,?,?,?)", (cid, kind, value["evidence_id"], value.get("title", "")[:200], "failed" if value.get("error") else "ready", 10 * 1024 * 1024 if kind == "document" else 0))
            await db.execute("INSERT INTO m20_materials_initialized VALUES (?)", (cid,))

    async def check_material_budget(self, cid, *, kind=None, eid=None, input_bytes=0):
        await self._initialize_materials(cid)
        async with self.chat.store._lock:
            async with self.chat.store._db().execute("SELECT kind,evidence_id,input_bytes FROM m20_materials WHERE conversation_id=?", (cid,)) as cursor:
                items = await cursor.fetchall()
        if eid is not None and kind is not None and any((item[0], item[1]) == (kind, eid) for item in items):
            return
        if len(items) >= 3 or sum(item[2] for item in items) + input_bytes > 30 * 1024 * 1024:
            raise ToolError("MATERIAL_LIMIT", "有效资料最多3份且本地附件合计不超过30MiB，请先移除不再使用的资料")

    async def material_added(self, cid, kind, eid, *, input_bytes=0):
        value = await (self.chat.documents if kind == "document" else self.chat.evidence).get(cid, eid)
        await self.check_material_budget(cid, kind=kind, eid=eid, input_bytes=input_bytes)
        async with self.chat.store._lock:
            await self.chat.store._db().execute("DELETE FROM m20_removed_sources WHERE conversation_id=? AND kind=? AND evidence_id=?", (cid, kind, eid))
            await self.chat.store._db().execute("INSERT OR REPLACE INTO m20_materials VALUES (?,?,?,?,?,?)", (cid, kind, eid, value.get("title", "")[:200], "failed" if value.get("error") else "ready", input_bytes))

    async def remove(self, request):
        cid = str(request.id)
        await (self.chat.documents if request.kind == "document" else self.chat.evidence).get(cid, request.evidence_id)
        async with self.chat.store._lock:
            await self.chat.store._db().execute("INSERT OR IGNORE INTO m20_removed_sources VALUES (?,?,?)", (cid, request.kind, request.evidence_id))
            await self.chat.store._db().execute("DELETE FROM m20_materials WHERE conversation_id=? AND kind=? AND evidence_id=?", (cid, request.kind, request.evidence_id))
        await self.chat.repository.append(cid, "system", "资料已从本会话有效集合移除；原文件和历史引用保留。", "material_removed",
                                          {"kind": request.kind, "evidence_id": request.evidence_id})

    async def _update(self, cid, rid, **values):
        allowed = {"plan_json", "position", "state", "continuation_id", "workflow_json", "baseline"}
        if not values or set(values) - allowed:
            raise ValueError("工作流更新字段无效")
        async with self.chat.store._lock:
            await self.chat.store._db().execute("UPDATE m20_workflows SET " + ",".join(name + "=?" for name in values) + " WHERE conversation_id=? AND request_id=?",
                                              [*values.values(), cid, rid])

    async def pause(self, cid, rid, action, question, *, input=None, choices=None, approval=False, notify=True):
        token = str(uuid4())
        state = "waiting_approval" if approval else "waiting_input"
        value = {"request_id": rid, "continuation_id": token, "state": state, "reason": action,
                 "action": action, "question": question}
        if input is not None:
            value["input"] = input
        if choices:
            value["choices"] = choices
        baseline = await self.chat.repository.sequence(cid)
        await self._update(cid, rid, state=state, continuation_id=token, workflow_json=json.dumps(value, ensure_ascii=False), baseline=baseline)
        await self.chat.repository.finish(cid, rid, state)
        await self.chat.repository.append(cid, "assistant", question, "workflow", {"request_id": rid, "action": action})
        if notify:
            await self.chat.streams.emit(cid, rid, "paused", {"action": action, "question": question})

    async def fail_parent_without_event(self, cid, rid):
        """子请求运输不能输出父身份事件；返回快照反映失败，保持严格stdio绑定。"""
        await self._update(cid, rid, state="failed", continuation_id=None, workflow_json=None)
        await self.chat.repository.finish(cid, rid, "failed")
        async with self.chat.store._lock:
            await self.chat.store._db().execute("UPDATE m20_streams SET state='failed' WHERE conversation_id=? AND request_id=?", (cid, rid))

    async def _terminal(self, cid, rid, state, *, code=None, message=None):
        await self._update(cid, rid, state=state, continuation_id=None, workflow_json=None)
        await self.chat.repository.finish(cid, rid, state)
        if code:
            await self.chat.repository.append(cid, "system", message, "error", {"code": code, "request_id": rid})
            await self.chat.streams.emit(cid, rid, "failed", {"code": code, "message": message})
        else:
            await self.chat.streams.emit(cid, rid, "cancelled" if state == "cancelled" else "completed",
                                         {"label": "已取消；未自动重放" if state == "cancelled" else "本次请求已完成"})

    async def cancel(self, cid, rid):
        row = await self.row(cid, rid)
        if not row or row["state"] not in {"running", "waiting_input", "waiting_approval"}:
            return False
        active = self.chat._active.get(cid)
        if active and (active["request_id"] == rid or active.get("parent_request_id") == rid):
            active["cancelled"] = True
            if active["model"] is not None and not active["model"].done():
                active["model"].cancel()
            if active.get("parent_request_id") == rid:
                await self._terminal(cid, rid, "cancelled")
            return True
        await self.chat.repository.append(cid, "system", "已取消等待资料/批准的原请求；旧接续身份失效。", "error", {"code": "REQUEST_CANCELLED", "request_id": rid})
        await self._terminal(cid, rid, "cancelled")
        return True

    async def natural(self, request):
        cid, rid = str(request.id), str(request.request_id)
        old = await self.row(cid)
        if old and old["request_id"] != rid and old["state"] in {"running", "waiting_input", "waiting_approval"}:
            raise ToolError("REQUEST_PENDING", "当前请求仍待资料或批准，请补必要信息或取消后开始新请求")
        if not request.text.strip():
            raise ToolError("INVALID_PARAMS", "消息不能为空")
        if not await self.chat.repository.claim(cid, rid, "natural:" + request.text):
            return
        async with self.chat.store._lock:
            await self.chat.store._db().execute("INSERT INTO m20_workflows(conversation_id,request_id,text,plan_json,position,state,continuation_id,workflow_json,baseline) VALUES (?,?,?,'[]',0,'running',NULL,NULL,0)", (cid, rid, request.text))
        await self.chat.repository.append(cid, "user", request.text, "natural_request")
        await self.chat.streams.start(cid, rid)
        active = {"request_id": rid, "model": None, "cancelled": False, "deadline": asyncio.get_running_loop().time() + 50}
        self.chat._active[cid] = active
        try:
            active["purpose"] = "routing"
            history, _ = await self.chat.repository.messages(cid)
            plan = await understand(self.chat, cid, request.text, await self.materials(cid), history, active)
            await self._update(cid, rid, plan_json=plan.model_dump_json())
            await self.drive(cid, rid, active)
        except asyncio.CancelledError:
            if not active["cancelled"]:
                raise
            await self._terminal(cid, rid, "cancelled")
        except (ModelUnavailable, TimeoutError, ToolError, JSONStreamError) as error:
            await self.failed(cid, rid, error)
        finally:
            self.chat._active.pop(cid, None)

    async def failed(self, cid, rid, error):
        code = error.code if isinstance(error, ToolError) else "INVALID_GENERATION" if isinstance(error, JSONStreamError) else "MISSING_CREDENTIAL" if isinstance(error, ModelUnavailable) and str(error) == "MISSING_CREDENTIAL" else "STREAM_UNSUPPORTED" if isinstance(error, ModelUnavailable) and str(error) == "STREAM_UNSUPPORTED" else "MODEL_TIMEOUT" if isinstance(error, TimeoutError) else "MODEL_UNAVAILABLE"
        message = error.message if isinstance(error, ToolError) else "固定Main返回的JSON不完整或结构非法；已生成部分未通过严格JSON校验，未保存成功回答、自动降级或重试。" if isinstance(error, JSONStreamError) else "固定Main凭据缺失，请在设置配置；未调用备用模型。" if code == "MISSING_CREDENTIAL" else "固定模型不支持本次SSE；需要另行确认非流式请求，未自动降级。" if code == "STREAM_UNSUPPORTED" else "本次模型流不可用、被中断或结构无效；临时文字未保存为成功回答，未自动重试。"
        row = await self.row(cid, rid)
        if isinstance(error, ModelUnavailable) and code != "MISSING_CREDENTIAL" and row and not row["fallback_used"]:
            active = self.chat._active.get(cid, {})
            await self.chat.repository.append(cid, "system", message, "error", {"code": code, "request_id": rid})
            await self.pause(cid, rid, "stream_fallback", "固定Main流式请求失败或不支持；可另行原生确认一次非流式请求，可能再次计费。没有自动重试、换模型或推进工具。",
                             input={"purpose": active.get("purpose", "routing"), "instruction": row["text"][:2000]}, approval=True)
            return
        await self._terminal(cid, rid, "failed", code=code, message=message)

    async def consume_fallback(self, cid, rid):
        """调用前条件落库，一次批准最多产生一次新模型请求；失败也不能复用。"""
        async with self.chat.store._lock:
            cursor = await self.chat.store._db().execute("UPDATE m20_workflows SET fallback_used=1 WHERE conversation_id=? AND request_id=? AND state='waiting_approval' AND fallback_used=0", (cid, rid))
            if cursor.rowcount != 1:
                raise ToolError("FALLBACK_ALREADY_USED", "本次非流式降级批准已消费或失效，不会重复调用")

    async def confirm_fallback(self, request):
        cid, rid = str(request.id), str(request.request_id)
        row = await self.row(cid, rid)
        if not row or row["state"] != "waiting_approval" or row["continuation_id"] != str(request.continuation_id):
            raise ToolError("STALE_CONTINUATION", "降级确认已失效，没有重发")
        workflow = json.loads(row["workflow_json"])
        if workflow["action"] != "stream_fallback":
            raise ToolError("FALLBACK_NOT_CONFIRMED", "当前步骤不允许模型降级")
        purpose = workflow["input"]["purpose"]
        if purpose == "synthesis":
            raise ToolError("FALLBACK_APPROVAL_REQUIRED", "证据回答须重新预览准确片段并通过既有原生生成审批；不能使用通用降级确认")
        if purpose not in {"routing", "answer"}:
            raise ToolError("INVALID_PARAMS", "此步骤不允许非流式降级")
        await self.consume_fallback(cid, rid)
        await self._update(cid, rid, state="running", continuation_id=None, workflow_json=None)
        await self.chat.repository.finish(cid, rid, "pending")
        active = {"request_id": rid, "model": None, "cancelled": False, "purpose": purpose, "confirmed_nonstream": True, "deadline": asyncio.get_running_loop().time() + 50}
        self.chat._active[cid] = active
        await self.chat.streams.emit(cid, rid, "tool_status", {"stage": "confirmed_nonstream", "label": "原生再次批准固定Main的一次非流式请求；等待完整响应"})
        try:
            if purpose == "routing":
                history, _ = await self.chat.repository.messages(cid)
                plan = await understand(self.chat, cid, row["text"], await self.materials(cid), history, active, nonstream=True)
                await self._update(cid, rid, plan_json=plan.model_dump_json())
                await self.drive(cid, rid, active)
            else:
                await self.answer(cid, rid, workflow["input"]["instruction"], active, nonstream=True)
                await self._terminal(cid, rid, "completed")
        except asyncio.CancelledError:
            if not active["cancelled"]:
                raise
            await self._terminal(cid, rid, "cancelled")
        except (ModelUnavailable, TimeoutError, ToolError, JSONStreamError) as error:
            await self.failed(cid, rid, error)
        finally:
            self.chat._active.pop(cid, None)

    async def continue_request(self, request):
        cid, rid = str(request.id), str(request.request_id)
        phase_deadline = asyncio.get_running_loop().time() + 50
        row = await self.row(cid, rid)
        if not row or row["state"] not in {"waiting_input", "waiting_approval"} or row["continuation_id"] != str(request.continuation_id):
            raise ToolError("STALE_CONTINUATION", "接续身份已消费、取消或失效；没有重放原任务")
        workflow = json.loads(row["workflow_json"])
        action = workflow["action"]
        position = row["position"]
        if action == "directory":
            self.chat.gateway.authorized_root(cid)
        elif action == "materials":
            effective = await self.materials(cid)
            if workflow.get("input", {}).get("requires_slot") and len(effective) >= 3:
                raise ToolError("MATERIAL_LIMIT", "请先移除一份不再使用的资料，再接续已保留请求")
            if not workflow.get("input", {}).get("requires_slot") and not any(item["status"] == "ready" for item in effective):
                raise ToolError("MATERIAL_REQUIRED", "尚无可用本地资料，请完成解析或取消原请求")
        elif action == "clarification":
            if not request.answer or not request.answer.strip():
                raise ToolError("CLARIFICATION_REQUIRED", "请补充本次必要信息")
            await self.chat.repository.append(cid, "user", request.answer, "clarification", {"request_id": rid})
            plan = Route.model_validate_json(row["plan_json"])
            current = plan.steps[position]
            if current.kind == "clarify":
                active = {"request_id": rid, "model": None, "cancelled": False, "deadline": phase_deadline}
                self.chat._active[cid] = active
                try:
                    history, _ = await self.chat.repository.messages(cid)
                    replacement = await understand(self.chat, cid, row["text"] + "\n用户补充：" + request.answer,
                                                   await self.materials(cid), history, active)
                    if position + len(replacement.steps) > 4:
                        raise ToolError("TASK_LIMIT", "复合请求超过4步骤，请明确拆分；没有删减或执行剩余目标")
                    plan.steps = [*plan.steps[:position], *replacement.steps]
                finally:
                    self.chat._active.pop(cid, None)
            elif current.kind == "search":
                current.query = request.answer[:300]
            else:
                # 多来源歧义只接受当前有效资料的明确名称或“全部”；不会解析资料中的指令。
                ready = [item for item in await self.materials(cid) if item["status"] == "ready"]
                selected = ready if request.answer.strip() in {"全部", "这些", "全部资料"} else [item for item in ready if item["evidence_id"] == request.answer.strip() or item["title"] == request.answer.strip()]
                if not 1 <= len(selected) <= 3:
                    raise ToolError("AMBIGUOUS_SOURCE", "请明确1到3份当前有效资料的名称")
                if request.answer.strip() not in {"全部", "这些", "全部资料"} and len(selected) != 1:
                    raise ToolError("AMBIGUOUS_SOURCE", "同名资料包含多个版本，请选择一个明确证据ID")
                current.source_ids = [item["evidence_id"] for item in selected]
            await self._update(cid, rid, plan_json=plan.model_dump_json())
        else:
            messages = await self.chat.repository.since(cid, row["baseline"])
            required = {"synthesis": "synthesis", "stream_fallback": "synthesis", "publication": "publication", "development": "development",
                        "script": "automation", "desktop": "automation", "browser": "automation", "cleanup": "cleanup", "files": "result"}.get(action)
            successes = [item for item in messages if item["kind"] == required]
            if not successes and action != "desktop":
                raise ToolError("STEP_NOT_VERIFIED", "该步骤尚无真实已保存结果；没有推进或重放")
            if action in {"synthesis", "stream_fallback"}:
                expected = {(item["kind"], item["evidence_id"]) for item in workflow["input"]["sources"]}
                args = {key: workflow["input"][key] for key in ("mode", "question", "sources")}
                packet = await self.chat.synthesis_preview(SynthesisPreview(id=cid, **args))
                available = {(item["kind"], item["evidence_id"]) for item in await self.materials(cid) if item["status"] == "ready"}
                successes = [item for item in successes if {(entry["kind"], entry["evidence_id"]) for entry in item["data"]["coverage"]} == expected
                             and item["data"].get("revision") == packet["revision"] and expected <= available]
            if action == "publication":
                successes = [item for item in successes if item["data"].get("message_id") == workflow["input"]["message_id"] and item["data"].get("format") == workflow["input"]["format"]]
            if action in {"desktop", "browser", "script"}:
                # M18 真实账本的核验终态，而不是“已批准/运行中”消息，才能推进原请求。
                history = await self.chat.automation.repository.history(cid)
                entries = history.get("operations", []) if isinstance(history, dict) else history
                if action == "desktop":
                    # M18后台先提交控件核验账本，再追加会话摘要；状态读取可落在两事务之间。
                    # 直接核对本步骤创建基线之后的真实操作，摘要消息不是执行身份或核验依据。
                    successes = [{"data": {"operation_id": item["operation_id"]}} for item in entries
                                 if item.get("kind") == "desktop" and item.get("status") in {"verified", "completed"}
                                 and item.get("created_at", "") >= workflow["input"]["success_rule"]["created_after"]]
                ids = {item["data"].get("operation_id") for item in successes}
                successes = successes if any(item.get("operation_id") in ids and item.get("kind") == action and item.get("status") in {"verified", "completed"} for item in entries) else []
                if action == "browser" and successes:
                    rule = workflow["input"]["success_rule"]
                    successes = successes if await self.browser_step_verified(cid, messages, successes, rule) else []
                if action == "desktop" and successes:
                    successes = successes if await self.desktop_step_verified(cid, successes, workflow["input"]["success_rule"]) else []
            if action == "files":
                successes = [item for item in successes if item["data"].get("operation_id") == workflow["input"]["operation_id"] and item["data"].get("success") is True]
            if action == "cleanup":
                successes = [item for item in successes if item["data"].get("plan_id") == workflow["input"]["plan_id"] and item["data"].get("status") in {"completed", "restored"}]
            if not successes:
                raise ToolError("STEP_NOT_VERIFIED", "现有结果身份或核验状态不匹配原步骤；没有推进")
            position += 1
        # 在会话锁内消费唯一token；之后错误也不会让原批准或未知副作用被重复执行。
        await self._update(cid, rid, state="running", position=position, continuation_id=None, workflow_json=None)
        await self.chat.repository.finish(cid, rid, "pending")
        active = {"request_id": rid, "model": None, "cancelled": False, "deadline": phase_deadline}
        self.chat._active[cid] = active
        try:
            await self.drive(cid, rid, active)
        except asyncio.CancelledError:
            if not active["cancelled"]:
                raise
            await self._terminal(cid, rid, "cancelled")
        except (ModelUnavailable, TimeoutError, ToolError, JSONStreamError) as error:
            await self.failed(cid, rid, error)
        finally:
            self.chat._active.pop(cid, None)

    async def drive(self, cid, rid, active):
        row = await self.row(cid, rid)
        plan = Route.model_validate_json(row["plan_json"])
        position = row["position"]
        while position < len(plan.steps):
            remaining(active, 50)
            if active["cancelled"]:
                raise asyncio.CancelledError
            step = plan.steps[position]
            await self.chat.streams.emit(cid, rid, "tool_status", {"stage": step.kind, "label": "正在处理已确定步骤"})
            if step.kind in {"list", "search", "space", "files", "development"} and not self.chat.gateway.status(cid)["allow_files"]:
                await self.pause(cid, rid, "directory", "请通过＋选择并授权本次目录；原请求已保留，成功后接续。")
                return
            if step.kind in {"list", "search", "space"}:
                if step.kind == "search" and not step.query.strip():
                    await self.pause(cid, rid, "clarification", "请补充要匹配的文件名片段；只检索文件名。")
                    return
                async def emit(kind, payload):
                    await self.chat.streams.emit(cid, rid, kind, payload)
                result = await asyncio.wait_for(self.chat.scans.run(cid, rid, path=step.path, depth=step.depth, query=step.query,
                                                                  operation=step.kind, emit=emit, cancelled=lambda: active["cancelled"]), remaining(active, 50))
                summary = result["summary"]
                tool = {"list": "list_directory", "search": "search_files", "space": "analyze_directory_space"}[step.kind]
                await self.chat.repository.append(cid, "assistant", f"已发现{summary['discovered']}条，当前展示{len(result['entries'])}条；扫描范围为相对路径 {step.path}，深度{step.depth}层。分类仅依据扩展名和目录属性，未读取正文。完整已发现清单可分页回查。", "directory_result",
                                                  {"scan_id": result["scan_id"], "tool": tool, "summary": summary, "entries": result["entries"]})
            elif step.kind in {"read_url", "web_search", "material_quote"}:
                child = {"id": cid, "request_id": str(uuid4())}
                effective = await self.materials(cid)
                if step.kind in {"read_url", "web_search"} and len(effective) >= 3:
                    await self.pause(cid, rid, "materials", "当前有效资料已达3份；请先移除一份再接续。历史引用保留，没有重读或联网。", input={"requires_slot": True})
                    return
                if step.kind == "read_url":
                    await self.chat.browser_request("chat.browser.read", BrowserRead(**child, url=step.url), deadline=active["deadline"], active=active)
                elif step.kind == "web_search":
                    await self.chat.browser_request("chat.browser.search", BrowserSearch(**child, query=step.query[:500], max_results=3-len(effective)), deadline=active["deadline"], active=active)
                else:
                    active_ids = {(item["kind"], item["evidence_id"]) for item in await self.materials(cid)}
                    docs = [item for item in await self.chat.documents.search(cid, step.query[:200]) if ("document", item["evidence_id"]) in active_ids]
                    webs = [item for item in await self.chat.evidence.search(cid, step.query[:200]) if ("browser", item["evidence_id"]) in active_ids]
                    await self.chat.repository.append(cid, "assistant", "以下是当前有效资料的原文引用；未做模型总结。" if docs or webs else "当前有效资料没有匹配原文；已移除资料不会参与本次检索。",
                                                      "document" if docs else "source", {"items": docs or webs, "operation": "ask", "error": None})
                recent = await self.chat.repository.since(cid, await self.chat.repository.sequence(cid) - 2)
                if recent and recent[-1]["kind"] == "error":
                    raise ToolError(recent[-1]["data"]["code"], recent[-1]["text"])
                if recent and isinstance(recent[-1].get("data"), dict) and recent[-1]["data"].get("error"):
                    failure = recent[-1]["data"]["error"]
                    raise ToolError(failure["code"], failure["message"])
            elif step.kind == "material_answer":
                ready = [item for item in await self.materials(cid) if item["status"] == "ready"]
                if not ready:
                    await self.pause(cid, rid, "materials", "请通过＋添加本地资料；添加不等于上云，原请求保留并在解析成功后接续。")
                    return
                named = [item for item in ready if item["title"] and item["title"] in step.query]
                for item in ready:
                    if item["kind"] == "browser" and item not in named:
                        detail = await self.chat.evidence.get(cid, item["evidence_id"])
                        if detail.get("source_url") and detail["source_url"] in step.query:
                            named.append(item)
                plural = any(word in step.query for word in ("这些", "全部", "所有", "比较", "对比", "综合"))
                if step.source_ids:
                    selected = [item for item in ready if item["evidence_id"] in step.source_ids]
                else:
                    selected = named or (ready if plural or len(ready) == 1 else [])
                if step.source_ids and len({item["evidence_id"] for item in selected}) != len(set(step.source_ids)):
                    raise ToolError("STALE_SOURCE", "明确选择的资料已不在本会话有效集合，请重新确认")
                if not selected or len(selected) > 3:
                    await self.pause(cid, rid, "clarification", "请明确本次使用的1到3份资料；资料标题和正文均不授予权限。",
                                     choices=[{"id": item["evidence_id"], "label": item["title"] + " · " + item["evidence_id"][:8]} for item in ready])
                    return
                sources = [{"kind": item["kind"], "evidence_id": item["evidence_id"]} for item in selected]
                await self.pause(cid, rid, "synthesis", "请核对确切拟发送片段并原生确认；正文只在确认后发给固定Main。",
                                 input={"mode": "summary" if any(word in step.query for word in ("总结", "摘要", "概括")) else "answer", "question": step.query[:300] or row["text"][:300], "sources": sources}, approval=True)
                return
            elif step.kind == "publication":
                messages, _ = await self.chat.repository.messages(cid)
                source = next((item for item in reversed(messages) if item["kind"] == "synthesis"), None)
                if not source:
                    raise ToolError("SOURCE_REQUIRED", "需要当前会话已保存的带引用回答，才能生成简报")
                data = source["data"]
                await self.pause(cid, rid, "publication", "已准备本地简报内容；请预览并用原生保存框选择新文件。",
                                 input={"message_id": source["id"], "format": step.format, "title": step.query[:40] or "Orvia带引用简报", "answer": data["answer"], "claim_texts": [item["text"] for item in data["claims"]]}, approval=True)
                return
            elif step.kind == "development":
                await self.pause(cid, rid, "development", "请预览项目上下文并原生确认固定Computer生成；生成草稿后逐文件审查和批准。",
                                 input={"requirement": step.query, "kind": step.kind_hint if step.kind_hint in {"code", "prototype"} else "code", "stack": step.stack, "paths": [], "sources": []}, approval=True)
                return
            elif step.kind in {"script", "desktop", "browser"}:
                if step.kind == "browser" and (urlsplit(step.url).scheme != "https" or not urlsplit(step.url).netloc):
                    await self.pause(cid, rid, "clarification", "网页操作需要一个准确HTTPS站点，请补充本次目标。")
                    return
                input = {"requirement": step.query}
                if step.kind == "script":
                    input.update(source_kind=step.kind_hint if step.kind_hint in {"paste", "file", "model"} else "model", inputs=[])
                    match = re.search(r"```(?:python|py)?\s*\n(.*?)```", row["text"], re.S)
                    if match:
                        input["source"] = match.group(1)
                elif step.kind == "browser" and step.url:
                    input["url"] = step.url
                    input["success_rule"] = self.browser_success_rule(step.query, step.url)
                elif step.kind == "desktop":
                    input["success_rule"] = self.desktop_success_rule(step.query)
                question = "该步骤需要原生选择准确目标、完整预览和逐步批准；原请求等待真实核验结果。"
                if step.kind == "desktop" and input["success_rule"]["action"] == "set_value" and "value_sha256" not in input["success_rule"]:
                    question = "原需求未给确切输入文本；请在本次单步预览填写并确认，不能沿用旧任务值。仍须原生选择准确控件、独立批准实际预览并核验。"
                await self.pause(cid, rid, step.kind, question, input=input, approval=True)
                return
            elif step.kind == "cleanup":
                result = await self.chat.cleanup.scan(cid)
                await self.chat.repository.append(cid, "assistant", "仅扫描当前用户Temp顶层旧.tmp/.log；尚未移动，隔离不会释放空间。", "cleanup",
                                                  {"plan_id": result["plan_id"], "status": "planned", "count": len(result["entries"])})
                await self.pause(cid, rid, "cleanup", "请逐项核对旧临时文件隔离计划并原生批准。", input={"plan_id": result["plan_id"], "revision": result["revision"]}, approval=True)
                return
            elif step.kind == "files":
                await self.chat._send_claimed(Send(id=cid, request_id=rid, text=row["text"]), append_user=False)
                latest, _ = await self.chat.repository.messages(cid)
                if latest and latest[-1]["kind"] == "error":
                    raise ToolError(latest[-1]["data"]["code"], latest[-1]["text"])
                if latest and latest[-1]["kind"] == "plan":
                    await self.pause(cid, rid, "files", "逐项计划已就绪；需独立原生批准并真实执行核验。", input=latest[-1]["data"], approval=True)
                    return
            elif step.kind == "clarify":
                await self.pause(cid, rid, "clarification", step.query or "请明确本次目标和必要范围。")
                return
            elif step.kind == "unsupported":
                raise ToolError("UNSUPPORTED_TASK", step.query or "该任务未实现，未执行或编造结果。")
            else:
                if active.get("confirmed_nonstream") and active.get("purpose") == "routing":
                    await self.chat.repository.append(cid, "assistant", step.query, "natural_answer", {"model": "deepseek-flash", "notice": "经确认的固定Main非流式意图解释，不是工具执行事实"})
                else:
                    await self.answer(cid, rid, step.query or row["text"], active)
            position += 1
            await self._update(cid, rid, position=position)
        if active["cancelled"]:
            raise asyncio.CancelledError
        await self._terminal(cid, rid, "completed")

    async def answer(self, cid, rid, question, active, *, nonstream=False):
        mission = await self.chat.store.get_mission(cid)
        profile = next(item for item in mission.models if item.role == "main")
        parser = AnswerJSONStream()
        active["purpose"] = "answer"
        async def delta(value):
            text = parser.feed(value)
            if text:
                await self.chat.streams.emit(cid, rid, "model_delta", {"text": text, "provisional": True})
        messages = [{"role": "system", "content": "只回答用户普通问题，输出JSON {\"answer\":字符串}。不得假装读取资料、执行工具、核实新事实或拥有权限。"}, {"role": "user", "content": question}]
        model = asyncio.create_task(self.chat.client.complete(profile, messages, max_tokens=1024) if nonstream else
                                    self.chat.client.stream(profile, messages, max_tokens=1024, response_format={"type": "json_object"}, on_delta=delta))
        active["model"] = model
        try:
            result = await asyncio.wait_for(model, remaining(active))
        finally:
            active["model"] = None
        if nonstream:
            parser.feed(result.text or "")
        if result.finish_reason == "length":
            raise ToolError("GENERATION_TRUNCATED", "固定Main达到本次1024输出token预算，回答被截断；已生成部分仅供核对，未保存成功回答或自动重试。")
        if result.finish_reason != "stop" or result.tool_calls:
            raise ToolError("INVALID_GENERATION", "模型结束状态无效或提出了工具调用；未保存成功回答。")
        value = parser.finish()
        if set(value) != {"answer"} or not value["answer"].strip():
            raise ToolError("INVALID_GENERATION", "模型回答结构无效或未完整结束")
        data = {"model": profile.model, "usage": result.usage, "request_id": rid, "notice": "模型回答不等于工具事实核验"}
        if not nonstream:
            data["stream_prefix_chars"] = await self.chat.streams.prefix_size(cid, rid)
        await self.chat.repository.append(cid, "assistant", value["answer"], "natural_answer", data)
