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
    """将阻塞读取移到工作线程，主协程串行调度请求并保持响应顺序。"""
    application = Application()
    try:
        while True:
            line, oversized = await asyncio.to_thread(read_frame, reader)
            if oversized:
                response = error_response(None, "INVALID_REQUEST", "请求行超过 64 KiB")
            elif not line:
                return
            else:
                response = await application.handle(line)
            payload = json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n"
            writer.write(payload.encode("utf-8"))
            writer.flush()
    finally:
        await application.close()
