"""V4-004 真实临时SQLite/FTS与合成嵌入契约，不下载或调用真实模型。"""

import asyncio
import hashlib
import math
import struct
from uuid import uuid4

import pytest

from orvia_backend.context import ContextService
from orvia_backend.retrieval import RetrievalError, RetrievalService
from orvia_backend.retrieval import service as retrieval_module
from orvia_backend.retrieval.service import DIMENSION, MODEL_REVISION, PREPROCESS, SIGNATURE, _decode, _vector
from orvia_backend.storage import Store


class SyntheticEmbedder:
    signature = SIGNATURE

    def __init__(self):
        self.calls = []
        self.ready = True
        self.reason = "MODEL_MISSING"
        self.hook = None

    def status(self):
        return {"ready": self.ready, "reason": None if self.ready else self.reason, "signature": self.signature}

    async def embed(self, texts, query=False):
        self.calls.append((list(texts), query))
        if self.hook:
            await self.hook()
        result = []
        for text in texts:
            vector = [0.0] * DIMENSION
            index = 0 if any(word in text.lower() for word in ("汽车", "交通", "car")) else 1 if "咖啡" in text else 2
            vector[index] = 2.0
            result.append(vector)
        return result


async def setup(tmp_path):
    store = Store(tmp_path / "facts.sqlite")
    await store.open()
    embedder = SyntheticEmbedder()
    service = RetrievalService(store, embedder)
    await service.open()
    return store, ContextService(store), embedder, service


async def raw_document(store, mission, source, texts, start=1):
    document = {"id": str(uuid4()), "mission_id": mission, "source": source,
                "content_hash": hashlib.sha256("\n".join(texts).encode()).hexdigest(), "updated_at": "synthetic"}
    await store.replace_context_document(document, [{"id": start + i, "chunk_index": i, "content": text} for i, text in enumerate(texts)], [ContextService._tokens(text) for text in texts])
    return document


async def count_vectors(store, mission=None):
    async with store._lock:
        async with store._db().execute("SELECT count(*) FROM retrieval_vectors" + (" WHERE mission_id=?" if mission else ""), [mission] if mission else []) as cursor:
            return (await cursor.fetchone())[0]


def test_real_sqlite_fts_hybrid_synonym_and_restart_consistency(tmp_path):
    async def run():
        store, context, embedder, service = await setup(tmp_path)
        try:
            await context.index_text("mission", "cars", "汽车使用电能，可以减少城市污染。")
            await context.index_text("mission", "coffee", "咖啡烘焙流程与饮料生产。")
            assert (await service.rebuild("mission"))["status"] == "completed"
            result = await service.search("mission", "交通工具")
            assert result["status"] == "hybrid" and result["evidence"][0]["source"] == "cars"
            assert result["evidence"][0]["channels"] == ["vector"]
            lexical = await service.search("mission", "汽车")
            assert set(lexical["evidence"][0]["channels"]) == {"keyword", "vector"}
            assert lexical["evidence"][0]["model_revision"] == MODEL_REVISION
            assert math.isfinite(lexical["evidence"][0]["score"])
            reopened = RetrievalService(store, embedder)
            await reopened.open()
            assert await reopened.search("mission", "汽车") == lexical
            assert (await reopened.status("mission"))["indexed_chunks"] == 2
        finally:
            await store.close()
    asyncio.run(run())


def test_missing_runtime_fallback_no_embedding_or_fake_completion(tmp_path):
    async def run():
        store, context, embedder, service = await setup(tmp_path)
        try:
            await context.index_text("mission", "source", "汽车的合成资料")
            embedder.ready = False
            result = await service.rebuild("mission")
            assert result["status"] == "keyword_only" and result["reason"] == "MODEL_MISSING"
            result = await service.search("mission", "汽车")
            assert result["status"] == "keyword_only" and result["reason"] == "MODEL_MISSING"
            assert result["evidence"][0]["channels"] == ["keyword"]
            assert result["evidence"][0]["model_revision"] is None
            assert embedder.calls == []
        finally:
            await store.close()
    asyncio.run(run())


