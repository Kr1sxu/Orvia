"""JSON Lines 协议：输入只在内存校验，响应不回显请求内容。"""

import json
import platform
from typing import Any

MAX_LINE_BYTES = 64 * 1024
SERVICE = "orvia-backend"


def error_response(request_id: str | None, code: str, message: str) -> dict[str, Any]:
    """构造稳定的错误信封；解析失败时不猜测请求 ID。"""
    return {"v": 1, "id": request_id, "ok": False, "error": {"code": code, "message": message}}


class Session:
    """单个进程连接的握手状态；每次启动必须重新 hello。"""

    def __init__(self) -> None:
        self.ready = False

    def handle(self, line: bytes) -> dict[str, Any]:
        """处理一个有界 UTF-8 JSON 帧，成功 hello 后才允许 health。"""
        try:
            request = json.loads(line.decode("utf-8"))
        except (ValueError, RecursionError):
            # ValueError 同时覆盖非法 UTF-8、JSON 语法和超长整数字面量。
            return error_response(None, "INVALID_REQUEST", "请求必须是 UTF-8 JSON")

        if not isinstance(request, dict):
            return error_response(None, "INVALID_REQUEST", "请求必须是对象")
        request_id = request.get("id")
        if not isinstance(request_id, str) or not request_id.strip():
            return error_response(None, "INVALID_REQUEST", "请求 ID 必须是非空字符串")
        if type(request.get("v")) is not int or request["v"] != 1:
            return error_response(request_id, "UNSUPPORTED_VERSION", "仅支持协议版本 1")
        if not isinstance(request.get("method"), str) or request.get("params") != {}:
            return error_response(request_id, "INVALID_REQUEST", "方法必须是字符串且参数必须是空对象")

        method = request["method"]
        if method == "hello":
            # 握手可重复，避免客户端重试使连接进入不可恢复状态。
            self.ready = True
            result = {"protocol": 1, "service": SERVICE, "python": platform.python_version()}
        elif method == "health":
            if not self.ready:
                return error_response(request_id, "NOT_READY", "请先完成 hello 握手")
            result = {"status": "ok", "service": SERVICE}
        else:
            return error_response(request_id, "METHOD_NOT_FOUND", "不支持该方法")
        return {"v": 1, "id": request_id, "ok": True, "result": result}
