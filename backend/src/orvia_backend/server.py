"""异步 stdio 服务；stdout 专用于协议，禁止混入日志。"""

import asyncio
from contextvars import ContextVar
import json
from typing import BinaryIO

from .protocol import MAX_LINE_BYTES, error_response
from .application import Application
from .computer.paths import ToolError

EVENT_BYTES = 12 * 1024
OUTPUT_QUEUE = 32
OUTPUT_TIMEOUT = 10
_transport_id = ContextVar("orvia_transport_id", default=None)


class BoundedOutput:
    """单写者、逐帧确认的私有输出队列；慢管道不能无限积累扫描或模型正文。

    原生write/flush放在工作线程，避免占住事件循环使取消和健康检查失效。
    发送方等待实际写入，业务先落盘的事实不会因背压而被伪造为成功输出。
    断管道只停止输出，不重放业务，也不中止正在记账的文件副作用。
    """

    def __init__(self, writer: BinaryIO):
        self.writer = writer
        self.queue = asyncio.Queue(maxsize=OUTPUT_QUEUE)
        self.failed = None
        self.task = asyncio.create_task(self._run())

    @staticmethod
    def encode(value: dict, event: bool) -> bytes:
        encoded = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        maximum = EVENT_BYTES if event else MAX_LINE_BYTES
        if len(encoded) > maximum:
            if event:
                raise ToolError("STREAM_OUTPUT_LIMIT", "流式事件超过帧预算，已停止并保留已落盘事实")
            value = error_response(value.get("id"), "OUTPUT_LIMIT", "结果超过协议预算，请核对实际状态，不会自动重试")
            encoded = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
            if len(encoded) > MAX_LINE_BYTES:
                encoded = (json.dumps(error_response(None, "OUTPUT_LIMIT", "响应身份超过预算")) + "\n").encode("utf-8")
        return encoded

    async def send(self, value: dict, *, event: bool = False) -> None:
        if self.failed:
            if event:
                raise self.failed
            return
        encoded = self.encode(value, event)
        done = asyncio.get_running_loop().create_future()
        try:
            # put与实际写入共用总期限，而非每层各增加一次等待预算。
            async with asyncio.timeout(OUTPUT_TIMEOUT):
                await self.queue.put((encoded, done))
                await done
        except TimeoutError:
            self._fail(ToolError("STREAM_BACKPRESSURE", "流式结果消费超时，已停止；请读取历史事实，不会自动重发"))
            if event:
                raise self.failed from None
        except ToolError:
            if event:
                raise

    def _write(self, payload: bytes) -> None:
        self.writer.write(payload)
        self.writer.flush()

    def _fail(self, error: ToolError) -> None:
        self.failed = self.failed or error
        while not self.queue.empty():
            item = self.queue.get_nowait()
            if item is not None:
                _, done = item
                if not done.done():
                    done.set_exception(self.failed)
            self.queue.task_done()

    async def _run(self) -> None:
        while True:
            item = await self.queue.get()
            try:
                if item is None:
                    return
                encoded, done = item
                if self.failed:
                    if not done.done():
                        done.set_exception(self.failed)
                    continue
                try:
                    await asyncio.to_thread(self._write, encoded)
                except OSError:
                    self._fail(ToolError("STREAM_DISCONNECTED", "私有输出管道已断开；未自动重放任务"))
                    if not done.done():
                        done.set_exception(self.failed)
                else:
                    if not done.done():
                        done.set_result(None)
            finally:
                self.queue.task_done()

    async def close(self) -> None:
        await self.queue.put(None)
        await self.task


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
    output = BoundedOutput(writer)

    async def event_sink(value):
        rid = _transport_id.get()
        if not isinstance(rid, str) or not rid:
            raise ToolError("STREAM_IDENTITY", "事件缺少当前私有请求身份，未输出")
        await output.send({**value, "id": rid}, event=True)

    application = Application(event_sink=event_sink)
    ordinary = asyncio.Lock()
    pending = set()

    async def handle_safely(line):
        token = None
        try:
            try:
                envelope = json.loads(line)
                rid = envelope.get("id") if isinstance(envelope, dict) else None
            except (ValueError, RecursionError):
                rid = None
            token = _transport_id.set(rid)
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
        finally:
            if token is not None:
                _transport_id.reset(token)

    async def dispatch(line):
        async with ordinary:
            await output.send(await handle_safely(line))

    try:
        while True:
            line, oversized = await asyncio.to_thread(read_frame, reader)
            if oversized:
                await output.send(error_response(None, "INVALID_REQUEST", "请求行超过 64 KiB"))
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
            control = isinstance(request, dict) and request.get("method") in {
                # 自有Shell长执行期间只读状态和取消必须旁路，否则真实Job无法及时被用户中止。
                "shell.cancel", "shell.status", "shell.history",
                # 普通用户进程等待不阻塞本会话事实查看，不旁路任何启动/关闭/终止动作。
                "process.status", "process.history", "process.list",
                "research.status", "research.history", "research.cancel",
                "health", "chat.cancel", "chat.get", "chat.list", "chat.scan.page",
                "chat.automation.cancel", "chat.automation.script.status",
                "chat.automation.browser.pending", "chat.automation.browser.request", "chat.automation.browser.close"}
            if control:
                # 旁路仍经过 Application 的完整协议及参数检查。
                # 控制和只读快照仍经完整验证，不等待长模型/扫描，但不放行写动作。
                await output.send(await handle_safely(line))
            elif len(pending) >= 32:
                rid = request.get("id") if isinstance(request, dict) else None
                await output.send(error_response(rid if isinstance(rid, str) else None, "SERVER_BUSY", "请求积压，请等待当前操作完成"))
            else:
                task = asyncio.create_task(dispatch(line))
                pending.add(task)
                task.add_done_callback(pending.discard)
    finally:
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        await application.close()
        await output.close()
