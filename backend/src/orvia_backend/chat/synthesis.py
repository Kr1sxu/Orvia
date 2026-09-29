"""M15 有界证据包与生成结果校验；资料和模型文本都只作为数据。"""

import hashlib
import json

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..computer.paths import ToolError
from ..context import ContextError, ContextService, chunk_text


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    text: str = Field(min_length=1, max_length=600)
    kind: str = Field(pattern=r"^(fact|inference|conflict|unknown)$")
    citations: list[str] = Field(default_factory=list, max_length=3)


class Generated(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    answer: str = Field(min_length=1, max_length=2200)
    claims: list[Claim] = Field(min_length=1, max_length=8)


def _revision(packet: dict) -> str:
    return hashlib.sha256(json.dumps(packet, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


async def prepare(chat, cid: str, mode: str, question: str, sources: list[dict]) -> dict:
    """重新读当前会话不可变版本；预览就是将发送的全部证据正文。"""
    if mode == "answer":
        try:
            # M06 是检索辅助而非生成前置条件；长问句或其保留语法仍可走有界采样。
            hits = (await ContextService(chat.store).search(cid, question[:200], 20))["evidence"]
        except ContextError:
            hits = []
    else:
        hits = []
    fragments, coverage = [], []
    for source in sources:
        kind, eid = source["kind"], source["evidence_id"]
        value = await (chat.documents if kind == "document" else chat.evidence).get(cid, eid)
        if value.get("error"):
            raise ToolError("SOURCE_UNAVAILABLE", "所选证据有读取或提取错误，请改选可用版本")
        candidates = []
        if kind == "document":
            for unit in value["units"]:
                if not unit["text"].strip():
                    continue
                for index, piece in enumerate(chunk_text(unit["text"], 600, 0)):
                    candidates.append({"citation": f"document:{eid}:{unit['number']}:{index}",
                                       "kind": kind, "evidence_id": eid, "locator": unit["locator"],
                                       "unit": unit["number"], "chunk": index, "text": piece,
                                       "method": unit["method"], "confidence": unit["confidence"]})
        else:
            content = value.get("content", "")
            if content.strip():
                for index, piece in enumerate(chunk_text(content, 600, 0)):
                    candidates.append({"citation": f"browser:{eid}:{index}", "kind": kind,
                                       "evidence_id": eid, "locator": value.get("source_url") or "搜索摘要",
                                       "chunk": index, "text": piece})
        if not candidates:
            raise ToolError("SOURCE_UNAVAILABLE", "所选证据没有可发送正文")
        # 摘要采样前中后；问答优先 M06 命中，剩余位置补充开头，避免把片段当全文。
        preferred = []
        if mode == "answer":
            for hit in hits:
                key = (f"document:{eid}:" if kind == "document" else f"browser:{eid}")
                if hit["source"].startswith(key):
                    preferred.extend(candidate for candidate in candidates if hit["text"] in candidate["text"])
        indices = [0, len(candidates) // 2, len(candidates) - 1]
        chosen = []
        for candidate in [*preferred, *(candidates[index] for index in indices)]:
            if candidate["citation"] not in {item["citation"] for item in chosen}:
                chosen.append(candidate)
            if len(chosen) == 3:
                break
        fragments.extend(chosen)
        coverage.append({"kind": kind, "evidence_id": eid, "title": value.get("title", ""),
                         "accessed_at": value.get("accessed_at"), "selected_chunks": len(chosen),
                         "available_chunks": len(candidates), "source_truncated": bool(value.get("truncated")),
                         "missing_units": value.get("missing_units", []),
                         "ocr_available": kind == "document" and any(unit.get("method") == "ocr" for unit in value["units"]),
                         "ocr_selected": any(item.get("method") == "ocr" for item in chosen)})
    packet = {"mode": mode, "question": question, "supplier": "Main · deepseek-flash · https://api.deepseek.com",
              "fragments": fragments, "coverage": coverage}
    packet["revision"] = _revision(packet)
    return packet


def verify_generated(raw: str, packet: dict) -> dict:
    """只验证引用结构与本次发送片段身份；不声称程序已核实语义真伪。"""
    try:
        result = Generated.model_validate_json(raw)
    except ValidationError:
        raise ToolError("INVALID_GENERATION", "模型回答结构无效；未保存为带引用回答") from None
    allowed = {item["citation"]: item["evidence_id"] for item in packet["fragments"]}
    for claim in result.claims:
        if len(set(claim.citations)) != len(claim.citations) or any(cite not in allowed for cite in claim.citations):
            raise ToolError("INVALID_CITATION", "模型引用了本次未发送的证据片段")
        minimum = 2 if claim.kind == "conflict" else 0 if claim.kind == "unknown" else 1
        if len(claim.citations) < minimum or (claim.kind == "unknown" and claim.citations):
            raise ToolError("INVALID_CITATION", "模型结论的引用数量与类型不符")
        if claim.kind == "conflict" and len({allowed[cite] for cite in claim.citations}) < 2:
            raise ToolError("INVALID_CITATION", "来源冲突必须引用两个不同证据版本")
    return result.model_dump()
