"""M17 受限代码与原型服务：模型只提出内容，程序绑定授权根和逐文件差异。"""

from __future__ import annotations

import difflib
import hashlib
import html
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ..computer.paths import PathPolicy, ToolError, _reparse, sensitive


ALLOWED = {".ts", ".tsx", ".js", ".jsx", ".html", ".css", ".json", ".md"}
MAX_FILES = 12
MAX_TOTAL = 64 * 1024
MAX_CONTEXT = 3
MAX_CONTEXT_BYTES = 8 * 1024


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _relative(raw: str) -> Path:
    """相对路径先逐段检查；禁止模型输出绝对路径、隐藏目录、ADS 和重解析点。"""
    candidate = Path(raw)
    parts = candidate.parts
    if (not raw or len(raw) > 240 or candidate.is_absolute() or candidate.drive or candidate.anchor
            or candidate.is_reserved() or not parts or any(part in {".", ".."} or part.startswith(".")
            or ":" in part or sensitive(part) for part in parts)
            or candidate.suffix.lower() not in ALLOWED):
        raise ToolError("CODE_PATH_DENIED", "生成文件路径不在首批允许范围")
    return candidate


def _target(policy: PathPolicy, raw: str) -> Path:
    policy._check_root()
    relative = _relative(raw)
    current = policy.root
    for part in relative.parts:
        current = current / part
        if current.exists() or current.is_symlink():
            if _reparse(current):
                raise ToolError("CODE_PATH_DENIED", "生成路径不能经过链接或联接")
            if current != policy.root / relative and not current.is_dir():
                raise ToolError("CODE_PATH_DENIED", "生成文件的父路径不是目录")
    return current


def _read_baseline(policy: PathPolicy, raw: str) -> tuple[str | None, dict | None]:
    target = _target(policy, raw)
    if not target.exists():
        return None, None
    if not target.is_file():
        raise ToolError("CODE_PATH_DENIED", "目标不是普通文件")
    policy.resolve(raw, "file")
    with target.open("rb") as stream:
        before = policy.validate_open_file(stream.fileno(), target)
        if before.st_size > MAX_TOTAL:
            raise ToolError("CODE_LIMIT", "既有文件超过差异预算，不能修改")
        data = stream.read(MAX_TOTAL + 1)
        after = policy.validate_open_file(stream.fileno(), target)
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ToolError("CODE_CHANGED", "读取期间文件已变化")
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ToolError("CODE_FORMAT", "首批只支持 UTF-8 文本项目") from exc
    if "\x00" in content:
        raise ToolError("CODE_FORMAT", "不能修改二进制文件")
    identity = {"dev": before.st_dev, "ino": before.st_ino, "size": before.st_size,
                "mtime_ns": before.st_mtime_ns, "sha256": hashlib.sha256(data).hexdigest()}
    return content, identity


def context_preview(policy: PathPolicy, paths: list[str]) -> dict:
    """仅把用户显式列出的少量 UTF-8 文件作为待确认上云上下文。"""
    if len(paths) > MAX_CONTEXT or len({p.casefold() for p in paths}) != len(paths):
        raise ToolError("CODE_LIMIT", "最多选择三个不同的上下文文件")
    entries = []
    for raw in paths:
        target = policy.resolve(str(_relative(raw)), "file")
        with target.open("rb") as stream:
            before = policy.validate_open_file(stream.fileno(), target)
            if before.st_size > MAX_CONTEXT_BYTES:
                raise ToolError("CODE_LIMIT", "上下文文件超过 8 KiB")
            data = stream.read(MAX_CONTEXT_BYTES + 1)
            after = policy.validate_open_file(stream.fileno(), target)
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ToolError("CODE_CHANGED", "读取期间上下文文件已变化")
        try:
            content = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ToolError("CODE_FORMAT", "上下文必须为 UTF-8 文本") from exc
        if "\x00" in content:
            raise ToolError("CODE_FORMAT", "上下文不能包含二进制内容")
        entries.append({"path": raw, "content": content, "sha256": hashlib.sha256(data).hexdigest()})
    return {"files": entries, "revision": _digest(entries)}


