"""内存字节流测试真实读取和调度逻辑，不模拟协议实现。"""

import asyncio
import io
import json

from orvia_backend.protocol import MAX_LINE_BYTES
from orvia_backend.server import read_frame, serve


def test_line_size_boundary() -> None:
    assert read_frame(io.BytesIO(b"x" * (MAX_LINE_BYTES - 1) + b"\n")) == (
        b"x" * (MAX_LINE_BYTES - 1) + b"\n", False
    )
    stream = io.BytesIO(b"x" * (MAX_LINE_BYTES * 3) + b"\nnext\n")
    assert read_frame(stream) == (b"", True)
    assert read_frame(stream) == (b"next\n", False)


def test_oversized_unterminated_frame_and_eof() -> None:
    stream = io.BytesIO(b"x" * (MAX_LINE_BYTES + 1))
    assert read_frame(stream) == (b"", True)
    assert read_frame(stream) == (b"", False)


def test_recovery_after_bad_frames_and_eof() -> None:
    hello = b'{"v":1,"id":"h","method":"hello","params":{}}\n'
    health = b'{"v":1,"id":"c","method":"health","params":{}}'
    reader = io.BytesIO(b"x" * (MAX_LINE_BYTES + 1) + b"\n{\n" + hello + health)
    writer = io.BytesIO()
    asyncio.run(serve(reader, writer))
    results = [json.loads(line) for line in writer.getvalue().splitlines()]
    assert len(results) == 4
    # health既有控制旁路允许先于ordinary hello响应；按运输ID核对，不能假设FIFO。
    invalid = [item for item in results if not item['ok']]
    assert len(invalid) == 2 and all(item['error']['code'] == 'INVALID_REQUEST' for item in invalid)
    valid = {item['id']: item for item in results if item['ok']}
    assert set(valid) == {'h', 'c'} and valid['h']['ok'] is True
    assert valid['c']['result']['status'] == 'ok'


def test_empty_input_exits_without_output() -> None:
    output = io.BytesIO()
    asyncio.run(serve(io.BytesIO(), output))
    assert output.getvalue() == b""
