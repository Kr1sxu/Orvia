"""基于 SQLite 的本地草稿存储；路径仅来自后端可信启动配置。"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import aiosqlite

from orvia_backend.domain import Mission, MissionCreate, get_profiles


class Store:
    """串行访问同一连接，保证迁移、幂等创建和读取互不穿插事务。"""

    def __init__(self, path: Path):
        self.path = path
        self._connection: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    def _db(self) -> aiosqlite.Connection:
        if self._connection is None:
            raise RuntimeError("store is not open")
        return self._connection

    async def open(self) -> None:
        """迁移在单一事务内完成；未知未来版本必须停止，不能覆盖。"""
        async with self._lock:
            if self._connection is not None:
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            db = await aiosqlite.connect(self.path, isolation_level=None)
            try:
                await db.execute("PRAGMA busy_timeout = 2000")
                await db.execute("PRAGMA foreign_keys = ON")
                await db.execute("PRAGMA journal_mode = WAL")
                await db.execute("BEGIN IMMEDIATE")
                async with db.execute("PRAGMA user_version") as cursor:
                    version = (await cursor.fetchone())[0]
                if version > 1:
                    raise ValueError("database schema version is newer than supported")
                if version == 0:
                    await db.execute("""CREATE TABLE missions (
                        id TEXT PRIMARY KEY,
                        client_request_id TEXT NOT NULL UNIQUE,
                        title TEXT NOT NULL,
                        status TEXT NOT NULL CHECK(status = 'draft'),
                        created_at TEXT NOT NULL,
                        models_json TEXT NOT NULL CHECK(json_valid(models_json))
                    )""")
                    await db.execute("""CREATE TRIGGER mission_models_immutable
                        BEFORE UPDATE OF models_json ON missions
                        WHEN NEW.models_json IS NOT OLD.models_json
                        BEGIN SELECT RAISE(ABORT, 'mission model snapshot is immutable'); END""")
                    await db.execute("PRAGMA user_version = 1")
                # M04 在 v1 数据库中追加账本表；不升高 user_version，保持已有 M02 数据库可打开。
                await db.execute("""CREATE TABLE IF NOT EXISTS operation_tasks (
                    id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    root TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('planned','approved','running','completed','failed','interrupted','undone','partially_undone')),
                    plan_json TEXT NOT NULL CHECK(json_valid(plan_json)),
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )""")
                await db.execute("""CREATE TABLE IF NOT EXISTS operation_entries (
                    task_id TEXT NOT NULL REFERENCES operation_tasks(id) ON DELETE CASCADE,
                    sequence INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    source TEXT,
                    destination TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('planned','completed','failed','undone')),
                    before_json TEXT,
                    after_json TEXT,
                    error TEXT,
                    PRIMARY KEY(task_id, sequence)
                )""")
                await db.execute("""CREATE TABLE IF NOT EXISTS context_documents (
                    id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    chunk_count INTEGER NOT NULL
                )""")
                await db.execute("""CREATE TABLE IF NOT EXISTS context_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id TEXT NOT NULL REFERENCES context_documents(id) ON DELETE CASCADE,
                    mission_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    UNIQUE(document_id, chunk_index)
                )""")
                await db.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS context_fts USING fts5(
                    tokens, mission_id UNINDEXED, document_id UNINDEXED, chunk_index UNINDEXED
                )""")
                await db.execute("""CREATE TABLE IF NOT EXISTS context_preferences (
                    mission_id TEXT NOT NULL,
                    preference_key TEXT NOT NULL,
                    preference_value TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(mission_id, preference_key)
                )""")
                await db.execute("""CREATE TABLE IF NOT EXISTS context_summaries (
                    mission_id TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                )""")
                await db.commit()
            except BaseException:
                # 初始化失败必须释放连接；原异常交给服务层分类，不静默兜底。
                await db.rollback()
                await db.close()
                raise
            db.row_factory = aiosqlite.Row
            self._connection = db

    async def close(self) -> None:
        """等待当前事务后关闭连接；重复关闭不会改变数据。"""
        async with self._lock:
            if self._connection is not None:
                await self._connection.close()
                self._connection = None

    @staticmethod
    def _decode(row: aiosqlite.Row) -> Mission:
        # 磁盘数据仍是不可信输入，损坏快照必须失败，不能改用当前配置。
        values = dict(row)
        values["models"] = json.loads(values.pop("models_json"))
        return Mission.model_validate(values)

    async def create_mission(self, request: MissionCreate) -> Mission:
        """相同请求返回原草稿；同一标识不同内容明确报错，不泄露原文。"""
        async with self._lock:
            db = self._db()
            await db.execute("BEGIN IMMEDIATE")
            try:
                async with db.execute("SELECT * FROM missions WHERE client_request_id = ?", (str(request.client_request_id),)) as cursor:
                    row = await cursor.fetchone()
                if row is not None:
                    mission = self._decode(row)
                    if mission.title != request.title:
                        raise ValueError("client_request_id already used with different content")
                else:
                    mission = Mission(**request.model_dump(), id=uuid4(), status="draft", created_at=datetime.now(timezone.utc), models=get_profiles())
                    await db.execute("INSERT INTO missions VALUES (?, ?, ?, ?, ?, ?)", (
                        str(mission.id), str(mission.client_request_id), mission.title, mission.status,
                        mission.created_at.isoformat(), json.dumps([profile.model_dump() for profile in mission.models]),
                    ))
                await db.commit()
                return mission
            except BaseException:
                await db.rollback()
                raise

    async def get_mission(self, mission_id: str) -> Mission | None:
        """按标识返回经契约复核的草稿；不存在时返回 None。"""
        async with self._lock:
            async with self._db().execute("SELECT * FROM missions WHERE id = ?", (mission_id,)) as cursor:
                row = await cursor.fetchone()
            return self._decode(row) if row is not None else None

    async def list_missions(self) -> list[Mission]:
        """按创建时间倒序返回最多 20 个草稿，限制跨进程响应大小。"""
        async with self._lock:
            async with self._db().execute("SELECT * FROM missions ORDER BY created_at DESC, id DESC LIMIT 20") as cursor:
                rows = await cursor.fetchall()
            return [self._decode(row) for row in rows]

    async def create_operation(self, operation: dict) -> None:
        """持久化不可变计划和账本初始条目；调用方已完成路径与契约校验。"""
        async with self._lock:
            db = self._db()
            await db.execute("BEGIN IMMEDIATE")
            try:
                await db.execute("INSERT INTO operation_tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (
                    operation["id"], operation["mission_id"], operation["root"], operation["status"],
                    json.dumps(operation["plan"], ensure_ascii=False), None,
                    operation["created_at"], operation["created_at"],
                ))
                for entry in operation["plan"]["actions"]:
                    await db.execute("INSERT INTO operation_entries(task_id, sequence, kind, source, destination, status) VALUES (?, ?, ?, ?, ?, ?)",
                                     (operation["id"], entry["sequence"], entry["kind"], entry.get("source"), entry["destination"], "planned"))
                await db.commit()
            except BaseException:
                await db.rollback()
                raise

    async def get_operation(self, operation_id: str) -> dict | None:
        """读取计划及逐步状态，供恢复和撤销重新核验，不信任调用方缓存。"""
        async with self._lock:
            async with self._db().execute("SELECT * FROM operation_tasks WHERE id = ?", (operation_id,)) as cursor:
                task = await cursor.fetchone()
            if task is None:
                return None
            async with self._db().execute("SELECT * FROM operation_entries WHERE task_id = ? ORDER BY sequence", (operation_id,)) as cursor:
                entries = [dict(row) for row in await cursor.fetchall()]
            result = dict(task)
            result["plan"] = json.loads(result.pop("plan_json"))
            result["entries"] = entries
            return result

    async def get_latest_operation(self, mission_id: str) -> dict | None:
        """仅按任务创建时间取最近一条账本，供受限撤销使用。"""
        async with self._lock:
            async with self._db().execute(
                "SELECT id FROM operation_tasks WHERE mission_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
                (mission_id,),
            ) as cursor:
                row = await cursor.fetchone()
            operation_id = row[0] if row is not None else None
        return await self.get_operation(operation_id) if operation_id is not None else None

    async def update_operation(self, operation_id: str, status: str, *, error: str | None = None,
                               sequence: int | None = None, entry_status: str | None = None,
                               before: dict | None = None, after: dict | None = None) -> None:
        """以单事务更新任务和一个账本条目，崩溃后不会产生半条记录。"""
        async with self._lock:
            db = self._db()
            await db.execute("BEGIN IMMEDIATE")
            try:
                now = datetime.now(timezone.utc).isoformat()
                await db.execute("UPDATE operation_tasks SET status = ?, error = ?, updated_at = ? WHERE id = ?",
                                 (status, error, now, operation_id))
                if sequence is not None and entry_status is not None:
                    await db.execute("UPDATE operation_entries SET status = ?, before_json = ?, after_json = ?, error = ? WHERE task_id = ? AND sequence = ?",
                                     (entry_status, json.dumps(before, ensure_ascii=False) if before else None,
                                      json.dumps(after, ensure_ascii=False) if after else None, error, operation_id, sequence))
                await db.commit()
            except BaseException:
                await db.rollback()
                raise

    async def recover_operations(self) -> list[str]:
        """后端重启时将未完成任务标成 interrupted，等待用户明确恢复或撤销。"""
        async with self._lock:
            db = self._db()
            await db.execute("BEGIN IMMEDIATE")
            try:
                async with db.execute("SELECT id FROM operation_tasks WHERE status IN ('running','approved')") as cursor:
                    ids = [row[0] for row in await cursor.fetchall()]
                if ids:
                    await db.execute("UPDATE operation_tasks SET status = 'interrupted', error = '后端连接中断，需重新核验', updated_at = ? WHERE status IN ('running','approved')",
                                     (datetime.now(timezone.utc).isoformat(),))
                await db.commit()
                return ids
            except BaseException:
                await db.rollback()
                raise

    async def replace_context_document(self, document: dict, chunks: list[dict], tokenized: list[str]) -> None:
        """按来源原子替换任务范围内的文本块和 FTS 行，避免半次索引可见。"""
        async with self._lock:
            db = self._db()
            await db.execute("BEGIN IMMEDIATE")
            try:
                # 分词可能跨越会话删除；在最终写事务内核对墓碑，晚到索引不能复活正文。
                # 独立目录Mission没有chat记录，仍可使用原有索引接口。
                async with db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='chat_deletions'") as cursor:
                    has_deletions = await cursor.fetchone() is not None
                if has_deletions:
                    async with db.execute("SELECT 1 FROM chat_deletions WHERE id=?", (document["mission_id"],)) as cursor:
                        if await cursor.fetchone() is not None:
                            raise ValueError("会话已删除，晚到上下文不能写回")
                async with db.execute("SELECT id FROM context_documents WHERE mission_id = ? AND source = ?",
                                      (document["mission_id"], document["source"])) as cursor:
                    old = await cursor.fetchone()
                if old is not None:
                    await db.execute("DELETE FROM context_fts WHERE document_id = ?", (old[0],))
                    await db.execute("DELETE FROM context_documents WHERE id = ?", (old[0],))
                await db.execute("INSERT INTO context_documents VALUES (?, ?, ?, ?, ?, ?)",
                                 (document["id"], document["mission_id"], document["source"], document["content_hash"],
                                  document["updated_at"], len(chunks)))
                for chunk, indexed in zip(chunks, tokenized, strict=True):
                    await db.execute("INSERT INTO context_chunks(id, document_id, mission_id, chunk_index, content) VALUES (?, ?, ?, ?, ?)",
                                     (chunk["id"], document["id"], document["mission_id"], chunk["chunk_index"], chunk["content"]))
                    await db.execute("INSERT INTO context_fts(rowid, tokens, mission_id, document_id, chunk_index) VALUES (?, ?, ?, ?, ?)",
                                     (chunk["id"], indexed, document["mission_id"], document["id"], chunk["chunk_index"]))
                await db.commit()
            except BaseException:
                await db.rollback()
                raise

    async def search_context(self, mission_id: str, match_query: str, limit: int) -> list[dict]:
        """仅在指定 Mission 的 FTS5 范围内检索，并返回原文块和来源。"""
        async with self._lock:
            async with self._db().execute(
                """SELECT c.document_id, d.source, c.chunk_index, c.content, bm25(context_fts) AS score
                   FROM context_fts JOIN context_chunks c ON c.id = context_fts.rowid
                   JOIN context_documents d ON d.id = c.document_id
                   WHERE context_fts MATCH ? AND context_fts.mission_id = ?
                   ORDER BY score LIMIT ?""", (match_query, mission_id, limit)) as cursor:
                return [dict(row) for row in await cursor.fetchall()]

    async def clear_context(self, mission_id: str, source: str | None = None) -> int:
        """删除任务范围内的索引及原文块；不触碰用户原文件。"""
        async with self._lock:
            db = self._db()
            await db.execute("BEGIN IMMEDIATE")
            try:
                if source is None:
                    async with db.execute("SELECT id FROM context_documents WHERE mission_id = ?", (mission_id,)) as cursor:
                        ids = [row[0] for row in await cursor.fetchall()]
                    await db.execute("DELETE FROM context_documents WHERE mission_id = ?", (mission_id,))
                else:
                    async with db.execute("SELECT id FROM context_documents WHERE mission_id = ? AND source = ?", (mission_id, source)) as cursor:
                        ids = [row[0] for row in await cursor.fetchall()]
                    await db.execute("DELETE FROM context_documents WHERE mission_id = ? AND source = ?", (mission_id, source))
                for document_id in ids:
                    await db.execute("DELETE FROM context_fts WHERE document_id = ?", (document_id,))
                await db.commit()
                return len(ids)
            except BaseException:
                await db.rollback()
                raise

    async def set_preference(self, mission_id: str, key: str, value: str) -> None:
        async with self._lock:
            await self._db().execute("INSERT INTO context_preferences VALUES (?, ?, ?, ?) ON CONFLICT(mission_id, preference_key) DO UPDATE SET preference_value = excluded.preference_value, updated_at = excluded.updated_at",
                                     (mission_id, key, value, datetime.now(timezone.utc).isoformat()))

    async def get_preferences(self, mission_id: str) -> dict[str, str]:
        async with self._lock:
            async with self._db().execute("SELECT preference_key, preference_value FROM context_preferences WHERE mission_id = ? ORDER BY preference_key", (mission_id,)) as cursor:
                return {row[0]: row[1] for row in await cursor.fetchall()}

    async def update_summary(self, mission_id: str, summary: str, revision: int) -> None:
        async with self._lock:
            await self._db().execute("INSERT INTO context_summaries VALUES (?, ?, ?, ?) ON CONFLICT(mission_id) DO UPDATE SET summary = excluded.summary, revision = excluded.revision, updated_at = excluded.updated_at",
                                     (mission_id, summary, revision, datetime.now(timezone.utc).isoformat()))

    async def get_summary(self, mission_id: str) -> dict | None:
        async with self._lock:
            async with self._db().execute("SELECT mission_id, summary, revision, updated_at FROM context_summaries WHERE mission_id = ?", (mission_id,)) as cursor:
                row = await cursor.fetchone()
            return dict(row) if row is not None else None
