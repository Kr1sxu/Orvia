"""M16 冻结后端在隔离环境中实际生成三格式，不依赖开发 Python 或 Office。"""

import asyncio
import json
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

import pytest

from test_frozen import Frozen


pytestmark = pytest.mark.skipif(not os.environ.get("ORVIA_FROZEN_BACKEND"), reason="需显式指定 M16 冻结 EXE")


def test_frozen_publication_assets_and_renderers(tmp_path):
    async def scenario():
        client = await Frozen().start(tmp_path)
        try:
            cid = (await client.call("chat.create", {"client_request_id": str(uuid4()), "title": "M16 frozen synthetic"}))["id"]
        finally:
            await client.close()
        eid, mid = "a" * 64, str(uuid4())
        citation = f"document:{eid}:1:0"
        message = {"id": mid, "role": "assistant", "text": "synthetic", "kind": "synthesis", "created_at": "2026-09-29T00:00:00Z",
                   "data": {"answer": "合成资料简报摘要", "claims": [{"text": "需要保留来源", "kind": "fact", "citations": [citation]}],
                            "citations": [{"citation": citation, "kind": "document", "evidence_id": eid, "locator": "第1页", "chunk": 0}],
                            "coverage": [{"kind": "document", "evidence_id": eid, "title": "synthetic.pdf"}],
                            "revision": "b" * 64, "model": "deepseek-flash", "usage": {}}}
        with sqlite3.connect(tmp_path / "app.sqlite") as db:
            db.execute("INSERT INTO chat_messages(conversation_id,message_json) VALUES (?,?)", (cid, json.dumps(message, ensure_ascii=False)))
        client = await Frozen().start(tmp_path)
        try:
            for format in ("docx", "pptx", "pdf"):
                request = {"id": cid, "message_id": mid, "format": format, "title": "冻结合成简报",
                           "answer": "只发送本地合成内容", "claim_texts": ["保留引用"]}
                preview = await client.call("chat.publication.preview", request)
                destination = tmp_path / f"frozen-brief.{format}"
                result = await client.call("chat.publication.save", {**request, "revision": preview["revision"],
                                                                      "request_id": str(uuid4()), "path": str(destination)})
                assert result["messages"][-1]["kind"] == "publication"
                header = destination.read_bytes()[:4]
                assert header == (b"%PDF" if format == "pdf" else b"PK\x03\x04")
        finally:
            await client.close()
    asyncio.run(scenario())
