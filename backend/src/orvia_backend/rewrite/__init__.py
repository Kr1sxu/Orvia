"""有界查询改写与当前会话资料检索；所有模型建议必须通过程序规则核验。"""
from .service import RewriteService, RewriteError
__all__ = ['RewriteService', 'RewriteError']