def test_mission_source_isolation_and_dedup_keeps_provenance(tmp_path):
    async def run():
        store, context, embedder, service = await setup(tmp_path)
        try:
            await context.index_text("mission", "a", "汽车合成正文")
            await context.index_text("mission", "b", "汽车合成正文")
            await context.index_text("mission", "hidden", "汽车合成私有范围")
            await context.index_text("other", "foreign", "汽车其它任务正文")
            result = await service.rebuild("mission", ["a", "b"])
            assert result["indexed_chunks"] == 2 and result["unique_texts"] == 1
            assert len(embedder.calls) == 1 and len(embedder.calls[0][0]) == 1
            result = await service.search("mission", "汽车", sources=["a", "b"])
            assert len(result["evidence"]) == 1
            assert {row["source"] for row in result["evidence"][0]["supporting_sources"]} == {"a", "b"}
            result = await service.search("mission", "汽车", sources=["b"])
            assert all(item["source"] == "b" for item in result["evidence"])
            assert result["coverage"]["scope_sources"] == 1
        finally:
            await store.close()
    asyncio.run(run())


def test_source_deletion_cascades_and_clear_only_derived_data(tmp_path):
    async def run():
        store, context, embedder, service = await setup(tmp_path)
        try:
            await context.index_text("mission", "a", "汽车资料")
            await context.index_text("mission", "b", "咖啡资料")
            await service.rebuild("mission")
            assert await count_vectors(store) == 2
            await context.clear("mission", "a")
            assert await count_vectors(store) == 1
            result = await service.search("mission", "汽车", sources=["a"])
            assert result["evidence"] == []
            assert (await service.clear("mission", ["b"]))["removed_vectors"] == 1
            assert (await context.search("mission", "咖啡"))["evidence"]
            assert await count_vectors(store) == 0
        finally:
            await store.close()
    asyncio.run(run())


@pytest.mark.parametrize("change", ["replace", "delete", "add", "document_hash", "mission_delete"])
def test_rebuild_race_does_not_write_stale_or_resurrect_deleted_sources(tmp_path, change):
    async def run():
        store, context, embedder, service = await setup(tmp_path)
        try:
            if change == "mission_delete":
                await store._db().execute("CREATE TABLE chat_deletions(id TEXT PRIMARY KEY,state TEXT)")
                await service.open()
            await context.index_text("mission", "source", "汽车旧版合成正文")
            async def race():
                if change == "replace":
                    await context.index_text("mission", "source", "汽车新版合成正文")
                elif change == "delete":
                    await context.clear("mission")
                elif change == "add":
                    await context.index_text("mission", "new", "咖啡新增范围")
                elif change == "document_hash":
                    await store._db().execute("UPDATE context_documents SET content_hash='changed' WHERE mission_id='mission'")
                else:
                    await store._db().execute("INSERT INTO chat_deletions VALUES('mission','pending')")
            embedder.hook = race
            result = await service.rebuild("mission")
            assert result["status"] == "failed"
            assert result["reason"] in ("RETRIEVAL_CHANGED", "RETRIEVAL_DELETED")
            assert await count_vectors(store) == 0
        finally:
            await store.close()
    asyncio.run(run())


@pytest.mark.parametrize("bad", [[1.0] * 2, [0.0] * DIMENSION, [float("nan")] + [0.0] * (DIMENSION - 1), [float("inf")] + [0.0] * (DIMENSION - 1), [True] + [0.0] * (DIMENSION - 1), ["x"] + [0.0] * (DIMENSION - 1)])
def test_vector_contract_rejects_bad_embedding(tmp_path, bad):
    async def run():
        store, context, embedder, service = await setup(tmp_path)
        try:
            await context.index_text("mission", "source", "汽车资料")
            async def invalid(texts, query=False):
                return [bad for _ in texts]
            embedder.embed = invalid
            result = await service.rebuild("mission")
            assert result["status"] == "failed" and result["reason"] == "RETRIEVAL_VECTOR"
            assert await count_vectors(store) == 0
            result = await service.search("mission", "汽车")
            assert result["status"] == "keyword_only" and result["evidence"]
        finally:
            await store.close()
    asyncio.run(run())


