"""V4-006真实产品stdio/SQLite/资料解析，仅合成固定Main回答使用HTTP替身。"""
import asyncio
import importlib.util
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
spec = importlib.util.spec_from_file_location("v4_memory_fixture", Path(__file__).with_name("v4-memory-backend.py"))
memory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(memory)
base = memory.base
original = base.content_for


def content(payload):
    system = payload["messages"][0]["content"]
    if "allowed_candidates" in system and "candidates:[{query,source_ids}]" in system:
        packet = json.loads(payload["messages"][1]["content"])
        # 故意仅回显程序批准范围内的合成候选；不伪造权限、SQLite记忆或执行成功。
        return {"candidates": packet["allowed_candidates"]}
    return original(payload)


base.content_for = content
if __name__ == "__main__":
    asyncio.run(base.serve(sys.stdin.buffer, sys.stdout.buffer))
