"""M15 E2E 仅替换模型回答；Electron、stdio、SQLite 与文档解析均为真实。"""
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend/src"))
from orvia_backend.configuration.client import Completion, ModelClient
from orvia_backend.server import serve


async def synthetic_complete(self, profile, messages, **kwargs):
    assert profile.role == "main" and profile.model == "deepseek-flash"
    packet = json.loads(messages[1]["content"].split("：", 1)[1])
    assert packet["fragments"] and len(packet["fragments"]) <= 9
    cite = packet["fragments"][0]["citation"]
    return Completion(json.dumps({"answer": "合成摘要：需要保留来源。", "claims": [
        {"text": "合成资料要求保留来源。", "kind": "fact", "citations": [cite]}]}, ensure_ascii=False), (), "stop", {"total_tokens": 28})


ModelClient.complete = synthetic_complete
asyncio.run(serve(sys.stdin.buffer, sys.stdout.buffer))
