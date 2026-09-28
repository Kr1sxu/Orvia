"""异步 stdio 服务；stdout 专用于协议，禁止混入日志。"""

import asyncio
import json
from typing import BinaryIO

from .protocol import MAX_LINE_BYTES, error_response
from .application import Application


def read_frame(stream: BinaryIO) -> tuple[bytes, bool]:
    """按字节限制完整行（包含换行），超限后消费到下一行边界。"""
    line = stream.readline(MAX_LINE_BYTES + 1)
    oversized = len(line) > MAX_LINE_BYTES
    if oversized:
        # 分块丢弃剩余部分，既限制内存，又避免后半行被解释成新请求。
        while line and not line.endswith(b"\n"):
            line = stream.readline(MAX_LINE_BYTES + 1)
        return b"", True
    return line, False


async def serve(reader: BinaryIO, writer: BinaryIO) -> None:
    """普通请求保序串行；取消/健康检查旁路，最多积压 32 项，按 ID 对应响应。"""
    application = Application()
    ordinary = asyncio.Lock()
    pending = set()
    output_closed = False

    def emit(response):
        nonlocal output_closed
        if output_closed:
            return
        payload = json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n"
        try:
            writer.write(payload.encode("utf-8"))
            writer.flush()
        except OSError:
            # 管道断开只停止输出；不在文件操作中途取消事务或打印异常路径。
            output_closed = True

    async def handle_safely(line):
        try:
            return await application.handle(line)
        except Exception:
            # 这是进程协议边界的最终隔离，业务预期错误仍由 Application 精确映射。
            # 不记录原始异常，以免第三方库将路径、请求体或凭据写入 stderr。
            try:
                request = json.loads(line)
                rid = request.get("id") if isinstance(request, dict) else None
            except (ValueError, RecursionError):
                rid = None
            return error_response(rid if isinstance(rid, str) else None, "INTERNAL_ERROR", "后端处理失败，请检查当前状态后重试")

    async def dispatch(line):
        async with ordinary:
            emit(await handle_safely(line))

    try:
        while True:
            line, oversized = await asyncio.to_thread(read_frame, reader)
            if oversized:
                emit(error_response(None, "INVALID_REQUEST", "请求行超过 64 KiB"))
                continue
            if not line:
                # EOF 先收尾已经接收的请求，不把正在记账的操作强行取消。
                if pending:
                    await asyncio.gather(*pending)
                return
            try:
                request = json.loads(line)
            except (ValueError, RecursionError):
                request = {}
            control = isinstance(request, dict) and request.get("method") in {"health", "chat.cancel"}
            if control:
                # 旁路仍经过 Application 的完整协议及参数检查。
                emit(await handle_safely(line))
            elif len(pending) >= 32:
                rid = request.get("id") if isinstance(request, dict) else None
                emit(error_response(rid if isinstance(rid, str) else None, "SERVER_BUSY", "请求积压，请等待当前操作完成"))
            else:
                task = asyncio.create_task(dispatch(line))
                pending.add(task)
                task.add_done_callback(pending.discard)
    finally:
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        await application.close()