@pytest.mark.parametrize("column,value,reason", [
    ("signature", "old", "INDEX_VERSION_MISMATCH"),
    ("model_revision", "other-revision", "INDEX_VERSION_MISMATCH"),
    ("preprocess", "other-pooling", "INDEX_VERSION_MISMATCH"),
    ("content_hash", "wrong", "INDEX_SOURCE_CHANGED"),
    ("document_hash", "wrong", "INDEX_SOURCE_CHANGED"),
    ("document_id", "wrong", "INDEX_SOURCE_CHANGED"),
    ("vector", struct.pack("<" + "f" * DIMENSION, *([0.0] * DIMENSION)), "INDEX_VECTOR_INVALID"),
    ("vector", struct.pack("<" + "f" * DIMENSION, *([float("nan")] + [0.0] * (DIMENSION - 1))), "INDEX_VECTOR_INVALID"),
])
def test_persistent_vector_version_corruption_cannot_be_used(tmp_path, column, value, reason):
    async def run():
        store, context, embedder, service = await setup(tmp_path)
        try:
            await context.index_text("mission", "source", "汽车资料")
            await service.rebuild("mission")
            assert column in {"signature", "model_revision", "preprocess", "content_hash", "document_hash", "document_id", "vector"}
            await store._db().execute("UPDATE retrieval_vectors SET " + column + "=?", [value])
            result = await service.search("mission", "汽车")
            assert result["status"] == "keyword_only" and result["reason"] == reason
            assert all(item["channels"] == ["keyword"] for item in result["evidence"])
        finally:
            await store.close()
    asyncio.run(run())


def test_normalization_float32_and_blob_length_check(tmp_path):
    assert len(_vector([2.0] * DIMENSION)) == 4096
    vector = _decode(_vector([2.0] * DIMENSION))
    assert abs(math.hypot(*vector) - 1.0) < 1e-4
    with pytest.raises(RetrievalError, match="长度"):
        _decode(b"invalid")


def test_batch_scope_and_per_mission_limits(tmp_path):
    async def run():
        store, context, embedder, service = await setup(tmp_path)
        try:
            await raw_document(store, "mission", "source", ["汽车资料" + str(i) for i in range(19)])
            assert (await service.rebuild("mission"))["status"] == "completed"
            assert [len(call[0]) for call in embedder.calls] == [8, 8, 3]
            await raw_document(store, "big", "source", ["汽车" + str(i) for i in range(513)], start=1000)
            result = await service.rebuild("big")
            assert result["status"] == "keyword_only" and result["reason"] == "INDEX_MISSION_LIMIT"
            await raw_document(store, "long", "source", ["车" * 601], start=2000)
            assert (await service.rebuild("long"))["reason"] == "INDEX_TEXT_LIMIT"
            for sources in (["a"] * 2, ["x" + str(i) for i in range(151)]):
                with pytest.raises(RetrievalError):
                    await service.search("mission", "汽车", sources=sources)
            for i in range(151):
                await context.index_text("manysources", str(i), "汽车资料")
            with pytest.raises(RetrievalError, match="150"):
                await service.search("manysources", "汽车")
            assert (await service.search("manysources", "汽车", sources=["1"]))["coverage"]["scope_sources"] == 1
        finally:
            await store.close()
    asyncio.run(run())


def test_runtime_signature_change_and_fault_fallback(tmp_path):
    async def run():
        store, context, embedder, service = await setup(tmp_path)
        try:
            await context.index_text("mission", "source", "汽车资料")
            embedder.signature = "wrong"
            assert (await service.status())["reason"] == "MODEL_SIGNATURE_MISMATCH"
            assert (await service.rebuild("mission"))["status"] == "keyword_only"
            assert embedder.calls == []
            embedder.signature = SIGNATURE
            await service.rebuild("mission")
            async def failure(texts, query=False):
                raise RuntimeError("合成worker故障，不应出现在结果")
            embedder.embed = failure
            result = await service.search("mission", "汽车")
            assert result["reason"] == "EMBEDDING_FAILED" and result["evidence"]
        finally:
            await store.close()
    asyncio.run(run())