def _prototype_files(spec: dict) -> list[dict]:
    """模型只填结构化文案；可交互代码由固定生成器构造，不在应用中运行。"""
    if (not isinstance(spec, dict) or set(spec) != {"title", "pages"} or not isinstance(spec["title"], str)
            or not 1 <= len(spec["title"]) <= 80):
        raise ToolError("INVALID_GENERATION", "原型结构无效")
    pages = spec["pages"]
    if not isinstance(pages, list) or not 1 <= len(pages) <= 4:
        raise ToolError("INVALID_GENERATION", "原型须有 1–4 个页面")
    ids = set()
    for page in pages:
        if not isinstance(page, dict) or set(page) != {"id", "title", "body", "buttons", "form"}:
            raise ToolError("INVALID_GENERATION", "原型页面结构无效")
        if not isinstance(page["id"], str) or not page["id"].isascii() or not page["id"].isalnum() or len(page["id"]) > 24 or page["id"] in ids:
            raise ToolError("INVALID_GENERATION", "原型页面 ID 无效")
        ids.add(page["id"])
        if any(not isinstance(page[key], str) or len(page[key]) > limit for key, limit in (("title", 80), ("body", 500))):
            raise ToolError("INVALID_GENERATION", "原型文案超过预算")
        if not isinstance(page["buttons"], list) or len(page["buttons"]) > 4:
            raise ToolError("INVALID_GENERATION", "原型导航超出预算")
        if page["form"] is not None and (not isinstance(page["form"], dict) or set(page["form"]) != {"label", "success"}
                                      or any(not isinstance(value, str) or len(value) > 100 for value in page["form"].values())):
            raise ToolError("INVALID_GENERATION", "原型表单结构无效")
    for page in pages:
        for button in page["buttons"]:
            if (not isinstance(button, dict) or set(button) != {"label", "target"} or not isinstance(button["label"], str)
                    or len(button["label"]) > 40 or button["target"] not in ids):
                raise ToolError("INVALID_GENERATION", "原型导航目标无效")
    title = html.escape(spec["title"])
    sections = []
    for index, page in enumerate(pages):
        buttons = "".join(f'<button type="button" data-target="{html.escape(b["target"])}">{html.escape(b["label"])}</button>' for b in page["buttons"])
        form = "" if page["form"] is None else (f'<form><label>{html.escape(page["form"]["label"])}<input required maxlength="100"></label>'
            f'<button type="submit">提交演示</button><p class="feedback" role="status" data-success="{html.escape(page["form"]["success"])}"></p></form>')
        sections.append(f'<section id="page-{page["id"]}" class="page" {"" if index == 0 else "hidden"}><h1>{html.escape(page["title"])}</h1>'
                        f'<p>{html.escape(page["body"])}</p><nav>{buttons}</nav>{form}</section>')
    markup = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' + f'<title>{title}</title><link rel="stylesheet" href="style.css"></head><body><header>{title}<small>演示数据 · 未连接真实业务</small></header><main>' + "".join(sections) + '</main><script src="app.js"></script></body></html>'
    css = 'body{margin:0;font:16px system-ui,sans-serif;background:#f6f8fb;color:#223}header{padding:18px 7%;background:white;border-bottom:1px solid #dde}header small{display:block;color:#667;font-size:12px}main{max-width:800px;margin:6vh auto;padding:0 20px}.page{background:white;border:1px solid #dde;border-radius:16px;padding:32px;box-shadow:0 12px 40px #2331}button,input{font:inherit;padding:10px;border:1px solid #ccd;border-radius:8px}button{margin:6px;cursor:pointer}form{margin-top:20px}label{display:grid;gap:8px}[hidden]{display:none!important}.feedback{color:#285f4c}'
    js = '"use strict";document.addEventListener("click",e=>{const b=e.target.closest("button[data-target]");if(!b)return;document.querySelectorAll(".page").forEach(p=>p.hidden=p.id!=="page-"+b.dataset.target)});document.addEventListener("submit",e=>{e.preventDefault();const f=e.target;if(!f.reportValidity())return;const out=f.querySelector(".feedback");out.textContent=out.dataset.success+"（演示反馈，未发送数据）"});'
    return [{"path": "index.html", "content": markup}, {"path": "style.css", "content": css}, {"path": "app.js", "content": js}]


