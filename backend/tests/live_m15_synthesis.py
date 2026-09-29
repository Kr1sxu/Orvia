"""显式 --run-live 才用本进程读取的开发 Key，发送短合成资料；绝不打印正文。"""
import argparse
import asyncio
import json
import re
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from uuid import uuid4

from orvia_backend.application import Application


async def call(app, method, params=None):
    return await app.handle(json.dumps({"v": 1, "id": str(uuid4()), "method": method, "params": params or {}}).encode())


def development_key():
    path = Path(__file__).resolve().parents[2] / ".env.local"
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip().startswith("DEEPSEEK_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"\'')
    return ""


async def run():
    key = development_key()
    if not key:
        print("M15 live: MISSING_CREDENTIAL")
        return 2
    results = Path(__file__).resolve().parents[2] / "artifacts/test-results/M15"
    results.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="live-", dir=results) as directory:
        app = Application()
        try:
            await call(app, "hello")
            started = await call(app, "initialize", {"data_directory": directory, "credentials": {"main": key}})
            if not started["ok"]:
                print("M15 live: INIT_FAILED")
                return 2
            cid = (await call(app, "chat.create", {"client_request_id": str(uuid4()), "title": "M15 synthetic live"}))["result"]["id"]
            parsed = {"format": "docx", "units": [{"number": 1, "locator": "段落 1", "text": "合成项目甲的交付日期是2031年4月8日，负责人代号为A。", "method": "text", "confidence": None, "error": None}],
                      "total_units": 1, "truncated": False, "missing_units": [], "error": None}
            document = await app.chat.documents.save(cid, "synthetic.docx", b"m15-synthetic-only", parsed)
            browser = await app.chat.evidence.save(cid, {"title": "合成网页", "source_url": "https://example.com/synthetic-m15", "mode": "http",
                "accessed_at": "2026-09-29", "content": "合成网页记录项目甲的交付日期为2031年4月8日。", "truncated": False, "error": None})
            request = {"id": cid, "mode": "answer", "question": "两个合成来源中的项目甲交付日期是什么？请给引用。", "sources": [
                {"kind": "document", "evidence_id": document["evidence_id"]}, {"kind": "browser", "evidence_id": browser["evidence_id"]}]}
            preview = (await call(app, "chat.synthesis.preview", request))["result"]
            generated = (await call(app, "chat.synthesis.generate", {**request, "revision": preview["revision"], "request_id": str(uuid4())}))["result"]
            last = generated["messages"][-1]
            if last["kind"] != "synthesis":
                print("M15 live: FAILED code=" + str(last.get("data", {}).get("code", "UNKNOWN")))
                return 1
            data = last["data"]
            combined = data["answer"] + " ".join(claim["text"] for claim in data["claims"])
            date_ok = bool(re.search(r"2031\s*(?:年|[-/.])\s*0?4\s*(?:月|[-/.])\s*0?8", combined))
            citation_ok = bool(data["claims"] and data["citations"])
            if not citation_ok or not date_ok:
                print(f"M15 live: CONTENT_CHECK_FAILED date_ok={date_ok} citations_ok={citation_ok} claims={len(data['claims'])}")
                return 1
            print(f"M15 live: PASS calls=1 model=deepseek-flash sources=2 claims={len(data['claims'])} citations={len(data['citations'])} total_tokens={data['usage'].get('total_tokens','unavailable')}")
            return 0
        finally:
            await app.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-live", action="store_true")
    if not parser.parse_args().run_live:
        print("M15 live: skipped (requires --run-live)")
        sys.exit(0)
    sys.exit(asyncio.run(run()))
