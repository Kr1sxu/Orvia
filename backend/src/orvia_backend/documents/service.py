"""复用 M12 不可变证据和 M06 检索，导出只包含可回溯的本地提取原文。"""

import hashlib
import json
import re
from datetime import datetime, timezone

from ..browser.evidence import EvidenceStore
from ..computer.paths import ToolError
from ..context import ContextService


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class DocumentStore(EvidenceStore):
    def __init__(self, store):
        super().__init__(store, kind="document")

    async def save(self, cid, title, data, parsed):
        """源字节哈希与提取内容哈希分开，OCR 变化也产生新版本。"""
        item = {**parsed, "title": title[:200], "accessed_at": datetime.now(timezone.utc).isoformat(),
                "file_hash": hashlib.sha256(data).hexdigest(),
                "content_hash": digest(json.dumps(parsed, ensure_ascii=False, sort_keys=True))}
        identity = [cid, item["title"], item["file_hash"], item["content_hash"]]
        if len(json.dumps(item, ensure_ascii=False).encode("utf-8")) > 48 * 1024:
            raise ToolError("OUTPUT_LIMIT", "文档证据超过通信预算")
        saved = await self.save_version(cid, item, identity)
        context = ContextService(self.store)
        for unit in saved["units"]:
            if unit["text"].strip():
                await context.index_text(cid, f'document:{saved["evidence_id"]}:{unit["number"]}', unit["text"])
        return saved

    @staticmethod
    def summary(value):
        return {**value, "units": [{**unit, "text": unit["text"][:180]} for unit in value["units"][:1]],
                "preview_truncated": any(len(unit["text"]) > 180 for unit in value["units"]) or len(value["units"]) > 1}

    async def search(self, cid, query):
        found = await ContextService(self.store).search(cid, query, 20)
        items, seen = [], set()
        for hit in found["evidence"]:
            if not hit["source"].startswith("document:") or hit["source"] in seen:
                continue
            _, eid, number = hit["source"].split(":")
            value = await self.get(cid, eid)
            unit = next((unit for unit in value["units"] if unit["number"] == int(number)), None)
            if unit is None:
                continue
            items.append({**self.summary(value), "units": [{**unit, "text": hit["text"][:600]}], "preview_truncated": True})
            seen.add(hit["source"])
            if len(items) == 5:
                break
        return items

    async def preview(self, cid, eid, format):
        """预览绑定内容哈希；覆盖率表示非空提取单元都有引用，不代表事实正确。"""
        value = await self.get(cid, eid)
        units = [unit for unit in value["units"] if unit["text"].strip()]
        if not units:
            raise ToolError("EXPORT_EMPTY", "没有可导出的提取正文")
        coverage = {"cited": len(units), "total": len(units)}
        payload = {"schema": "orvia.document.export.v1", "notice": "不可信来源原文；未经模型总结或事实核验。引用覆盖仅针对已提取内容。",
                   "coverage": coverage, "source": value}
        if format == "json":
            content = json.dumps(payload, ensure_ascii=False, indent=2)
        else:
            # 全部外部正文使用动态长度代码围栏，防止导出后的 Markdown 执行 HTML/图片请求。
            def literal(text):
                fence = "`" * (max((len(match) for match in re.findall(r"`+", text)), default=0) + 4)
                return fence + "\n" + text + "\n" + fence
            lines = ["# Orvia 文档原文导出", payload["notice"],
                     f'引用覆盖：{len(units)}/{len(units)} 个已提取单元；原文截断：{value["truncated"]}；缺失单元：{value["missing_units"]}',
                     "来源名称：\n" + literal(value["title"]), f'证据 ID：{eid}',
                     f'原文件 SHA256：{value["file_hash"]}', f'内容 SHA256：{value["content_hash"]}',
                     f'提取时间：{value["accessed_at"]}']
            for unit in units:
                lines.extend([f'## 引用 {eid}:{unit["number"]}', literal(unit["locator"]),
                              f'提取方式：{unit["method"]}；OCR 置信度：{unit["confidence"]}', literal(unit["text"])])
            content = "\n\n".join(lines) + "\n"
        if len(json.dumps(content, ensure_ascii=False).encode("utf-8")) > 48 * 1024:
            raise ToolError("OUTPUT_LIMIT", "导出内容超过通信预算，请使用更短的附件")
        return {"evidence_id": eid, "format": format, "revision": digest(content),
                "filename": f"Orvia-{eid[:12]}.{format}", "content": content, "coverage": coverage,
                "truncated": value["truncated"], "missing_units": value["missing_units"]}
