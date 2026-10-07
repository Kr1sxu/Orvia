"""业务有效关联转成精确来源范围；历史证据身份不能自行恢复附件关联。"""

from ..computer.paths import ToolError


class ScopedRetrieval:
    def __init__(self, chat, service):
        self.chat, self.service = chat, service

    async def sources(self, cid, selected=None):
        await self.chat.repository.get(cid)
        materials = [item for item in await self.chat.natural.materials(cid) if item["status"] == "ready"]
        if selected is not None:
            for item in selected:
                await (self.chat.documents if item["kind"] == "document" else self.chat.evidence).get(cid, item["evidence_id"])
            wanted = {(item["kind"], item["evidence_id"]) for item in selected}
            active = {(item["kind"], item["evidence_id"]) for item in materials}
            if not wanted <= active:
                raise ToolError("SOURCE_UNAVAILABLE", "资料已解除关联，不能用于本次检索")
            materials = [item for item in materials if (item["kind"], item["evidence_id"]) in wanted]
        sources = []
        for item in materials:
            kind, eid = item["kind"], item["evidence_id"]
            if kind == "browser":
                sources.append("browser:" + eid)
            else:
                evidence = await self.chat.documents.get(cid, eid)
                sources.extend(f"document:{eid}:{unit['number']}" for unit in evidence["units"] if unit["text"].strip())
        if len(materials) > 3 or len(sources) > 150:
            raise ToolError("RETRIEVAL_SCOPE_LIMIT", "有效资料超过3份或150个定位，请减少关联资料")
        return sorted(set(sources))

    async def search(self, cid, query, limit=5, selected=None):
        scope = await self.sources(cid, selected)
        result = await self.service.search(cid, query, limit, scope)
        if scope != await self.sources(cid, selected):
            raise ToolError("SOURCE_CHANGED", "检索期间资料关联发生变化，请重新检索")
        return result

    async def rebuild(self, cid):
        scope = await self.sources(cid)
        result = await self.service.rebuild(cid, scope)
        if scope != await self.sources(cid):
            # 保留已存事实片段，清除本次失效scope派生数据；不把过期批准当完成。
            await self.service.clear(cid, scope)
            raise ToolError("SOURCE_CHANGED", "建立索引期间资料关联变化，已清除本次向量")
        return result