def test_deadline_and_cancellation_leave_no_partial_index(tmp_path, monkeypatch):
    async def run():
        store, context, embedder, service = await setup(tmp_path)
        try:
            await context.index_text("mission", "source", "汽车资料")
            clock = [0.0]
            monkeypatch.setattr(retrieval_module, "monotonic", lambda: clock[0])
            async def elapsed():
                clock[0] = 121.0
            embedder.hook = elapsed
            result = await service.rebuild("mission")
            assert result["reason"] == "EMBEDDING_TIMEOUT" and await count_vectors(store) == 0
            clock[0] = 0.0
            entered = asyncio.Event()
            async def block():
                entered.set()
                await asyncio.Event().wait()
            embedder.hook = block
            task = asyncio.create_task(service.rebuild("mission"))
            await entered.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert await count_vectors(store) == 0
        finally:
            await store.close()
    asyncio.run(run())


def test_global_budget_and_atomic_limit_failure(tmp_path):
    async def run():
        store, context, embedder, service = await setup(tmp_path)
        try:
            vector = _vector([1.0] + [0.0] * (DIMENSION - 1))
            for i in range(8):
                mission = "filled" + str(i)
                document = await raw_document(store, mission, "source", ["汽车" + str(j) for j in range(512)], start=1 + i * 512)
                rows = [(1 + i * 512 + j, mission, document["id"], document["content_hash"], hashlib.sha256(("汽车" + str(j)).encode()).hexdigest(), SIGNATURE, MODEL_REVISION, DIMENSION, PREPROCESS, vector) for j in range(512)]
                await store._db().executemany("INSERT INTO retrieval_vectors VALUES(?,?,?,?,?,?,?,?,?,?)", rows)
            await raw_document(store, "overflow", "source", ["汽车新资料"], start=5000)
            result = await service.rebuild("overflow")
            assert result["status"] == "failed" and result["reason"] == "RETRIEVAL_GLOBAL_LIMIT"
            assert await count_vectors(store) == 4096
            assert await count_vectors(store, "overflow") == 0
        finally:
            await store.close()
    asyncio.run(run())


def test_candidate_limit_and_provenance_output_budget(tmp_path):
    async def run():
        store, context, embedder, service = await setup(tmp_path)
        try:
            await raw_document(store, "mission", "source", ["汽车同一内容"] * 512)
            await service.rebuild("mission")
            result = await service.search("mission", "汽车")
            assert result["coverage"]["candidate_chunks"] <= 512
            assert len(result["evidence"]) == 1
            assert result["evidence"][0]["provenance_count"] == 512
            assert result["evidence"][0]["provenance_truncated"]
            assert len(result["evidence"][0]["supporting_sources"]) == 8
            assert len(str(result)) < 32 * 1024
        finally:
            await store.close()
    asyncio.run(run())


def test_signature_change_during_query_or_index_and_huge_integer_rejected(tmp_path):
    async def run():
        store, context, embedder, service = await setup(tmp_path)
        try:
            await context.index_text("mission", "source", "汽车资料")
            await service.rebuild("mission")
            async def change():
                embedder.signature = "unexpected-switch"
            embedder.hook = change
            result = await service.search("mission", "汽车")
            assert result["status"] == "keyword_only" and result["reason"] == "MODEL_SIGNATURE_MISMATCH"
            embedder.signature = SIGNATURE
            result = await service.rebuild("mission")
            assert result["status"] == "failed" and result["reason"] == "MODEL_SIGNATURE_MISMATCH"
            assert await count_vectors(store) == 1
            with pytest.raises(RetrievalError, match="浮点范围"):
                _vector([10**1000] + [0.0] * (DIMENSION - 1))
        finally:
            await store.close()
    asyncio.run(run())


