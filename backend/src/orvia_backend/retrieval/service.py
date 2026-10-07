"""SQLite 原文、FTS5 和固定 Qwen 向量融合；不读取原文件、不访问网络。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import struct
from time import monotonic

from ..context.service import ContextService
from ..storage import Store


MODEL_REVISION = "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"
PREPROCESS = "qwen-lasttoken-v1"
DIMENSION = 1024
SIGNATURE = f"Qwen/Qwen3-Embedding-0.6B@{MODEL_REVISION}:{DIMENSION}:{PREPROCESS}"
LIMITS = {"sources": 150, "mission_chunks": 512, "global_chunks": 4096, "embedding_batch": 8,
          "vector_read_batch": 128, "text_chars": 600, "batch_seconds": 30, "total_seconds": 120,
          "candidates": 512, "output_bytes": 32 * 1024}
VECTOR_FORMAT = "<" + "f" * DIMENSION


class RetrievalError(ValueError):
    """稳定的输入/范围错误，避免暴露正文及运行时系统异常。"""

    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


def _fail(code, message):
    raise RetrievalError(code, message)


def _hash(text):
    try:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    except UnicodeEncodeError:
        _fail("RETRIEVAL_TEXT", "原文包含无效Unicode字符")


def _bytes(value):
    return len(json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8"))


def _vector(values):
    """拒绝维度、非有限值和零向量；单位化后以固定little-endian float32存储。"""
    if not isinstance(values, list) or len(values) != DIMENSION:
        _fail("RETRIEVAL_VECTOR", "嵌入维度不符合固定1024维契约")
    numbers = []
    for value in values:
        if type(value) not in (float, int):
            _fail("RETRIEVAL_VECTOR", "嵌入包含非有限值或非法数值类型")
        try:
            number = float(value)
        except OverflowError:
            _fail("RETRIEVAL_VECTOR", "嵌入数值超过浮点范围")
        if not math.isfinite(number):
            _fail("RETRIEVAL_VECTOR", "嵌入包含非有限值或非法数值类型")
        numbers.append(number)
    norm = math.hypot(*numbers)
    if not math.isfinite(norm) or norm <= 0:
        _fail("RETRIEVAL_VECTOR", "嵌入不能为零或非有限向量")
    try:
        blob = struct.pack(VECTOR_FORMAT, *(value / norm for value in numbers))
    except (OverflowError, struct.error):
        _fail("RETRIEVAL_VECTOR", "嵌入不能编码为float32")
    return blob


def _decode(blob):
    if not isinstance(blob, bytes) or len(blob) != DIMENSION * 4:
        _fail("RETRIEVAL_VECTOR", "向量BLOB长度无效")
    values = struct.unpack(VECTOR_FORMAT, blob)
    if any(not math.isfinite(value) for value in values) or abs(math.hypot(*values) - 1) > 1e-4:
        _fail("RETRIEVAL_VECTOR", "持久化向量未通过有限值和归一化核验")
    return values


class RetrievalService:
    """只对调用方明确提供的Mission/来源检索已存原文，模型运行与SQLite锁隔离。"""

    def __init__(self, store: Store, embedder):
        self.store, self.embedder = store, embedder
        self._rebuild_lock = asyncio.Lock()
        self._has_deletions = False

    async def open(self):
        """向量逐片段FK级联删除；迁移不改变已有user_version且不加载模型依赖。"""
        async with self.store._lock:
            db = self.store._db()
            await db.execute("BEGIN IMMEDIATE")
            try:
                await db.execute("""CREATE TABLE IF NOT EXISTS retrieval_vectors(
                    chunk_id INTEGER PRIMARY KEY REFERENCES context_chunks(id) ON DELETE CASCADE,
                    mission_id TEXT NOT NULL,document_id TEXT NOT NULL,document_hash TEXT NOT NULL,
                    content_hash TEXT NOT NULL,signature TEXT NOT NULL,model_revision TEXT NOT NULL,
                    dimension INTEGER NOT NULL CHECK(dimension=1024),preprocess TEXT NOT NULL,
                    vector BLOB NOT NULL CHECK(length(vector)=4096))""")
                await db.execute("CREATE INDEX IF NOT EXISTS retrieval_vectors_mission ON retrieval_vectors(mission_id,signature)")
                await db.execute("CREATE TABLE IF NOT EXISTS retrieval_epochs(mission_id TEXT PRIMARY KEY,generation INTEGER NOT NULL)")
                async with db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='chat_deletions'") as cursor:
                    self._has_deletions = await cursor.fetchone() is not None
                await db.commit()
            except BaseException:
                await db.rollback()
                raise

    @staticmethod
    def _scope(mission_id, sources):
        mission_id = ContextService._mission(mission_id)
        if sources is not None:
            if not isinstance(sources, list) or not 0 <= len(sources) <= LIMITS["sources"]:
                _fail("RETRIEVAL_SCOPE", "来源范围必须为0～150个明确标签")
            sources = [ContextService._source(source) for source in sources]
            if len(set(sources)) != len(sources):
                _fail("RETRIEVAL_SCOPE", "来源范围不允许重复标签")
            sources = sorted(sources)
            if _bytes(sources) > 48 * 1024:
                _fail("RETRIEVAL_SCOPE", "准确来源标签合计超过48KiB预算")
        return mission_id, sources

    async def _not_deleted(self, db, mission_id):
        # 服务可单独使用；聊天表存在时，删除日志阻止晚到索引任务恢复被删身份。
        if self._has_deletions:
            async with db.execute("SELECT 1 FROM chat_deletions WHERE id=?", (mission_id,)) as cursor:
                if await cursor.fetchone():
                    _fail("RETRIEVAL_DELETED", "所属会话已删除，不再提供索引或检索")

    @staticmethod
    def _where(mission_id, sources):
        where, params = "c.mission_id=? AND d.mission_id=?", [mission_id, mission_id]
        if sources is not None:
            where += " AND d.source IN (" + ",".join("?" for _ in sources) + ")"
            params += sources
        return where, params

    async def _source_count(self, db, mission_id, sources):
        where, params = self._where(mission_id, sources)
        async with db.execute("SELECT DISTINCT d.source FROM context_chunks c JOIN context_documents d ON d.id=c.document_id WHERE " + where + " LIMIT " + str(LIMITS["sources"] + 1), params) as cursor:
            count = len(await cursor.fetchall())
        if count > LIMITS["sources"]:
            _fail("RETRIEVAL_SCOPE", "当前任务超过150个来源，请明确缩小范围")
        return count

    @staticmethod
    async def _epoch(db, mission_id):
        async with db.execute("SELECT generation FROM retrieval_epochs WHERE mission_id=?", [mission_id]) as cursor:
            row = await cursor.fetchone()
        return row[0] if row else 0

    async def _snapshot(self, db, mission_id, sources):
        await self._not_deleted(db, mission_id)
        await self._source_count(db, mission_id, sources)
        where, params = self._where(mission_id, sources)
        async with db.execute("""SELECT c.id,c.document_id,c.chunk_index,substr(c.content,1,601),d.source,d.content_hash
            FROM context_chunks c JOIN context_documents d ON d.id=c.document_id WHERE """ + where + " ORDER BY c.id LIMIT 513", params) as cursor:
            rows = await cursor.fetchall()
        return [{"chunk_id": row[0], "document_id": row[1], "chunk_index": row[2], "text": row[3],
                 "source": row[4], "document_hash": row[5], "content_hash": _hash(row[3])} for row in rows]

    def _runtime(self):
        """运行时只能声明固定已核验模型；缺模型或签名变化明确降级，不自动准备或下载。"""
        if getattr(self.embedder, "signature", None) != SIGNATURE:
            return False, "MODEL_SIGNATURE_MISMATCH"
        try:
            state = self.embedder.status()
        except (ValueError, RuntimeError, OSError):
            return False, "MODEL_UNAVAILABLE"
        if not isinstance(state, dict) or type(state.get("ready")) is not bool:
            return False, "MODEL_STATUS_INVALID"
        if state.get("signature", SIGNATURE) != SIGNATURE:
            return False, "MODEL_SIGNATURE_MISMATCH"
        reason = state.get("reason")
        if reason is not None and (not isinstance(reason, str) or len(reason) > 100):
            return False, "MODEL_STATUS_INVALID"
        return state["ready"], None if state["ready"] else reason or "MODEL_UNAVAILABLE"

    async def status(self, mission_id=None):
        if mission_id is not None:
            mission_id = ContextService._mission(mission_id)
        ready, reason = self._runtime()
        async with self.store._lock:
            db = self.store._db()
            if mission_id is not None:
                await self._not_deleted(db, mission_id)
            where, params = (" WHERE mission_id=?", [mission_id]) if mission_id is not None else ("", [])
            async with db.execute("SELECT count(*) FROM retrieval_vectors" + where, params) as cursor:
                count = (await cursor.fetchone())[0]
        return {"ready": ready, "reason": reason, "signature": SIGNATURE, "model_revision": MODEL_REVISION,
                "dimension": DIMENSION, "preprocess": PREPROCESS, "indexed_chunks": count,
                "mission_id": mission_id, "limits": dict(LIMITS)}

    async def _embed(self, texts, query, remaining=120):
        if len(texts) > LIMITS["embedding_batch"]:
            _fail("RETRIEVAL_LIMIT", "嵌入批次超过8段")
        ready, reason = self._runtime()
        if not ready:
            _fail("RETRIEVAL_MODEL", reason)
        values = await asyncio.wait_for(self.embedder.embed(texts, query=query), min(remaining, LIMITS["batch_seconds"]))
        ready, reason = self._runtime()
        if not ready:
            _fail("RETRIEVAL_MODEL", reason)
        if not isinstance(values, list) or len(values) != len(texts):
            _fail("RETRIEVAL_VECTOR", "嵌入批次数量不符合输入")
        return [_vector(value) for value in values]

    async def rebuild(self, mission_id, sources=None):
        """120秒总预算包含等待和数据库核验；空范围不扩大成历史任务全集。"""
        mission_id, sources = self._scope(mission_id, sources)
        started = monotonic()
        if sources == []:
            async with self.store._lock:
                await self._not_deleted(self.store._db(), mission_id)
            return {"mission_id": mission_id, "status": "keyword_only", "reason": "SCOPE_EMPTY", "indexed_chunks": 0,
                    "unique_texts": 0, "signature": SIGNATURE}
        try:
            return await asyncio.wait_for(self._rebuild(mission_id, sources, started), LIMITS["total_seconds"])
        except asyncio.TimeoutError:
            return {"mission_id": mission_id, "status": "failed", "reason": "RETRIEVAL_TIMEOUT", "indexed_chunks": 0,
                    "unique_texts": 0, "signature": SIGNATURE}

    async def _rebuild(self, mission_id, sources, started):
        """先取不可变快照、锁外本地嵌入，提交时重查完整版本；失败不写入部分索引。"""
        async with self._rebuild_lock:
            ready, reason = self._runtime()
            response = {"mission_id": mission_id, "status": "keyword_only", "reason": reason,
                        "indexed_chunks": 0, "unique_texts": 0, "signature": SIGNATURE}
            async with self.store._lock:
                snapshot = await self._snapshot(self.store._db(), mission_id, sources)
                epoch = await self._epoch(self.store._db(), mission_id)
            if not ready:
                return response
            if len(snapshot) > LIMITS["mission_chunks"]:
                return {**response, "reason": "INDEX_MISSION_LIMIT"}
            if any(not row["text"].strip() or len(row["text"]) > LIMITS["text_chars"] for row in snapshot):
                return {**response, "reason": "INDEX_TEXT_LIMIT"}
            unique = {row["content_hash"]: row["text"] for row in snapshot}
            vectors = {}
            hashes = list(unique)
            try:
                for start in range(0, len(hashes), LIMITS["embedding_batch"]):
                    remaining = LIMITS["total_seconds"] - (monotonic() - started)
                    if remaining <= 0:
                        raise asyncio.TimeoutError
                    batch = hashes[start:start + LIMITS["embedding_batch"]]
                    encoded = await self._embed([unique[digest] for digest in batch], False, remaining)
                    vectors.update(zip(batch, encoded, strict=True))
                if monotonic() - started > LIMITS["total_seconds"]:
                    raise asyncio.TimeoutError
                ready, reason = self._runtime()
                if not ready:
                    return {**response, "reason": reason, "status": "failed"}
                async with self.store._lock:
                    db = self.store._db()
                    await db.execute("BEGIN IMMEDIATE")
                    try:
                        current = await self._snapshot(db, mission_id, sources)
                        if current != snapshot or epoch != await self._epoch(db, mission_id):
                            _fail("RETRIEVAL_CHANGED", "来源或正文版本已变化，旧嵌入结果不写回")
                        where, params = self._where(mission_id, sources)
                        scope_sql = "SELECT c.id FROM context_chunks c JOIN context_documents d ON d.id=c.document_id WHERE " + where
                        async with db.execute("SELECT count(*) FROM retrieval_vectors WHERE chunk_id IN (" + scope_sql + ")", params) as cursor:
                            replaced = (await cursor.fetchone())[0]
                        async with db.execute("SELECT count(*),sum(CASE WHEN mission_id=? THEN 1 ELSE 0 END) FROM retrieval_vectors", [mission_id]) as cursor:
                            total, mission_total = await cursor.fetchone()
                        if total - replaced + len(snapshot) > LIMITS["global_chunks"]:
                            _fail("RETRIEVAL_GLOBAL_LIMIT", "全库向量超过4096段，请先清理索引")
                        if (mission_total or 0) - replaced + len(snapshot) > LIMITS["mission_chunks"]:
                            _fail("RETRIEVAL_MISSION_LIMIT", "本任务向量超过512段，请先清理索引")
                        await db.execute("DELETE FROM retrieval_vectors WHERE chunk_id IN (" + scope_sql + ")", params)
                        await db.executemany("INSERT INTO retrieval_vectors VALUES(?,?,?,?,?,?,?,?,?,?)", [
                            (row["chunk_id"], mission_id, row["document_id"], row["document_hash"], row["content_hash"], SIGNATURE,
                             MODEL_REVISION, DIMENSION, PREPROCESS, vectors[row["content_hash"]]) for row in snapshot])
                        await db.commit()
                    except BaseException:
                        await db.rollback()
                        raise
            except asyncio.TimeoutError:
                return {**response, "status": "failed", "reason": "EMBEDDING_TIMEOUT"}
            except RetrievalError as exc:
                return {**response, "status": "failed", "reason": exc.message if exc.code == "RETRIEVAL_MODEL" else exc.code}
            except (ValueError, RuntimeError, OSError):
                return {**response, "status": "failed", "reason": "EMBEDDING_FAILED"}
            return {**response, "status": "completed", "reason": None, "indexed_chunks": len(snapshot), "unique_texts": len(unique)}

    async def clear(self, mission_id, sources=None):
        """只删除派生向量，保留SQLite原文/FTS、原文件及导出成品。"""
        mission_id, sources = self._scope(mission_id, sources)
        async with self.store._lock:
            db = self.store._db()
            await self._not_deleted(db, mission_id)
            if sources == []:
                return {"mission_id": mission_id, "removed_vectors": 0}
            if sources is None:
                sql, params = "DELETE FROM retrieval_vectors WHERE mission_id=?", [mission_id]
            else:
                where, params = self._where(mission_id, sources)
                sql = "DELETE FROM retrieval_vectors WHERE chunk_id IN (SELECT c.id FROM context_chunks c JOIN context_documents d ON d.id=c.document_id WHERE " + where + ")"
            await db.execute("BEGIN IMMEDIATE")
            try:
                # 删除与epoch一起提交，任何较早开始的锁外嵌入不能在clear之后重新写回。
                await db.execute("""INSERT INTO retrieval_epochs VALUES(?,1)
                    ON CONFLICT(mission_id) DO UPDATE SET generation=generation+1""", [mission_id])
                cursor = await db.execute(sql, params)
                await db.commit()
                return {"mission_id": mission_id, "removed_vectors": cursor.rowcount}
            except BaseException:
                await db.rollback()
                raise

    async def _candidates(self, mission_id, sources, query):
        """FTS最多512候选，向量每批128条读取；SQL先限定任务和准确来源范围。"""
        tokens = list(dict.fromkeys(ContextService._tokens(query).split()))[:32]
        match = " OR ".join('"' + token.replace('"', '') + '"' for token in tokens)
        chunks, keyword, vectors, invalid = {}, [], {}, None
        async with self.store._lock:
            db = self.store._db()
            await self._not_deleted(db, mission_id)
            source_count = await self._source_count(db, mission_id, sources)
            epoch = await self._epoch(db, mission_id)
            where, params = self._where(mission_id, sources)
            if match:
                async with db.execute("""SELECT c.id,c.document_id,c.chunk_index,c.content,d.source,d.content_hash
                    FROM context_fts JOIN context_chunks c ON c.id=context_fts.rowid JOIN context_documents d ON d.id=c.document_id
                    WHERE context_fts MATCH ? AND context_fts.mission_id=? AND length(c.content)<=600 AND """ + where + " ORDER BY bm25(context_fts),c.id LIMIT 512", [match, mission_id, *params]) as cursor:
                    rows = await cursor.fetchall()
                for row in rows:
                    cid = row[0]
                    chunks[cid] = {"chunk_id": cid, "document_id": row[1], "chunk_index": row[2], "text": row[3], "source": row[4], "document_hash": row[5], "content_hash": _hash(row[3])}
                    keyword.append(cid)
            async with db.execute("""SELECT c.id,c.document_id,c.chunk_index,substr(c.content,1,601),d.source,d.content_hash,
                v.document_id,v.document_hash,v.content_hash,v.signature,v.model_revision,v.dimension,v.preprocess,v.vector
                FROM retrieval_vectors v JOIN context_chunks c ON c.id=v.chunk_id JOIN context_documents d ON d.id=c.document_id
                WHERE v.mission_id=? AND """ + where + " ORDER BY c.id LIMIT 513", [mission_id, *params]) as cursor:
                count = 0
                while True:
                    rows = await cursor.fetchmany(LIMITS["vector_read_batch"])
                    if not rows:
                        break
                    for row in rows:
                        count += 1
                        if count > LIMITS["candidates"]:
                            invalid = "INDEX_MISSION_LIMIT"
                            break
                        cid, docid, chunk_index, text, source, doc_hash = row[:6]
                        if len(text) > LIMITS["text_chars"]:
                            invalid = "INDEX_TEXT_LIMIT"
                            continue
                        digest = _hash(text)
                        if (docid != row[6] or doc_hash != row[7] or digest != row[8]):
                            invalid = "INDEX_SOURCE_CHANGED"
                            continue
                        if (row[9], row[10], row[11], row[12]) != (SIGNATURE, MODEL_REVISION, DIMENSION, PREPROCESS):
                            invalid = "INDEX_VERSION_MISMATCH"
                            continue
                        try:
                            vector = _decode(row[13])
                        except RetrievalError:
                            invalid = "INDEX_VECTOR_INVALID"
                            continue
                        vectors[cid] = vector
                        chunks[cid] = {"chunk_id": cid, "document_id": docid, "chunk_index": chunk_index, "text": text, "source": source, "document_hash": doc_hash, "content_hash": digest}
            # 两通道各512时不能将候选总数变成1024：保留关键词优先和其余有界向量候选。
            allowed = list(dict.fromkeys(keyword + list(vectors)))[:LIMITS["candidates"]]
            chunks = {cid: chunks[cid] for cid in allowed}
            keyword = [cid for cid in keyword if cid in chunks]
            vectors = {cid: vector for cid, vector in vectors.items() if cid in chunks}
        return chunks, keyword, vectors, invalid, source_count, epoch

    async def search(self, mission_id, query, limit=5, sources=None):
        """关键词和余弦独立排名，以RRF(k=60)融合；相似度仅用于召回而不证明事实。"""
        mission_id, sources = self._scope(mission_id, sources)
        if not isinstance(query, str) or not query.strip() or len(query) > 200 or "\x00" in query:
            _fail("RETRIEVAL_QUERY", "检索问题必须为1～200字符")
        if type(limit) is not int or not 1 <= limit <= 20:
            _fail("RETRIEVAL_LIMIT", "返回数量必须为1～20")
        _hash(query)
        if sources == []:
            async with self.store._lock:
                await self._not_deleted(self.store._db(), mission_id)
            return {"mission_id": mission_id, "query": query, "status": "keyword_only", "reason": "SCOPE_EMPTY", "evidence": [],
                    "coverage": {"indexed_chunks": 0, "candidate_chunks": 0, "scope_sources": 0, "output_limited": False}}
        query_vector, reason = None, None
        ready, reason = self._runtime()
        chunks, keyword, vectors, invalid, source_count, epoch = await self._candidates(mission_id, sources, query)
        if invalid:
            reason = invalid
        if not vectors:
            reason = reason or "INDEX_MISSING"
        # 没有可使用的固定版本索引时直接关键词返回，避免不必要的昂贵查询嵌入。
        if ready and vectors and not invalid:
            try:
                query_vector = _decode((await self._embed([query], True))[0])
            except asyncio.TimeoutError:
                reason = "EMBEDDING_TIMEOUT"
            except RetrievalError as exc:
                reason = exc.message if exc.code == "RETRIEVAL_MODEL" else exc.code
            except (ValueError, RuntimeError, OSError):
                reason = "EMBEDDING_FAILED"
            current_chunks, current_keyword, current_vectors, current_invalid, current_source_count, current_epoch = await self._candidates(mission_id, sources, query)
            if epoch != current_epoch or chunks != current_chunks or vectors != current_vectors or current_invalid:
                reason, query_vector = current_invalid or "INDEX_CHANGED", None
            chunks, keyword, vectors, source_count = current_chunks, current_keyword, current_vectors, current_source_count
        status = "hybrid" if query_vector is not None else "keyword_only"
        # 同一正文只占每通道一个排名位；完整来源关系仍在SQLite片段FK中保留。
        grouped = {}
        for cid, chunk in chunks.items():
            grouped.setdefault(chunk["content_hash"], []).append(cid)
        scores, channels = {}, {}
        def rank(ids, channel):
            seen = set()
            for cid in ids:
                digest = chunks[cid]["content_hash"]
                if digest in seen:
                    continue
                seen.add(digest)
                scores[digest] = scores.get(digest, 0.0) + 1.0 / (60 + len(seen))
                channels.setdefault(digest, []).append(channel)
        rank(keyword, "keyword")
        if query_vector is not None:
            similarity = {cid: max(-1.0, min(1.0, math.fsum(a * b for a, b in zip(query_vector, vector, strict=True)))) for cid, vector in vectors.items()}
            rank(sorted(similarity, key=lambda cid: (-similarity[cid], cid)), "vector")
        evidence, output_limited = [], False
        for digest in sorted(scores, key=lambda value: (-scores[value], min(grouped[value]))):
            ids = sorted(grouped[digest])
            chunk = chunks[ids[0]]
            item = {key: chunk[key] for key in ("text", "source", "chunk_index", "chunk_id", "content_hash")}
            item.update(model_revision=MODEL_REVISION if "vector" in channels[digest] else None,
                        channels=channels[digest], score=scores[digest], provenance_count=len(ids),
                        supporting_sources=[{"source": chunks[cid]["source"], "chunk_index": chunks[cid]["chunk_index"], "chunk_id": cid} for cid in ids[:8]],
                        provenance_truncated=len(ids) > 8)
            if _bytes(evidence + [item]) > LIMITS["output_bytes"] - 2048:
                output_limited = True
                break
            evidence.append(item)
            if len(evidence) >= limit:
                break
        return {"mission_id": mission_id, "query": query, "status": status, "reason": reason, "evidence": evidence,
                "coverage": {"indexed_chunks": len(vectors), "candidate_chunks": len(chunks), "scope_sources": source_count,
                             "output_limited": output_limited}}
