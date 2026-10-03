"""只读备份一份已核验的合成mock回答，用于M16真实离线开发/安装成品对照。"""

import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "artifacts/test-results/M20"
SEED_PROFILE = RESULTS / "dialog-hjQMb9/profile"


def backup(profile: Path, seed_profile: Path | None = None) -> dict:
    """只复制SQLite一致性备份；不复制Vault或原生授权，不改原证据/回答。"""
    seed_profile = (seed_profile or SEED_PROFILE).resolve(strict=True)
    assert seed_profile.is_relative_to(RESULTS.resolve(strict=True)) and seed_profile.name == "profile", "仅接受M20合成证据profile"
    source = (seed_profile / "app.sqlite").resolve(strict=True)
    assert source.parent == seed_profile, "不得通过链接读取其他数据库"
    profile = profile.resolve(strict=True)
    assert profile.is_relative_to(RESULTS.resolve(strict=True)) and profile.name == "profile"
    destination = profile / "app.sqlite"
    assert not destination.exists(), "只允许新测试profile"
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    sys.path.insert(0, str(ROOT / "backend/src"))
    from orvia_backend.chat.synthesis import Generated

    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as db:
        assert db.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert db.execute("SELECT COUNT(*) FROM chat_requests WHERE status != 'completed'").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM m20_workflows WHERE state != 'completed'").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM m18_operations").fetchone()[0] == 0
        answers = [(cid, json.loads(raw)) for cid, raw in db.execute("SELECT conversation_id,message_json FROM chat_messages")
                   if json.loads(raw)["kind"] == "synthesis"]
        assert len(answers) == 1
        cid, answer = answers[0]
        data = answer["data"]
        parsed = Generated.model_validate({"answer": data["answer"], "claims": data["claims"]})
        assert data["model"] == "deepseek-flash" and len(data["revision"]) == 64
        citations = data["citations"]
        assert citations and all(item["kind"] == "document" for item in citations)
        valid = {item["citation"] for item in citations}
        assert all(cite in valid for claim in parsed.claims for cite in claim.citations)
        for item in citations:
            row = db.execute("SELECT evidence_json FROM document_evidence WHERE id=? AND mission_id=?", (item["evidence_id"], cid)).fetchone()
            assert row
            evidence = json.loads(row[0])
            assert evidence["format"] == "docx" and evidence["title"] == "synthetic.docx" and not evidence["error"]
            unit = next(unit for unit in evidence["units"] if unit["number"] == item["unit"])
            assert unit["locator"] == item["locator"] and unit["method"] == "text"
            document_path = (source.parent.parent / "synthetic.docx").resolve(strict=True)
            assert document_path.parent == source.parent.parent, "不得通过合成文件链接读取其他资料"
            assert hashlib.sha256(document_path.read_bytes()).hexdigest() == evidence["file_hash"]
        title = db.execute("SELECT title FROM chat_conversations WHERE id=?", (cid,)).fetchone()[0]
        # SQLite backup包含已提交WAL内容；来源连接始终mode=ro，目标是独占新profile。
        with closing(sqlite3.connect(destination)) as target:
            db.backup(target)
            assert target.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        facts = {"conversation_id": cid, "message_id": answer["id"], "title": title,
                 "citations": sorted(valid), "answerRevision": data["revision"], "sourceModel": data["model"],
                 "sourceRevision": hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest(),
                 "seededAnswerOrigin": "verified mock synthetic answer", "actualLocalSource": "DOCX",
                 "sourceUnits": len(evidence["units"]), "sqliteReadOnlyBackup": True,
                 "copiedFiles": ["app.sqlite"], "copiedVault": False, "copiedNativeDirectoryAuthority": False}
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before, "不得改动原数据库"
    return facts


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--seed-profile", help="可选M20树内已核验合成mock回答profile；不接受用户数据库")
    arguments = parser.parse_args()
    print(json.dumps(backup(Path(arguments.profile), Path(arguments.seed_profile) if arguments.seed_profile else None), ensure_ascii=False))