def test_keyword_does_not_return_out_of_budget_original_chunk(tmp_path):
    async def run():
        store, context, embedder, service = await setup(tmp_path)
        try:
            await raw_document(store, "mission", "source", ["汽车" * 301])
            embedder.ready = False
            result = await service.search("mission", "汽车")
            assert result["evidence"] == []
            assert all(len(item["text"]) <= 600 for item in result["evidence"])
        finally:
            await store.close()
    asyncio.run(run())


def test_empty_scope_never_reads_retained_history_or_embeds(tmp_path):
    async def run():
        store, context, embedder, service = await setup(tmp_path)
        try:
            await context.index_text("mission", "removed-source", "汽车保留的历史正文")
            assert (await service.search("mission", "汽车", sources=[]))["evidence"] == []
            assert (await service.rebuild("mission", []))["reason"] == "SCOPE_EMPTY"
            assert (await service.clear("mission", []))["removed_vectors"] == 0
            assert embedder.calls == []
        finally:
            await store.close()
    asyncio.run(run())


def test_astral_unicode_original_and_framed_output_budget(tmp_path):
    async def run():
        store, context, embedder, service = await setup(tmp_path)
        try:
            text = "😀" * 600
            await raw_document(store, "mission", "emoji", [text])
            assert (await service.rebuild("mission"))["status"] == "completed"
            result = await service.search("mission", "合成查询")
            assert result["evidence"][0]["text"] == text
            assert len(result["evidence"][0]["text"]) == 600
            assert retrieval_module._bytes(result) < 32 * 1024
        finally:
            await store.close()
    asyncio.run(run())


def test_clear_epoch_blocks_late_rebuild_without_deleting_original(tmp_path):
    async def run():
        store, context, embedder, service = await setup(tmp_path)
        try:
            await context.index_text("mission", "source", "汽车原文")
            await service.rebuild("mission")
            async def clear_during_embed():
                assert (await service.clear("mission"))["removed_vectors"] == 1
            embedder.hook = clear_during_embed
            result = await service.rebuild("mission")
            assert result["status"] == "failed" and result["reason"] == "RETRIEVAL_CHANGED"
            assert await count_vectors(store) == 0
            assert (await context.search("mission", "汽车"))["evidence"]
        finally:
            await store.close()
    asyncio.run(run())


def test_three_documents_fifty_unit_sources_each_remain_supported(tmp_path):
    async def run():
        store, context, embedder, service = await setup(tmp_path)
        try:
            sources = []
            for doc in range(3):
                for unit in range(50):
                    source = "document:" + str(doc) + ":" + str(unit)
                    sources.append(source)
                    await context.index_text("mission", source, "汽车合成正文" + str(doc) + "段" + str(unit))
            result = await service.rebuild("mission", sources)
            assert result["status"] == "completed" and result["indexed_chunks"] == 150
            result = await service.search("mission", "汽车", sources=sources)
            assert result["status"] == "hybrid" and result["coverage"]["scope_sources"] == 150
            assert retrieval_module._bytes(result) < 32 * 1024
        finally:
            await store.close()
    asyncio.run(run())


def test_missing_or_invalid_index_skips_query_embedding_and_query_clear_is_fenced(tmp_path):
    async def run():
        store, context, embedder, service = await setup(tmp_path)
        try:
            await context.index_text("mission", "source", "汽车正文")
            result = await service.search("mission", "汽车")
            assert result["reason"] == "INDEX_MISSING" and embedder.calls == []
            await service.rebuild("mission")
            embedder.calls.clear()
            await store._db().execute("UPDATE retrieval_vectors SET signature='wrong'")
            result = await service.search("mission", "汽车")
            assert result["reason"] == "INDEX_VERSION_MISMATCH" and embedder.calls == []
            await service.rebuild("mission")
            async def clear():
                await service.clear("mission")
            embedder.hook = clear
            result = await service.search("mission", "汽车")
            assert result["reason"] == "INDEX_CHANGED" and result["status"] == "keyword_only"
            assert result["evidence"][0]["channels"] == ["keyword"]
            assert result["coverage"]["indexed_chunks"] == 0
        finally:
            await store.close()
    asyncio.run(run())
