"""V4-001：可关闭的 Redis 辅助缓存和通知，SQLite 始终是唯一事实来源。"""

from .service import AuxiliaryConfig, AuxiliaryService

__all__ = ["AuxiliaryConfig", "AuxiliaryService"]