class DevelopmentService:
    """草稿持久化与文件应用分离，历史草稿不能在重新授权前写入。"""

    def __init__(self, store, gateway):
        self.store, self.gateway = store, gateway

    async def open(self):
        async with self.store._lock:
            await self.store._db().execute("""CREATE TABLE IF NOT EXISTS m17_drafts (
                id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, root TEXT NOT NULL,
                root_dev TEXT NOT NULL, root_ino TEXT NOT NULL, kind TEXT NOT NULL,
                plan_json TEXT NOT NULL CHECK(json_valid(plan_json)), created_at TEXT NOT NULL)""")

    def policy(self, cid: str) -> PathPolicy:
        return PathPolicy(str(self.gateway.authorized_root(cid)))

    async def create(self, cid: str, kind: str, generated: dict, stack: str = "react-vite") -> dict:
        policy = self.policy(cid)
        if kind not in {"code", "prototype"} or stack not in {"react-vite", "web-native"} or kind == "prototype" and stack != "web-native":
            raise ToolError("INVALID_PARAMS", "首批只支持 React/Vite 或原生网页")
        if kind == "code" and (not isinstance(generated, dict) or set(generated) != {"files"}):
            raise ToolError("INVALID_GENERATION", "代码结果只能包含文件清单")
        files = _prototype_files(generated) if kind == "prototype" else generated.get("files") if isinstance(generated, dict) else None
        if not isinstance(files, list) or not 1 <= len(files) <= MAX_FILES:
            raise ToolError("INVALID_GENERATION", "生成结果须包含 1–12 个文件")
        entries, total, seen = [], 0, set()
        for value in files:
            if not isinstance(value, dict) or set(value) != {"path", "content"} or not isinstance(value["path"], str) or not isinstance(value["content"], str):
                raise ToolError("INVALID_GENERATION", "生成文件结构无效")
            raw = value["path"]
            _relative(raw)
            suffix = Path(raw).suffix.lower()
            allowed = {".ts", ".tsx", ".html", ".css", ".json", ".md"} if stack == "react-vite" else {".js", ".html", ".css", ".json", ".md"}
            if suffix not in allowed:
                raise ToolError("CODE_FORMAT", "文件类型不属于所选语言和框架")
            if raw.casefold() in seen:
                raise ToolError("INVALID_GENERATION", "生成路径重复")
            seen.add(raw.casefold())
            content = value["content"]
            data = content.encode("utf-8")
            total += len(data)
            if not data or "\x00" in content or len(data) > 24 * 1024 or total > MAX_TOTAL:
                raise ToolError("CODE_LIMIT", "生成文件超过 12 个/64 KiB 或单文件 24 KiB 预算")
            old, baseline = _read_baseline(policy, raw)
            diff = "".join(difflib.unified_diff((old or "").splitlines(keepends=True), content.splitlines(keepends=True),
                                                fromfile="a/" + raw if old is not None else "/dev/null", tofile="b/" + raw))
            if old == content:
                raise ToolError("CODE_UNCHANGED", "生成结果包含没有变化的文件")
            # 差异必须完整可审查；若超出 stdio 预算则拒绝草稿，绝不静默截断。
            entries.append({"path": raw, "content": content, "baseline": baseline, "diff": diff, "status": "pending"})
        info = policy.root.stat()
        plan = {"kind": kind, "stack": stack, "files": entries, "prototype": generated if kind == "prototype" else None}
        # stdio 响应每行仅 64 KiB；差异与完整源码同时预览时需提前拒绝过大草稿。
        preview_budget = {"files": [{"path": item["path"], "content": item["content"], "diff": item["diff"]} for item in entries],
                          "prototype": plan["prototype"]}
        if len(json.dumps(preview_budget, ensure_ascii=False).encode("utf-8")) > 52 * 1024:
            raise ToolError("CODE_LIMIT", "草稿差异与源码超出通信预览预算，请缩小任务")
        revision = _digest({"root": str(policy.root), "dev": info.st_dev, "ino": info.st_ino, "plan": plan})
        draft_id = str(uuid4())
        async with self.store._lock:
            await self.store._db().execute("INSERT INTO m17_drafts VALUES (?,?,?,?,?,?,?,?)", (draft_id, cid, str(policy.root),
                str(info.st_dev), str(info.st_ino), kind, json.dumps({**plan, "revision": revision}, ensure_ascii=False), _now()))
        return await self.get(cid, draft_id)

    async def _row(self, cid: str, draft_id: str):
        async with self.store._lock:
            async with self.store._db().execute("SELECT * FROM m17_drafts WHERE id=? AND conversation_id=?", (draft_id, cid)) as cursor:
                row = await cursor.fetchone()
        if row is None:
            raise ToolError("NOT_FOUND", "当前会话没有此生成草稿")
        return dict(row)

    async def get(self, cid: str, draft_id: str) -> dict:
        row = await self._row(cid, draft_id)
        plan = json.loads(row["plan_json"])
        return {"draft_id": draft_id, "kind": row["kind"], "stack": plan["stack"], "revision": plan["revision"],
                "files": [{"index": index, "path": item["path"], "content": item["content"],
                           "diff": item["diff"], "status": item["status"], "operation": "modify" if item["baseline"] else "create"}
                          for index, item in enumerate(plan["files"])], "prototype": plan["prototype"]}

    async def apply(self, cid: str, draft_id: str, revision: str, index: int) -> dict:
        """每次只应用一个经过原生确认的文件，版本或现场变化立即拒绝。"""
        row = await self._row(cid, draft_id)
        policy = self.policy(cid)
        info = policy.root.stat()
        if str(policy.root) != row["root"] or (str(info.st_dev), str(info.st_ino)) != (row["root_dev"], row["root_ino"]):
            raise ToolError("ROOT_CHANGED", "项目授权根已变化，请重新授权和生成")
        plan = json.loads(row["plan_json"])
        if plan["revision"] != revision or not 0 <= index < len(plan["files"]):
            raise ToolError("STALE_APPROVAL", "草稿版本或文件序号不匹配")
        entry = plan["files"][index]
        if entry["status"] != "pending":
            raise ToolError("CODE_ALREADY_APPLIED", "此文件已应用或状态不确定，不重复写入")
        old, baseline = _read_baseline(policy, entry["path"])
        if baseline != entry["baseline"]:
            raise ToolError("CODE_CHANGED", "文件在预览后变化，拒绝覆盖；请重新生成")
        target = _target(policy, entry["path"])
        created_dirs = []
        current = policy.root
        for part in _relative(entry["path"]).parts[:-1]:
            current = current / part
            if not current.exists():
                current.mkdir()
                created_dirs.append(current)
            if _reparse(current) or not current.is_dir():
                raise ToolError("CODE_PATH_DENIED", "生成目录身份已变化")
        data = entry["content"].encode("utf-8")
        # 先写同目录临时文件；既有文件只在再次核对后原子替换，避免截断旧内容。
        stage = target.parent / (".orvia-stage-" + str(uuid4()))
        try:
            with stage.open("x+b") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if _read_baseline(policy, entry["path"])[1] != entry["baseline"]:
                raise ToolError("CODE_CHANGED", "写入前既有文件发生变化")
            if entry["baseline"] is None:
                # hard link 的原生独占目标语义防止首次创建时的并发覆盖。
                os.link(stage, target)
                stage.unlink()
            else:
                os.replace(stage, target)
            with target.open("rb") as stream:
                actual = stream.read(len(data) + 1)
            if actual != data:
                raise ToolError("CODE_VERIFY_FAILED", "写入后字节核验失败，请人工检查文件")
            entry["status"] = "applied"
            async with self.store._lock:
                await self.store._db().execute("UPDATE m17_drafts SET plan_json=? WHERE id=? AND conversation_id=?",
                    (json.dumps(plan, ensure_ascii=False), draft_id, cid))
            return {"path": entry["path"], "bytes": len(data), "verified": True, "draft_id": draft_id,
                    "remaining": sum(item["status"] == "pending" for item in plan["files"])}
        finally:
            if stage.exists():
                stage.unlink()
            # 目录可能在失败后仍包含外部新文件；只移除本轮创建且保持空的目录。
            for folder in reversed(created_dirs):
                try:
                    folder.rmdir()
                except OSError:
                    break
