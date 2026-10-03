"""M20 真实有界批次扫描、扩展名分类和完整已发现清单分页。"""

import asyncio
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import time
from uuid import uuid4

from ..computer.files import _entry
from ..computer.paths import ToolError, safe_stat, sensitive


EXTENSIONS = {
    "文档": {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".txt", ".md", ".rtf"},
    "表格与数据": {".xlsx", ".xls", ".csv", ".tsv", ".json", ".xml", ".sqlite"},
    "图片": {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".tif", ".tiff"},
    "音视频": {".mp3", ".wav", ".flac", ".mp4", ".mov", ".avi", ".mkv", ".m4a"},
    "代码": {".py", ".ts", ".tsx", ".js", ".jsx", ".html", ".css", ".c", ".cpp", ".java", ".rs", ".go"},
    "压缩包": {".zip", ".7z", ".rar", ".tar", ".gz"},
}
MAX_VISITED = 5000
MAX_WORK_SECONDS = 10
MAX_LEDGER_BYTES = 4 * 1024 * 1024


def category(entry):
    if entry["kind"] == "directory":
        return "文件夹"
    suffix = Path(entry["name"]).suffix.casefold()
    return next((name for name, values in EXTENSIONS.items() if suffix in values), "其他文件")


class ScanStore:
    def __init__(self, store, gateway):
        self.store, self.gateway = store, gateway

    async def open(self):
        async with self.store._lock:
            db = self.store._db()
            await db.execute("""CREATE TABLE IF NOT EXISTS m20_scans (
                id TEXT PRIMARY KEY,conversation_id TEXT NOT NULL,request_id TEXT NOT NULL,
                summary_json TEXT NOT NULL,state TEXT NOT NULL,operation TEXT NOT NULL DEFAULT 'list')""")
            await db.execute("""CREATE TABLE IF NOT EXISTS m20_scan_entries (
                scan_id TEXT NOT NULL,ordinal INTEGER NOT NULL,entry_json TEXT NOT NULL,
                PRIMARY KEY(scan_id,ordinal))""")
            async with db.execute("PRAGMA table_info(m20_scans)") as cursor:
                if "operation" not in {row[1] for row in await cursor.fetchall()}:
                    await db.execute("ALTER TABLE m20_scans ADD COLUMN operation TEXT NOT NULL DEFAULT 'list'")
            await db.execute("UPDATE m20_scans SET state='interrupted' WHERE state='running'")

    async def recover_history(self, cid, repository):
        """恢复已落库但未进入历史的扫描入口，不重扫/发布旧事件或恢复权限。

        批次事务与事件seq事务之间确有窗口。原请求已结束或重启标成interrupted之后，
        仅从SQLite重建已发现前缀；历史插入自身使用事务按scan_id去重，绝不称两次提交原子。
        """
        async with self.store._lock:
            async with self.store._db().execute("""SELECT s.id,s.request_id,s.state,s.operation
                FROM m20_scans s LEFT JOIN chat_requests r
                  ON r.conversation_id=s.conversation_id AND r.request_id=s.request_id
                WHERE s.conversation_id=? AND s.state!='running'
                  AND (r.status IS NULL OR r.status NOT IN ('pending','waiting_input','waiting_approval'))
                  AND NOT EXISTS(SELECT 1 FROM chat_messages m WHERE m.conversation_id=s.conversation_id
                    AND json_extract(m.message_json,'$.kind')='directory_result'
                    AND json_extract(m.message_json,'$.data.scan_id')=s.id)
                ORDER BY s.rowid""", (cid,)) as cursor:
                rows = await cursor.fetchall()
        for row in rows:
            page = await self.page(cid, row[0])
            summary = page["summary"]
            partial = row[2] != "completed" or not summary["complete"]
            if partial:
                summary.update(complete=False, truncated=True,
                               reason=summary.get("reason") or "扫描中断，保留已发现前缀；没有自动重扫")
            data = {"scan_id": row[0], "tool": {"list": "list_directory", "search": "search_files", "space": "analyze_directory_space"}.get(row[3], "list_directory"),
                    "summary": summary, "entries": page["entries"], "recovered": True, "partial": partial}
            message = repository._message("assistant", f"恢复上次扫描已保存的{page['total']}条发现记录，当前展示{len(page['entries'])}条。"
                "仅恢复历史事实与完整已发现清单入口，未继续原任务、重扫或恢复目录授权；分类依据扩展名，未读取正文。", "directory_result", data)
            async with self.store._lock:
                db = self.store._db()
                await db.execute("BEGIN IMMEDIATE")
                try:
                    await db.execute("""INSERT INTO chat_messages(conversation_id,message_json)
                        SELECT ?,? WHERE NOT EXISTS(SELECT 1 FROM chat_messages WHERE conversation_id=?
                        AND json_extract(message_json,'$.kind')='directory_result'
                        AND json_extract(message_json,'$.data.scan_id')=?)""",
                        (cid, json.dumps(message, ensure_ascii=False), cid, row[0]))
                    await db.commit()
                except BaseException:
                    await db.rollback()
                    raise

    async def _persist(self, scan_id, summary, entries, offset, state):
        async with self.store._lock:
            db = self.store._db()
            await db.execute("BEGIN IMMEDIATE")
            try:
                await db.executemany("INSERT INTO m20_scan_entries VALUES (?,?,?)",
                                     [(scan_id, offset + index, json.dumps(item, ensure_ascii=False)) for index, item in enumerate(entries)])
                await db.execute("UPDATE m20_scans SET summary_json=?,state=? WHERE id=? AND state='running'",
                                 (json.dumps(summary, ensure_ascii=False), state, scan_id))
                await db.commit()
            except BaseException:
                await db.rollback()
                raise

    async def page(self, cid, scan_id, offset=0):
        async with self.store._lock:
            db = self.store._db()
            async with db.execute("SELECT summary_json,state FROM m20_scans WHERE id=? AND conversation_id=?", (scan_id, cid)) as cursor:
                row = await cursor.fetchone()
            if row is None:
                raise ToolError("NOT_FOUND", "当前会话没有该扫描清单")
            async with db.execute("SELECT entry_json FROM m20_scan_entries WHERE scan_id=? AND ordinal>=? ORDER BY ordinal LIMIT 100", (scan_id, offset)) as cursor:
                entries = [json.loads(item[0]) for item in await cursor.fetchall()]
            async with db.execute("SELECT COUNT(*) FROM m20_scan_entries WHERE scan_id=?", (scan_id,)) as cursor:
                total = (await cursor.fetchone())[0]
        summary = json.loads(row[0])
        if row[1] == "interrupted":
            summary.update(complete=False, truncated=True, reason="扫描曾被中断；保留已发现清单，未自动重扫")
        result = {"scan_id": scan_id, "entries": entries, "offset": offset,
                  "next_offset": offset + len(entries) if offset + len(entries) < total else None,
                  "total": total, "summary": summary}
        # 极长合法路径也不能突破stdio帧；下一页从实际返回数接续，不遗漏已存条目。
        while len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > 48 * 1024 and entries:
            entries.pop()
            result["next_offset"] = offset + len(entries) if offset + len(entries) < total else None
        if offset == 0:
            summary["displayed"] = len(entries)
        return result

    async def run(self, cid, rid, *, path=".", depth=1, query="", operation="list", emit=None, cancelled=None):
        """只读访问在既有授权内；每批先落清单再发布，不预测文件名或百分比。"""
        if type(depth) is not int or not 1 <= depth <= 8 or operation not in {"list", "search", "space"}:
            raise ToolError("INVALID_PARAMS", "扫描范围无效")
        status = self.gateway.status(cid)
        policy = self.gateway.begin_scan("computer", cid, status["grant_id"])
        base = policy.resolve(path, "directory")
        scan_id = str(uuid4())
        visited = discovered = bytes_used = total_bytes = 0
        reasons, groups = Counter(), {}
        stopped = None
        started = time.monotonic()
        batch = []
        stack = [(base, 1)]
        summary = {}
        def summarize():
            return {"scope": path, "depth": depth, "recursive": depth > 1, "visited": visited,
                    "discovered": discovered, "displayed": min(discovered, 100),
                    "complete": stopped is None and not reasons, "truncated": stopped is not None,
                    "errors": [{"code": code, "count": count} for code, count in sorted(reasons.items())],
                    "categories": [{"name": name, "count": item[0], "bytes": item[1]} for name, item in sorted(groups.items())],
                    "total_bytes": total_bytes, "reason": stopped}
        async with self.store._lock:
            await self.store._db().execute("INSERT INTO m20_scans(id,conversation_id,request_id,summary_json,state,operation) VALUES (?,?,?,?,'running',?)", (scan_id, cid, rid, json.dumps(summarize(), ensure_ascii=False), operation))
        async def flush():
            nonlocal batch
            if not batch:
                return
            self.gateway.check_scan("computer", cid, status["grant_id"])
            await self._persist(scan_id, summarize(), batch, discovered - len(batch), "running")
            outgoing = batch
            batch = []
            if emit:
                await emit("scan_batch", {"scan_id": scan_id, "entries": outgoing, "discovered": discovered, "visited": visited})
            await asyncio.sleep(0)
        try:
            while stack and stopped is None:
                if time.monotonic() - started >= MAX_WORK_SECONDS:
                    stopped = "达到10秒扫描总耗时预算（含保存及流式等待）；尚有未扫描范围"
                    break
                directory, level = stack.pop()
                self.gateway.check_scan("computer", cid, status["grant_id"])
                try:
                    policy.resolve(directory.relative_to(policy.root).as_posix(), "directory")
                    with os.scandir(directory) as items:
                        while True:
                            if cancelled and cancelled():
                                stopped = "扫描已取消；已发现清单保留"
                                break
                            if visited >= MAX_VISITED or time.monotonic() - started >= MAX_WORK_SECONDS:
                                stopped = "达到5000条或10秒扫描总耗时预算（含保存及流式等待）；尚有未扫描范围"
                                break
                            # 批次输出后先核对墙钟预算，不能为了判定截断再访问下一个条目。
                            try:
                                item = next(items)
                            except StopIteration:
                                break
                            visited += 1
                            if sensitive(item.name):
                                reasons["sensitive_path"] += 1
                                continue
                            child = Path(item.path)
                            try:
                                relative = child.relative_to(policy.root).as_posix()
                                if len(relative) > 1000:
                                    raise ToolError("path_limit", "路径超过预算")
                                policy.resolve(relative)
                                info = safe_stat(child)
                            except ToolError as error:
                                reasons[error.code] += 1
                                continue
                            if not stat.S_ISREG(info.st_mode) and not stat.S_ISDIR(info.st_mode):
                                reasons["not_regular"] += 1
                                continue
                            if stat.S_ISDIR(info.st_mode) and level < depth:
                                stack.append((child, level + 1))
                            if operation == "search" and (not stat.S_ISREG(info.st_mode) or query.casefold() not in item.name.casefold()):
                                continue
                            entry = _entry(child, policy.root, info)
                            entry["category"] = category(entry)
                            amount = len(json.dumps(entry, ensure_ascii=False).encode("utf-8"))
                            if bytes_used + amount > MAX_LEDGER_BYTES:
                                stopped = "达到4MiB清单预算；尚有未扫描范围"
                                break
                            if batch and len(json.dumps({"scan_id": scan_id, "entries": [*batch, entry], "discovered": discovered + 1, "visited": visited}, ensure_ascii=False).encode("utf-8")) > 11 * 1024:
                                await flush()
                            batch.append(entry)
                            bytes_used += amount
                            discovered += 1
                            total_bytes += entry["size"]
                            group = groups.setdefault(entry["category"], [0, 0])
                            group[0] += 1
                            group[1] += entry["size"]
                            if len(batch) >= 40:
                                await flush()
                except ToolError as error:
                    if error.code.startswith("STREAM_"):
                        # 批次已提交而事件出口失败，必须结束整次扫描；不能当不可访问目录跳过。
                        raise
                    reasons[error.code] += 1
                except OSError:
                    reasons["path_unavailable"] += 1
            await flush()
        except ToolError as error:
            stopped = "流式结果输出中断；保留已发现前缀，没有自动重扫" if error.code.startswith("STREAM_") else "授权或目录身份已变化，扫描停止"
            reasons[error.code] += 1
            # 尚未发布的一批仍是已经发现的事实；落盘但不借失效权限继续扫描。
            if batch:
                await self._persist(scan_id, summarize(), batch, discovered - len(batch), "running")
                batch = []
        except asyncio.CancelledError:
            stopped = "扫描工作阶段超时或连接中断；保留已发现前缀，没有自动重扫"
            if batch:
                await self._persist(scan_id, summarize(), batch, discovered - len(batch), "running")
                batch = []
            raise
        finally:
            summary = summarize()
            await self._persist(scan_id, summary, [], discovered, "cancelled" if cancelled and cancelled() else "interrupted" if stopped and "中断" in stopped else "completed")
        return await self.page(cid, scan_id)
