"""真实临时 SQLite 测试，不使用数据库 mock 或真实模型。"""

import asyncio
import json
import sqlite3
from uuid import uuid4

import pytest
from pydantic import ValidationError

from orvia_backend.domain import MissionCreate
from orvia_backend.storage import Store


def test_persistence_idempotency_concurrency_and_conflict(tmp_path):
    async def scenario():
        path = tmp_path / "orvia.sqlite3"
        store = Store(path)
        await store.open()
        request = MissionCreate(client_request_id=uuid4(), title="合成草稿")
        try:
            missions = await asyncio.gather(*(store.create_mission(request) for _ in range(8)))
            assert len({mission.id for mission in missions}) == 1
            assert len(await store.list_missions()) == 1
            with pytest.raises(ValueError, match="^client_request_id already used with different content$"):
                await store.create_mission(MissionCreate(client_request_id=request.client_request_id, title="不同内容"))
            assert await store.get_mission(str(uuid4())) is None
        finally:
            await store.close()
        reopened = Store(path)
        await reopened.open()
        try:
            assert await reopened.get_mission(str(missions[0].id)) == missions[0]
            assert await reopened.create_mission(request) == missions[0]
        finally:
            await reopened.close()
        with sqlite3.connect(path) as db:
            assert db.execute("PRAGMA user_version").fetchone()[0] == 1
            assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    asyncio.run(scenario())


def test_newer_schema_refused_and_connection_released(tmp_path):
    path = tmp_path / "future.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA user_version = 2")
    async def scenario():
        store = Store(path)
        with pytest.raises(ValueError, match="newer than supported"):
            await store.open()
        await store.close()
    asyncio.run(scenario())
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2
        assert db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == []


def test_snapshot_sql_immutable_and_corruption_detected(tmp_path):
    path = tmp_path / "corruption.sqlite3"
    async def create():
        store = Store(path)
        await store.open()
        try:
            return await store.create_mission(MissionCreate(client_request_id=uuid4(), title="合成草稿"))
        finally:
            await store.close()
    mission = asyncio.run(create())
    with sqlite3.connect(path) as db:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("UPDATE missions SET models_json = '[]'")
        # 模拟离线破坏数据库；读取必须失败，不能回退为默认模型。
        db.execute("DROP TRIGGER mission_models_immutable")
        damaged = [profile.model_dump() for profile in mission.models]
        damaged[0]["model"] = "wrong-model"
        db.execute("UPDATE missions SET models_json = ?", (json.dumps(damaged),))
    async def read():
        store = Store(path)
        await store.open()
        try:
            with pytest.raises(ValidationError):
                await store.get_mission(str(mission.id))
            with pytest.raises(ValidationError):
                await store.list_missions()
        finally:
            await store.close()
    asyncio.run(read())


def test_migration_failure_rolls_back(tmp_path):
    path = tmp_path / "conflict.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE missions (existing TEXT)")
    async def scenario():
        store = Store(path)
        with pytest.raises(sqlite3.OperationalError):
            await store.open()
    asyncio.run(scenario())
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 0
        assert db.execute("PRAGMA table_info(missions)").fetchone()[1] == "existing"


def test_list_returns_latest_twenty(tmp_path):
    async def scenario():
        store = Store(tmp_path / "bounded.sqlite3")
        await store.open()
        try:
            created = [await store.create_mission(MissionCreate(client_request_id=uuid4(), title=f"草稿 {index}")) for index in range(22)]
            listed = await store.list_missions()
            assert len(listed) == 20
            assert listed == sorted(created, key=lambda mission: (mission.created_at, str(mission.id)), reverse=True)[:20]
            assert await store.get_mission(str(created[0].id)) == created[0]
        finally:
            await store.close()
    asyncio.run(scenario())
