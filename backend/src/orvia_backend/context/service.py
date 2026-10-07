"""上下文索引服务：只索引调用方明确提交的文本，不扫描用户目录。"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from uuid import uuid4, UUID
from time import monotonic

import jieba

from ..storage import Store


class ContextError(ValueError):
    """上下文输入或 FTS 查询不符合任务范围时的稳定错误。"""

    def __init__(self, code: str, message: str):
        self.code, self.message = code, message
        super().__init__(message)


def chunk_text(text: str, max_chars: int = 600, overlap: int = 80) -> list[str]:
    """按字符上限切分文本，优先在换行或句末断开，并限制重叠避免无限循环。"""
    if not isinstance(text, str) or not text.strip():
        raise ContextError("EMPTY_TEXT", "文本不能为空")
    if not 100 <= max_chars <= 2000 or not 0 <= overlap < max_chars // 2:
        raise ContextError("INVALID_CHUNK_SIZE", "文本块参数超出范围")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + max_chars)
        if end < len(normalized):
            boundary = max(normalized.rfind("\n", start + max_chars // 2, end),
                           normalized.rfind("。", start + max_chars // 2, end),
                           normalized.rfind(".", start + max_chars // 2, end))
            if boundary > start:
                end = boundary + 1
        piece = normalized[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(normalized):
            break
        start = max(start + 1, end - overlap)
    return chunks


class ContextService:
    """提供索引、检索、偏好和滚动摘要；所有数据按 Mission 隔离。"""

    def __init__(self, store: Store):
        self.store = store

    @staticmethod
    def _mission(mission_id: str) -> str:
        if not isinstance(mission_id, str) or not mission_id.strip() or len(mission_id) > 128:
            raise ContextError("INVALID_MISSION", "Mission 标识无效")
        return mission_id

    @staticmethod
    def _source(source: str) -> str:
        if not isinstance(source, str) or not source.strip() or len(source) > 1000:
            raise ContextError("INVALID_SOURCE", "来源标识无效")
        if "\r" in source or "\n" in source:
            raise ContextError("INVALID_SOURCE", "来源不能包含换行")
        return source.strip()

    @staticmethod
    def _tokens(text: str) -> str:
        # FTS5 使用空格分隔中文词；查询词只保留字母、数字、下划线和中文，避免注入 MATCH 运算符。
        words = [word.strip() for word in jieba.lcut(text) if word.strip()]
        return " ".join(word for word in words if re.fullmatch(r"[\w\u3400-\u9fff-]+", word, re.UNICODE))

    async def index_text(self, mission_id: str, source: str, text: str) -> dict:
        mission_id, source = self._mission(mission_id), self._source(source)
        chunks = chunk_text(text)
        document_id = str(uuid4())
        indexed = [self._tokens(chunk) for chunk in chunks]
        now = datetime.now(timezone.utc).isoformat()
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        await self.store.replace_context_document(
            {"id": document_id, "mission_id": mission_id, "source": source,
             "content_hash": digest, "updated_at": now},
            [{"id": uuid4().int % (2**63 - 1), "chunk_index": index, "content": chunk}
             for index, chunk in enumerate(chunks)], indexed,
        )
        return {"document_id": document_id, "mission_id": mission_id, "source": source,
                "chunk_count": len(chunks), "content_hash": digest}

    async def search(self, mission_id: str, query: str, limit: int = 5) -> dict:
        mission_id = self._mission(mission_id)
        if (not isinstance(query, str) or not query.strip() or len(query) > 200
                or any(char in query for char in '*"():')):
            raise ContextError("INVALID_QUERY", "检索词无效")
        if not isinstance(limit, int) or not 1 <= limit <= 20:
            raise ContextError("INVALID_LIMIT", "检索数量必须为 1 到 20")
        tokens = self._tokens(query)
        if not tokens:
            return {"mission_id": mission_id, "query": query, "evidence": []}
        # 每个 token 加引号，查询只执行 AND 词匹配，不允许调用方注入 FTS5 控制语法。
        match_query = " AND ".join(f'"{token.replace(chr(34), "")}"' for token in tokens.split())
        # 仅纯FTS SELECT可重试；分词、索引写入、向量推理及失效清理不在适配器内。
        retry = getattr(self.store, 'retry', None)
        if retry is None:
            rows = await self.store.search_context(mission_id, match_query, limit)
        else:
            try:
                cid = mission_id if str(UUID(mission_id)) == mission_id else None
            except ValueError:
                cid = None
            try:
                rows = await retry.run('context.sqlite_read', {'mission_id':mission_id,'match':match_query,'limit':limit},
                                       lambda:self.store.search_context(mission_id,match_query,limit),
                                       deadline=monotonic()+3.0,cid=cid)
            except TimeoutError:
                raise ContextError('SEARCH_TIMEOUT', '本机只读检索3秒预算已耗尽；未返回迟到值或扩大检索范围') from None
        return {"mission_id": mission_id, "query": query,
                "evidence": [{"source": row["source"], "chunk_index": row["chunk_index"],
                              "text": row["content"], "score": row["score"]} for row in rows]}

    async def clear(self, mission_id: str, source: str | None = None) -> dict:
        mission_id = self._mission(mission_id)
        if source is not None:
            source = self._source(source)
        return {"mission_id": mission_id, "removed_documents": await self.store.clear_context(mission_id, source)}

    async def set_preference(self, mission_id: str, key: str, value: str) -> dict:
        mission_id = self._mission(mission_id)
        if not isinstance(key, str) or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_.-]{0,63}", key):
            raise ContextError("INVALID_PREFERENCE", "偏好键格式无效")
        if not isinstance(value, str) or len(value) > 1000 or "\x00" in value:
            raise ContextError("INVALID_PREFERENCE", "偏好值超出范围")
        await self.store.set_preference(mission_id, key, value.strip())
        return {"mission_id": mission_id, "key": key, "updated": True}

    async def preferences(self, mission_id: str) -> dict:
        mission_id = self._mission(mission_id)
        return {"mission_id": mission_id, "preferences": await self.store.get_preferences(mission_id)}

    async def update_summary(self, mission_id: str, summary: str, revision: int) -> dict:
        mission_id = self._mission(mission_id)
        if not isinstance(summary, str) or len(summary) > 4000:
            raise ContextError("INVALID_SUMMARY", "摘要超出 4000 字符上限")
        if type(revision) is not int or not 1 <= revision <= 1_000_000:
            raise ContextError("INVALID_SUMMARY", "摘要版本无效")
        await self.store.update_summary(mission_id, summary.strip(), revision)
        return {"mission_id": mission_id, "revision": revision, "updated": True}

    async def summary(self, mission_id: str) -> dict:
        mission_id = self._mission(mission_id)
        return {"mission_id": mission_id, "summary": await self.store.get_summary(mission_id)}
