"""程序固定的安全分类；工具说明、模型输出与GET方法均不能授予重试资格。"""
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
import math
import sqlite3
import httpx

TOOLS = frozenset({"browser.static_read", "context.sqlite_read"})
BACKOFF = (0.2, 0.5)


class RetryError(ValueError):
    """稳定错误不含请求内容、地址、凭据或数据库异常正文。"""
    def __init__(self, code, message):
        self.code, self.message = code, message
        super().__init__(message)


class HTTPTransient(Exception):
    """仅由静态SafeHTTP适配器在收到准确临时状态响应后构造。"""
    def __init__(self, status, retry_after=None):
        self.status, self.retry_after = status, retry_after
        super().__init__("公开静态读取收到暂时性状态")


def retry_after(value, *, now=None):
    """只接受RFC秒数或HTTP日期；无效/无穷值拒绝，绝不忽略服务器等待要求。"""
    if value is None:
        return 0.0
    if not isinstance(value, str) or len(value) > 128:
        return None
    try:
        stripped = value.strip()
        if stripped.isascii() and stripped.isdecimal():
            result = float(stripped)
        else:
            date = parsedate_to_datetime(stripped)
            if date.tzinfo is None:
                return None
            result = max(0.0, (date - (now or datetime.now(UTC))).total_seconds())
        return result if math.isfinite(result) and result >= 0 else None
    except (ValueError, TypeError, OverflowError):
        return None


def classify(tool, error):
    """返回固定重试原因/安全错误码；发送后超时、读写错误和未知状态一律不重放。"""
    if tool == "browser.static_read":
        if isinstance(error, (httpx.ReadTimeout,httpx.WriteTimeout,httpx.ReadError,httpx.WriteError,httpx.RemoteProtocolError)):
            return "not_retryable", "NETWORK_UNKNOWN", None
        if isinstance(error, httpx.ConnectTimeout):
            return "connect_before_send", "CONNECT_TIMEOUT", 0.0
        if isinstance(error, httpx.ConnectError):
            return "connect_before_send", "CONNECT_ERROR", 0.0
        if isinstance(error, HTTPTransient) and error.status in {429, 503}:
            return f"http_{error.status}", f"HTTP_{error.status}", retry_after(error.retry_after)
    if tool == "context.sqlite_read" and isinstance(error, sqlite3.OperationalError):
        code = getattr(error, "sqlite_errorcode", None)
        if type(code) is int and (code & 255) in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
            locked = (code & 255) == sqlite3.SQLITE_LOCKED
            return "sqlite_locked" if locked else "sqlite_busy", "SQLITE_LOCKED" if locked else "SQLITE_BUSY", 0.0
    return "not_retryable", "NOT_RETRYABLE", None
