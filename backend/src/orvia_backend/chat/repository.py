"""会话持久化复用应用数据库及串行事务锁，不另建无约束连接。"""

import json
from datetime import datetime, timezone
from uuid import uuid4

from ..computer.paths import ToolError
from ..storage import Store


class ChatRepository:
    def __init__(self, store: Store):
        self.store = store

    async def open(self):
        async with self.store._lock:
            db = self.store._db()
            await db.execute("""CREATE TABLE IF NOT EXISTS chat_conversations (
                id TEXT PRIMARY KEY REFERENCES missions(id), title TEXT NOT NULL,
                operation_id TEXT, thread_id TEXT, created_at TEXT NOT NULL)""")
            await db.execute("""CREATE TABLE IF NOT EXISTS chat_messages (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL,
                message_json TEXT NOT NULL)""")
            await db.execute("""CREATE TABLE IF NOT EXISTS chat_requests (
                conversation_id TEXT NOT NULL, request_id TEXT NOT NULL, text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                PRIMARY KEY(conversation_id, request_id))""")
            async with db.execute("PRAGMA table_info(chat_requests)") as cursor:
                columns = {row[1] for row in await cursor.fetchall()}
            if "status" not in columns:
                # 旧草稿没有可靠完成标记，不能把未知请求静默视为成功。
                await db.execute("ALTER TABLE chat_requests ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'")
            await db.execute("BEGIN IMMEDIATE")
            try:
                async with db.execute("SELECT conversation_id,request_id FROM chat_requests WHERE status = 'pending'") as cursor:
                    interrupted = await cursor.fetchall()
                for row in interrupted:
                    message = self._message("system", "上次消息处理被中断；未自动重发模型或网页请求。请先查看已保存来源、计划与结果，再用新消息继续。",
                                            "error", {"code": "REQUEST_INTERRUPTED", "request_id": row[1]})
                    await db.execute("INSERT INTO chat_messages(conversation_id,message_json) VALUES (?, ?)",
                                     (row[0], json.dumps(message, ensure_ascii=False)))
                await db.execute("UPDATE chat_requests SET status = 'interrupted' WHERE status = 'pending'")
                await db.commit()
            except BaseException:
                await db.rollback()
                raise

    async def create(self, mission):
        async with self.store._lock:
            await self.store._db().execute("INSERT OR IGNORE INTO chat_conversations VALUES (?, ?, NULL, NULL, ?)",
                                          (str(mission.id), mission.title, mission.created_at.isoformat()))

    async def get(self, conversation_id):
        async with self.store._lock:
            async with self.store._db().execute("SELECT * FROM chat_conversations WHERE id = ?", (conversation_id,)) as cursor:
                row = await cursor.fetchone()
            if row is None:
                raise ToolError("NOT_FOUND", "会话不存在")
            return dict(row)

    async def list(self):
        async with self.store._lock:
            async with self.store._db().execute("SELECT id,title FROM chat_conversations ORDER BY created_at DESC,id DESC LIMIT 100") as cursor:
                return [dict(row) for row in await cursor.fetchall()]

    async def bind(self, conversation_id, operation_id, thread_id):
        async with self.store._lock:
            await self.store._db().execute("UPDATE chat_conversations SET operation_id = ?,thread_id = ? WHERE id = ?",
                                          (operation_id, thread_id, conversation_id))

    async def claim(self, conversation_id, request_id, text):
        """先持久化请求占位，断线不自动重发模型；同一标识不能换文本。"""
        async with self.store._lock:
            db = self.store._db()
            async with db.execute("SELECT text,status FROM chat_requests WHERE conversation_id = ? AND request_id = ?", (conversation_id, request_id)) as cursor:
                existing = await cursor.fetchone()
            if existing:
                if existing[0] != text:
                    raise ToolError("CONFLICT", "消息标识已用于其他内容")
                if existing[1] not in {"completed", "cancelled", "failed"}:
                    raise ToolError("REQUEST_INTERRUPTED", "该消息尚未完成或曾被中断；不会自动重发，请检查现有结果后用新消息继续")
                return False
            async with db.execute("SELECT COUNT(*) FROM chat_requests WHERE conversation_id = ?", (conversation_id,)) as cursor:
                count = (await cursor.fetchone())[0]
            if count >= 100:
                raise ToolError("BUDGET_EXCEEDED", "会话消息预算已用完，请新建会话")
            await db.execute("INSERT INTO chat_requests(conversation_id,request_id,text,status) VALUES (?, ?, ?, 'pending')", (conversation_id, request_id, text))
            return True

    async def finish(self, conversation_id, request_id, status="completed"):
        """请求终态持久化；取消不会在重启后被重放。"""
        async with self.store._lock:
            await self.store._db().execute("UPDATE chat_requests SET status = ? WHERE conversation_id = ? AND request_id = ?",
                                          (status, conversation_id, request_id))

    @staticmethod
    def _message(role, text, kind, data):
        return {"id": str(uuid4()), "role": role, "text": text, "kind": kind, "data": data,
                "created_at": datetime.now(timezone.utc).isoformat()}

    async def append(self, conversation_id, role, text, kind="text", data=None):
        message = self._message(role, text, kind, data)
        async with self.store._lock:
            await self.store._db().execute("INSERT INTO chat_messages(conversation_id,message_json) VALUES (?, ?)",
                                          (conversation_id, json.dumps(message, ensure_ascii=False)))

    async def messages(self, conversation_id):
        async with self.store._lock:
            async with self.store._db().execute("SELECT message_json FROM chat_messages WHERE conversation_id = ? ORDER BY sequence DESC LIMIT 30", (conversation_id,)) as cursor:
                rows = await cursor.fetchall()
            async with self.store._db().execute("SELECT COUNT(*) FROM chat_messages WHERE conversation_id = ?", (conversation_id,)) as cursor:
                count = (await cursor.fetchone())[0]
            return [json.loads(row[0]) for row in reversed(rows)], count

    async def message(self, conversation_id, message_id):
        """按会话和消息双重身份读取已保存结果，不受最近 30 条快照裁剪影响。"""
        async with self.store._lock:
            async with self.store._db().execute(
                "SELECT message_json FROM chat_messages WHERE conversation_id = ? AND json_extract(message_json, '$.id') = ? LIMIT 1",
                (conversation_id, message_id),
            ) as cursor:
                row = await cursor.fetchone()
        if row is None:
            raise ToolError("NOT_FOUND", "当前会话没有此生成结果")
        return json.loads(row[0])

    async def latest_request_status(self, conversation_id):
        async with self.store._lock:
            async with self.store._db().execute("SELECT status FROM chat_requests WHERE conversation_id = ? ORDER BY rowid DESC LIMIT 1", (conversation_id,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    async def operations(self, conversation_id):
        """只返回有限任务摘要，不将根路径或文件身份带到渲染进程。"""
        async with self.store._lock:
            async with self.store._db().execute("SELECT id,plan_json,status,created_at,updated_at FROM operation_tasks WHERE mission_id = ? ORDER BY created_at DESC,id DESC LIMIT 11", (conversation_id,)) as cursor:
                rows = await cursor.fetchall()
        return [{"operation_id": row["id"], "revision": json.loads(row["plan_json"]).get("revision", ""),
                 "status": row["status"], "created_at": row["created_at"], "updated_at": row["updated_at"], "can_undo": False} for row in rows[:10]], len(rows) > 10
