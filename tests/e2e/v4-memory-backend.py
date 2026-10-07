"""V4-003真实stdio/SQLite，唯一模型网络替身只处理固定合成资料。"""
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m20_backend as base

original = base.content_for


def content(payload):
    system = payload["messages"][0]["content"]
    if "memories:[{kind,key,value,source_ids}]" in system:
        packet = json.loads(payload["messages"][1]["content"])
        sources = {item["source_id"]: item for item in packet["sources"]}
        claims = []
        for turn in packet["rounds"]:
            user = next(item for item in turn["messages"] if item["role"] == "user" and item["source_id"] in sources)
            claims.append({"text": sources[user["source_id"]]["quote"], "source_ids": [user["source_id"]]})
        return {"summary": claims, "memories": [{"kind": item["kind"], "key": item["key"], "value": item["value"],
                 "source_ids": [source["source_id"] for source in item["sources"]]} for item in packet["candidates"]]}
    return original(payload)


base.content_for = content
if __name__ == "__main__":
    asyncio.run(base.serve(sys.stdin.buffer, sys.stdout.buffer))
