"""V4-005真实stdio/SQLite，仅固定合成关系输出使用HTTP网络替身。"""
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m20_backend as base

original = base.content_for


def content(payload):
    system = payload["messages"][0]["content"]
    if "from_key" in system and "relations" in system:
        packet = json.loads(payload["messages"][1]["content"])
        source = next(item for item in packet["sources"] if "合成人甲负责项目合成航线" in item["quote"])
        sid = source["source_id"]
        return {"entities": [
            {"key": "a", "kind": "person", "name": "合成人甲", "source_ids": [sid]},
            {"key": "b", "kind": "project", "name": "合成航线", "source_ids": [sid]},
            {"key": "c", "kind": "project", "name": "合成导航", "source_ids": [sid]},
            {"key": "d", "kind": "file", "name": "合成方案.md", "source_ids": [sid]},
        ], "relations": [
            {"from_key": "a", "to_key": "b", "kind": "responsible_for", "source_id": sid, "quote": "合成人甲负责项目合成航线"},
            {"from_key": "b", "to_key": "c", "kind": "depends_on", "source_id": sid, "quote": "项目合成航线依赖项目合成导航"},
            {"from_key": "d", "to_key": "b", "kind": "documents", "source_id": sid, "quote": "文件合成方案.md属于项目合成航线"},
        ]}
    return original(payload)


base.content_for = content
if __name__ == "__main__":
    asyncio.run(base.serve(sys.stdin.buffer, sys.stdout.buffer))
