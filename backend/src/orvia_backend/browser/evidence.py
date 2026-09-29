"""M12 不可变来源版本与 M06 检索：网页始终是数据，不进入文件规划提示词。"""

import hashlib
import json

from ..computer.paths import ToolError
from ..context import ContextService


class EvidenceStore:
    def __init__(self, store, *, kind="browser"):
        self.store = store
        # 表名只能来自程序常量，不接受网页、附件或 renderer 输入。
        self.table = {"browser": "browser_evidence", "document": "document_evidence"}[kind]

    async def open(self):
        async with self.store._lock:
            await self.store._db().execute(f"""CREATE TABLE IF NOT EXISTS {self.table} (
                id TEXT PRIMARY KEY, mission_id TEXT NOT NULL REFERENCES missions(id),
                evidence_json TEXT NOT NULL CHECK(json_valid(evidence_json)))""")

    async def save(self, cid, item):
        """同任务、URL、模式和内容去重；变化内容保留独立版本，摘要不能覆盖正文。"""
        digest = hashlib.sha256(item.get("content", "").encode("utf-8")).hexdigest()
        identity = [cid, item.get("source_url"), item.get("mode"), digest,
                    item.get("title"), item.get("truncated", False), item.get("error")]
        value = await self.save_version(cid, {**item, "content_hash": digest}, identity)
        if value.get("content", "").strip():
            # 独立 source 标识使搜索摘要/HTTP/动态读取和内容版本在 FTS 中保持边界。
            await ContextService(self.store).index_text(cid, "browser:" + value["evidence_id"], value["content"])
        return value

    async def save_version(self, cid, item, identity):
        """M12/M13 共用不可变版本持久化，原时间戳与会话归属不会被重读改写。"""
        eid = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        value = {**item, "evidence_id": eid}
        async with self.store._lock:
            db = self.store._db()
            async with db.execute(f"SELECT evidence_json FROM {self.table} WHERE id=? AND mission_id=?", (eid, cid)) as cursor:
                existing = await cursor.fetchone()
            if existing:
                # 原访问时间作为引用事实保留；再次获取时间随新的会话事件记录。
                value = json.loads(existing[0])
            else:
                await db.execute(f"INSERT INTO {self.table} VALUES (?,?,?)", (eid, cid, json.dumps(value, ensure_ascii=False)))
        return value

    async def get(self, cid, eid):
        """证据 ID 不是权限；必须同时匹配当前会话。"""
        async with self.store._lock:
            async with self.store._db().execute(f"SELECT evidence_json FROM {self.table} WHERE id=? AND mission_id=?", (eid, cid)) as cursor:
                row = await cursor.fetchone()
        if row is None:
            raise ToolError("NOT_FOUND", "当前会话没有此来源")
        return json.loads(row[0])

    async def list(self, cid):
        async with self.store._lock:
            async with self.store._db().execute(f"SELECT evidence_json FROM {self.table} WHERE mission_id=? ORDER BY rowid DESC LIMIT 21", (cid,)) as cursor:
                rows = await cursor.fetchall()
        return [self.summary(json.loads(row[0])) for row in rows[:20]], len(rows) > 20

    @staticmethod
    def summary(value):
        """快照只带短摘录；全文通过受限详情接口单独读取，防止撑破协议帧。"""
        return {**value, "content": value.get("content", "")[:180],
                "preview_truncated": len(value.get("content", "")) > 180}

    async def search(self, cid, query):
        # M06 查询只取当前任务，引用还要反查不可变证据，排除其它上下文来源。
        found = await ContextService(self.store).search(cid, query, 20)
        items, seen = [], set()
        for hit in found["evidence"]:
            if not hit["source"].startswith("browser:"):
                continue
            eid = hit["source"].removeprefix("browser:")
            if eid in seen:
                continue
            value = await self.get(cid, eid)
            items.append({**self.summary(value), "content": hit["text"][:600],
                          "chunk_index": hit["chunk_index"], "preview_truncated": len(hit["text"]) > 600})
            seen.add(eid)
            if len(items) == 5:
                break
        return items
