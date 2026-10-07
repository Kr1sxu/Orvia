"""V4-005 本地有来源支持的实体关系图。"""

from ..computer.paths import ToolError as GraphError
from .service import GraphService

__all__ = ["GraphService", "GraphError"]
