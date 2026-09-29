"""M16 本地成品生成；不调用模型或读取其他用户文件。"""

from .service import prepare_publication, render_publication

__all__ = ["prepare_publication", "render_publication"]
