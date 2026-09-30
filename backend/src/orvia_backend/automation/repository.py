"""M18 审计只保存摘要和核验事实，执行内容/令牌不成为重启授权。"""

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from ..computer.paths import ToolError


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


class AutomationRepository:
    def __init__(self, store):
        self.store = store

    async def open(self):
        async with self.store._lock:
            db = self.store._db()
            await db.execute("""CREATE TABLE IF NOT EXISTS m18_operations(
                id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES missions(id),
                kind TEXT NOT NULL, revision TEXT NOT NULL, status TEXT NOT NULL,
                audit_json TEXT NOT NULL CHECK(json_valid(audit_json)),
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
            # 旧正在执行的步骤可能已有副作用；既不恢复内存授权，也不自动重放。
            await db.execute("UPDATE m18_operations SET status='interrupted',updated_at=? WHERE status IN ('running','verifying','awaiting_request','awaiting_verification','cancel_requested')", (now(),))

    async def create(self, cid, kind, revision, audit):
        operation_id = str(uuid4())
        async with self.store._lock:
            async with self.store._db().execute("SELECT COUNT(*) FROM m18_operations WHERE conversation_id=?", (cid,)) as cursor:
                if (await cursor.fetchone())[0] >= 100:
                    raise ToolError("BUDGET_EXCEEDED", "本会话自动化步骤预算已用完")
            stamp = now()
            await self.store._db().execute("INSERT INTO m18_operations VALUES(?,?,?,?,?,?,?,?)", (operation_id, cid, kind, revision, "awaiting_approval", json.dumps(audit, ensure_ascii=False), stamp, stamp))
        return operation_id

    async def get(self, cid, oid):
        async with self.store._lock:
            async with self.store._db().execute("SELECT * FROM m18_operations WHERE id=? AND conversation_id=?", (oid, cid)) as cursor:
                row = await cursor.fetchone()
        if row is None:
            raise ToolError("NOT_FOUND", "当前会话没有此自动化步骤")
        return {"operation_id": row["id"], "kind": row["kind"], "revision": row["revision"], "status": row["status"],
                "audit": json.loads(row["audit_json"]), "created_at": row["created_at"], "updated_at": row["updated_at"]}

    async def transition(self, cid, oid, expected, status, evidence=None):
        """条件更新形成一次性步骤；相同批准绝不再次派发动作。"""
        current = await self.get(cid, oid)
        audit = current["audit"]
        if evidence is not None:
            audit["evidence"] = evidence
        async with self.store._lock:
            placeholders = ",".join("?" for _ in expected)
            cursor = await self.store._db().execute(f"UPDATE m18_operations SET status=?,audit_json=?,updated_at=? WHERE id=? AND conversation_id=? AND status IN ({placeholders})",
                (status, json.dumps(audit, ensure_ascii=False), now(), oid, cid, *expected))
            if cursor.rowcount != 1:
                raise ToolError("INVALID_STATE", "自动化步骤已执行或状态发生变化")

    async def history(self, cid):
        async with self.store._lock:
            async with self.store._db().execute("SELECT id FROM m18_operations WHERE conversation_id=? ORDER BY created_at DESC LIMIT 20", (cid,)) as cursor:
                ids = [row[0] for row in await cursor.fetchall()]
        return {"operations": [await self.get(cid, oid) for oid in ids]}
