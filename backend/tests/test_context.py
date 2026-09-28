import asyncio
from pathlib import Path

import pytest

from orvia_backend.context import ContextError, ContextService, chunk_text
from orvia_backend.storage import Store


def test_chunking_and_mission_scoped_fts(tmp_path: Path):
    async def scenario():
        store = Store(tmp_path / "app.sqlite")
        await store.open()
        try:
            service = ContextService(store)
            assert len(chunk_text("第一段。\n第二段。", max_chars=120, overlap=40)) == 1
            await service.index_text("mission-a", "notes.md", "项目整理规则：保留源文件，移动前需要审批。\n只读扫描后再执行。")
            await service.index_text("mission-b", "notes.md", "项目整理规则：另一个任务的内容。")
            result = await service.search("mission-a", "审批")
            assert result["evidence"] and result["evidence"][0]["source"] == "notes.md"
            assert not (await service.search("mission-a", "另一个"))["evidence"]
            assert (await service.set_preference("mission-a", "file.naming", "保留扩展名"))["updated"]
            assert (await service.preferences("mission-a"))["preferences"]["file.naming"] == "保留扩展名"
            await service.update_summary("mission-a", "当前已完成扫描。", 1)
            assert (await service.summary("mission-a"))["summary"]["revision"] == 1
            assert (await service.clear("mission-a"))["removed_documents"] == 1
            assert not (await service.search("mission-a", "审批"))["evidence"]
        finally:
            await store.close()
    asyncio.run(scenario())


def test_context_rejects_unsafe_inputs(tmp_path: Path):
    async def scenario():
        store = Store(tmp_path / "app.sqlite")
        await store.open()
        try:
            service = ContextService(store)
            with pytest.raises(ContextError) as exc:
                await service.set_preference("m", "bad key", "x")
            assert exc.value.code == "INVALID_PREFERENCE"
            with pytest.raises(ContextError) as exc:
                await service.search("m", '" OR *')
            assert exc.value.code == "INVALID_QUERY"
        finally:
            await store.close()
    asyncio.run(scenario())
