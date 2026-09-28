"""M06 任务范围上下文、偏好与 SQLite FTS5 轻量检索。"""

from .service import ContextService, ContextError, chunk_text

__all__ = ["ContextService", "ContextError", "chunk_text"]
