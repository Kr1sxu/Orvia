"""任意输出的最终协议预算：不截断JSON、不把超大结果当执行失败重试。"""
import asyncio
import io
import json
from orvia_backend.protocol import MAX_LINE_BYTES
from orvia_backend.server import serve
import orvia_backend.server as server


def test_output_json_escape_budget_keeps_connection(monkeypatch):
    class SyntheticApplication:
        def __init__(self, event_sink=None):
            pass
        async def handle(self, line):
            q=json.loads(line)
            return {"v":1,"id":q["id"],"ok":True,"result":{"text":"\x00"*16384} if q["method"]=="synthetic-output" else {"status":"ok"}}
        async def close(self): pass
    monkeypatch.setattr(server,"Application",SyntheticApplication)
    frames=[{"v":1,"id":"one","method":"synthetic-output","params":{}},{"v":1,"id":"two","method":"health","params":{}}]
    reader=io.BytesIO(('\n'.join(json.dumps(q) for q in frames)+'\n').encode())
    writer=io.BytesIO()
    asyncio.run(serve(reader,writer))
    lines=writer.getvalue().splitlines(keepends=True)
    assert len(lines)==2 and all(len(line)<=MAX_LINE_BYTES for line in lines)
    responses={q["id"]:q for q in map(json.loads,lines)}
    assert responses["one"]["error"]["code"]=="OUTPUT_LIMIT" and responses["two"]["result"]["status"]=="ok"
