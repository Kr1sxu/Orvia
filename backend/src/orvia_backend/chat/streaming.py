"""M20 流身份与持久递增序号；事件是事实状态，不是权限或自动重放队列。"""

import json
import time
from uuid import uuid4

from ..computer.paths import ToolError


class ChatStreams:
    def __init__(self, store):
        self.store = store
        self.sink = None

    async def open(self):
        async with self.store._lock:
            await self.store._db().execute("""CREATE TABLE IF NOT EXISTS m20_streams (
                conversation_id TEXT NOT NULL, request_id TEXT NOT NULL, stream_id TEXT NOT NULL,
                last_seq INTEGER NOT NULL DEFAULT 0, state TEXT NOT NULL, activity INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(conversation_id,request_id))""")
            async with self.store._db().execute("PRAGMA table_info(m20_streams)") as cursor:
                columns = {row[1] for row in await cursor.fetchall()}
            if "activity" not in columns:
                await self.store._db().execute("ALTER TABLE m20_streams ADD COLUMN activity INTEGER NOT NULL DEFAULT 0")
            if "model_text" not in columns:
                await self.store._db().execute("ALTER TABLE m20_streams ADD COLUMN model_text TEXT NOT NULL DEFAULT ''")
            # 重启不恢复等待资料/批准，也不重发旧事件或模型请求。
            await self.store._db().execute("UPDATE m20_streams SET state='interrupted' WHERE state IN ('running','paused')")
            # 完整结果和请求终态可能已提交，但终态事件尚未输出；恢复真实成功，不补造事件。
            await self.store._db().execute("UPDATE m20_streams SET state='completed' WHERE state='interrupted' AND EXISTS (SELECT 1 FROM chat_requests r WHERE r.conversation_id=m20_streams.conversation_id AND r.request_id=m20_streams.request_id AND r.status='completed')")

    async def start(self, cid, rid):
        async with self.store._lock:
            await self.store._db().execute("INSERT INTO m20_streams(conversation_id,request_id,stream_id,last_seq,state,activity) VALUES (?,?,?,0,'running',?)",
                                          (cid, rid, str(uuid4()), time.time_ns()))
        await self.emit(cid, rid, "started", {"label": "正在理解需求"})

    async def get(self, cid, rid=None):
        async with self.store._lock:
            sql = "SELECT request_id,stream_id,last_seq,state FROM m20_streams WHERE conversation_id=?"
            args = [cid]
            if rid is not None:
                sql += " AND request_id=?"
                args.append(rid)
            sql += " ORDER BY activity DESC,rowid DESC LIMIT 1"
            async with self.store._db().execute(sql, args) as cursor:
                row = await cursor.fetchone()
        return dict(row) if row else None

    async def prefix_size(self, cid, rid):
        """把已校验答案关联到真实前缀边界，复合请求后续失败只保留新的未核验部分。"""
        async with self.store._lock:
            async with self.store._db().execute("SELECT model_text FROM m20_streams WHERE conversation_id=? AND request_id=?", (cid, rid)) as cursor:
                row = await cursor.fetchone()
        # SQLite length(TEXT)在U+0000处停止；JSON字符串可合法含NUL，须与Python切片一致。
        return len(row[0]) if row else 0

    async def recover_history(self, cid, repository):
        """部分模型文字只作为未核验历史；幂等恢复不产生事件、调用或成功回答。"""
        async with self.store._lock:
            db = self.store._db()
            await db.execute("BEGIN IMMEDIATE")
            try:
                async with db.execute("SELECT request_id,stream_id,last_seq,state,model_text FROM m20_streams WHERE conversation_id=? AND state NOT IN ('running','completed') AND model_text!=''", (cid,)) as cursor:
                    rows = await cursor.fetchall()
                for row in rows:
                    async with db.execute("SELECT COALESCE(MAX(json_extract(message_json,'$.data.stream_prefix_chars')),0) FROM chat_messages WHERE conversation_id=? AND json_extract(message_json,'$.kind') IN ('synthesis','natural_answer') AND json_extract(message_json,'$.data.request_id')=?", (cid, row["request_id"])) as cursor:
                        verified = (await cursor.fetchone())[0]
                    text = row["model_text"][max(0, min(int(verified), len(row["model_text"]))):]
                    if not text:
                        continue
                    data = {"request_id": row["request_id"], "stream_id": row["stream_id"], "last_seq": row["last_seq"],
                            "state": row["state"], "text": text, "provisional": True}
                    async with db.execute("SELECT sequence,message_json FROM chat_messages WHERE conversation_id=? AND json_extract(message_json,'$.kind')='model_partial' AND json_extract(message_json,'$.data.stream_id')=? LIMIT 1", (cid, row["stream_id"])) as cursor:
                        existing = await cursor.fetchone()
                    label = "以下仅为实际模型部分正文，尚未完成结构或引用核验；不构成成功回答，不能制作成品。没有重放模型、事件或权限。"
                    if existing:
                        message = json.loads(existing["message_json"])
                        if message["data"] == data:
                            continue
                        message["data"] = data
                        await db.execute("UPDATE chat_messages SET message_json=? WHERE sequence=?", (json.dumps(message, ensure_ascii=False), existing["sequence"]))
                    else:
                        message = repository._message("assistant", label, "model_partial", data)
                        await db.execute("INSERT INTO chat_messages(conversation_id,message_json) VALUES (?,?)", (cid, json.dumps(message, ensure_ascii=False)))
                await db.commit()
            except BaseException:
                await db.rollback()
                raise

    async def emit(self, cid, rid, kind, payload):
        """真实正文和序号同次UPDATE持久化再通知；等待写者形成背压，不重发旧事件。"""
        if kind == "model_delta" and len(payload.get("text", "")) > 1024:
            # 分割的是刚收到的真实新增正文，不设定打字计时器，也不显示未产生文字。
            for offset in range(0, len(payload["text"]), 1024):
                await self.emit(cid, rid, kind, {**payload, "text": payload["text"][offset:offset + 1024]})
            return
        if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > 12 * 1024:
            raise ToolError("OUTPUT_LIMIT", "流式事件超过预算")
        state = {"paused": "paused", "completed": "completed", "failed": "failed", "cancelled": "cancelled"}.get(kind, "running")
        async with self.store._lock:
            db = self.store._db()
            async with db.execute("SELECT model_text FROM m20_streams WHERE conversation_id=? AND request_id=?", (cid, rid)) as cursor:
                previous = await cursor.fetchone()
            if previous is None:
                raise ToolError("NOT_FOUND", "流式请求不存在")
            text = previous[0]
            if kind == "model_delta":
                delta = payload.get("text")
                if not isinstance(delta, str) or payload.get("provisional") is not True:
                    raise ToolError("INVALID_STREAM", "模型正文增量结构无效")
                text += delta
                # 单条历史必须在快照预算内完整回查；超限前拒绝追加和显示。
                if len(text) > 16000 or len(json.dumps(text, ensure_ascii=False).encode("utf-8")) > 24 * 1024:
                    raise ToolError("OUTPUT_LIMIT", "模型正文超过显示与持久化预算；已显示部分完整保留，未作为成功回答")
            await db.execute("UPDATE m20_streams SET last_seq=last_seq+1,state=?,activity=?,model_text=? WHERE conversation_id=? AND request_id=?",
                             (state, time.time_ns(), text, cid, rid))
            async with db.execute("SELECT stream_id,last_seq FROM m20_streams WHERE conversation_id=? AND request_id=?", (cid, rid)) as cursor:
                row = await cursor.fetchone()
        if row is None:
            raise ToolError("NOT_FOUND", "流式请求不存在")
        value = {"v": 1, "event": "chat.stream", "conversation_id": cid, "request_id": rid,
                 "stream_id": row[0], "seq": row[1], "kind": kind, "payload": payload}
        if self.sink is not None:
            await self.sink(value)
