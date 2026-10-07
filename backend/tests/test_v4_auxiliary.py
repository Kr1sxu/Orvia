"""V4-001 使用真实临时 SQLite 验证事实边界；Redis 失败/污染由有界 fake 注入。"""

import asyncio
import json
from uuid import UUID

import pytest
from aiosqlite import OperationalError
from redis.exceptions import AuthenticationError, ConnectionError

from orvia_backend.auxiliary import AuxiliaryConfig, AuxiliaryService
from orvia_backend.auxiliary.service import validate_config
from orvia_backend.chat.repository import ChatRepository
from orvia_backend.storage import Store


async def setup(tmp_path):
    store = Store(tmp_path / "facts.sqlite")
    await store.open()
    await ChatRepository(store).open()
    service = AuxiliaryService(store)
    await service.open()
    return store, service


class FakePipeline:
    def __init__(self, client):
        self.client, self.calls = client, []

    def __getattr__(self, name):
        def append(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return self
        return append

    async def execute(self):
        result = []
        for name, args, kwargs in self.calls:
            result.append(await getattr(self.client, name)(*args, **kwargs))
        return result


class FakeRedis:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.values, self.queues, self.ttls = {}, {}, {}
        self.error, self.closed, self.pings = None, False, 0

    async def ping(self):
        self.pings += 1
        if self.error:
            raise self.error
        return True

    async def aclose(self):
        self.closed = True

    def pipeline(self, transaction=True):
        return FakePipeline(self)

    async def set(self, key, value, ex):
        if self.error:
            raise self.error
        self.values[key], self.ttls[key] = value, ex

    async def rpush(self, key, value):
        self.queues.setdefault(key, []).append(value)

    async def ltrim(self, key, start, stop):
        self.queues[key] = self.queues.get(key, [])[start:]

    async def expire(self, key, ttl):
        self.ttls[key] = ttl

    async def eval(self, script, number, key):
        if self.error:
            raise self.error
        if "LPOP" in script:
            values = self.queues.get(key, [])
            raw, self.queues[key] = values[:100], values[100:]
            return [item if len(item) <= 128 else "" for item in raw]
        value = self.values.get(key)
        return value if value and len(value) <= 256 else None


def test_strict_local_config():
    for config in ({"enabled": True, "host": "localhost", "port": 6379, "db": 0},
                   {"enabled": True, "host": "127.0.0.1", "port": True, "db": 0},
                   {"enabled": 1, "host": "127.0.0.1", "port": 6379, "db": 0},
                   {"enabled": True, "host": "127.0.0.1", "port": 6379, "db": 16},
                   {"enabled": True, "host": "::1", "port": 6379, "db": 0, "url": "redis://other"}):
        with pytest.raises(ValueError):
            validate_config(config)
    assert AuxiliaryConfig(host="::1").model_dump()["host"] == "::1"


def test_disabled_facts_trigger_revision_and_deletion(tmp_path, monkeypatch):
    async def scenario():
        store, service = await setup(tmp_path)
        try:
            def forbidden(**kwargs):
                raise AssertionError("关闭状态不应建立 Redis 连接")
            monkeypatch.setattr("orvia_backend.auxiliary.service.Redis", forbidden)
            assert (await service.status())["state"] == "disabled"
            await store._db().execute("INSERT INTO chat_requests VALUES ('synthetic-cid','request','private body','pending')")
            row = await (await store._db().execute("SELECT * FROM auxiliary_tasks")).fetchone()
            assert UUID(row["task_id"]).version == 4
            assert row["revision"] == 1
            await store._db().execute("UPDATE chat_requests SET status='completed'")
            row = await (await store._db().execute("SELECT * FROM auxiliary_tasks")).fetchone()
            assert row["status"] == "completed" and row["revision"] == 2
            await service.tick_once()
            projected = await service.status()
            assert projected["local_notifications_processed"] == 1
            assert projected["recent_tasks"][0]["status"] == "completed"
            assert set(projected["recent_tasks"][0]) == {"task_id", "version", "status"}
            await store._db().execute("INSERT INTO chat_deletions VALUES ('synthetic-cid','deleting')")
            assert (await service.status())["metadata_count"] == 0
            assert not (await service.status())["recent_tasks"]
            await service.tick_once()
            assert (await service.status())["metadata_count"] == 0
        finally:
            await service.close()
            await store.close()
    asyncio.run(scenario())


def test_cache_queue_sqlite_checks_and_poll_budgets(tmp_path, monkeypatch):
    async def scenario():
        store, service = await setup(tmp_path)
        monkeypatch.setattr("orvia_backend.auxiliary.service.Redis", FakeRedis)
        try:
            # 正文标记只进入业务事实表，不进入派生表、缓存或通知。
            for index in range(101):
                await store._db().execute("INSERT INTO chat_requests VALUES ('synthetic',?,?,'pending')", (str(index), "SECRET-SYNTHETIC-BODY"))
            await service.configure({"enabled": True, "host": "127.0.0.1", "port": 6379, "db": 0}, "SYNTHETIC-PASSWORD")
            client = service._client
            result = await service.tick_once()
            assert result["notifications_published"] == 100
            assert result["notifications_processed"] == 100
            assert result["cache_hits"] == 100
            assert len(result["recent_tasks"]) == 20
            assert "SECRET-SYNTHETIC-BODY" not in str(client.values) + str(client.queues)
            assert "SYNTHETIC-PASSWORD" not in json.dumps(result)
            assert all(ttl in (30, 60) for ttl in client.ttls.values())
            row = await (await store._db().execute("SELECT task_id,revision FROM auxiliary_tasks LIMIT 1")).fetchone()
            task_id, revision = row
            # 过期/伪造状态不能成为事实，合法通知 cache miss 只读回 SQL。
            client.values[service._cache_key(task_id)] = json.dumps({"task_id": task_id, "version": revision, "status": "completed"})
            client.queues[service._queue_key] = [json.dumps({"task_id": task_id, "version": revision}), "bad", "x" * 1000]
            await service._consume()
            assert (await service.status())["cache_misses"] == 1
            assert (await service.status())["notifications_discarded"] == 2
            await store._db().execute("UPDATE chat_requests SET status='completed' WHERE request_id='0'")
            await service._reconcile({"task_id": task_id, "version": revision}, client.values[service._cache_key(task_id)])
            assert (await service.status())["notifications_discarded"] == 3
            await store._db().execute("DELETE FROM chat_requests")
            await service._reconcile({"task_id": task_id, "version": revision}, client.values[service._cache_key(task_id)])
            assert (await service.status())["metadata_count"] == 0
            assert (await service.status())["notifications_discarded"] == 4
        finally:
            await service.close()
            await store.close()
    asyncio.run(scenario())


def test_rebuild_projection_restart_and_failed_config_is_atomic(tmp_path, monkeypatch):
    async def scenario():
        store, service = await setup(tmp_path)
        monkeypatch.setattr("orvia_backend.auxiliary.service.Redis", FakeRedis)
        try:
            await store._db().execute("INSERT INTO chat_requests VALUES ('synthetic','req','body','waiting_approval')")
            original = await (await store._db().execute("SELECT task_id FROM auxiliary_tasks")).fetchone()
            await store._db().execute("DELETE FROM auxiliary_tasks")
            await service.tick_once()
            item = (await service.status())["recent_tasks"][0]
            assert item["status"] == "waiting_approval" and item["task_id"] != original[0]
            await store._db().execute("UPDATE chat_requests SET status='failed'")
            assert not (await service.status())["recent_tasks"]  # 未消费旧版本不能继续展示。
            await service.tick_once()
            assert (await service.status())["recent_tasks"][0]["status"] == "failed"
            config = {"enabled": True, "host": "127.0.0.1", "port": 6379, "db": 0}
            await service.configure(config)
            client = service._client
            execute = store._db().execute
            async def full(sql, parameters=()):
                if "INSERT OR REPLACE INTO auxiliary_config" in sql:
                    raise OperationalError("synthetic disk full")
                return await execute(sql, parameters)
            with monkeypatch.context() as patch:
                patch.setattr(store._db(), "execute", full)
                with pytest.raises(OperationalError):
                    await service.configure({**config, "port": 6380})
            assert service._client is client and not client.closed
            assert (await service.status())["port"] == 6379
            await service.close()
            service = AuxiliaryService(store)
            await service.open()
            await service.tick_once()
            assert (await service.status())["recent_tasks"][0]["status"] == "failed"
        finally:
            await service.close()
            await store.close()
    asyncio.run(scenario())


def test_timeout_is_bounded_and_local_consumer_continues(tmp_path, monkeypatch):
    async def scenario():
        store, service = await setup(tmp_path)
        monkeypatch.setattr("orvia_backend.auxiliary.service.Redis", FakeRedis)
        try:
            await store._db().execute("INSERT INTO chat_requests VALUES ('synthetic','req','body','pending')")
            await service.configure({"enabled": True, "host": "127.0.0.1", "port": 6379, "db": 0})
            async def blocked(*args):
                await asyncio.sleep(10)
            monkeypatch.setattr(service._client, "eval", blocked)
            loop = asyncio.get_running_loop()
            start = loop.time()
            await service.tick_once()
            assert loop.time() - start < 2
            assert (await service.status())["state"] == "degraded"
            await service.tick_once()
            status = await service.status()
            assert status["local_notifications_processed"] == 1
            assert status["recent_tasks"][0]["status"] == "pending"
            assert status["notifications_processed"] == 0
        finally:
            await service.close()
            await store.close()
    asyncio.run(scenario())


def test_auxiliary_sql_failure_is_visible_without_observer_crash(tmp_path, monkeypatch):
    async def scenario():
        store, service = await setup(tmp_path)
        try:
            execute = store._db().execute
            def unavailable(sql, parameters=()):
                if "INSERT OR IGNORE INTO auxiliary_tasks" in sql:
                    raise OperationalError("synthetic storage failure with private details")
                return execute(sql, parameters)
            with monkeypatch.context() as patch:
                patch.setattr(store._db(), "execute", unavailable)
                await service.tick_once()
            result = await service.status()
            assert result["state"] == "degraded" and result["reason"] == "storage_unavailable"
            assert "details" not in json.dumps(result)
            assert service._task and not service._task.done()
        finally:
            await service.close()
            await store.close()
    asyncio.run(scenario())


def test_disconnect_circuit_breaker_auth_and_restart(tmp_path, monkeypatch):
    async def scenario():
        store, service = await setup(tmp_path)
        clients = []
        def factory(**kwargs):
            client = FakeRedis(**kwargs)
            clients.append(client)
            return client
        monkeypatch.setattr("orvia_backend.auxiliary.service.Redis", factory)
        try:
            config = {"enabled": True, "host": "127.0.0.1", "port": 6379, "db": 0}
            await service.replace_password("SYNTHETIC-PASSWORD")
            await service.configure(config)
            assert clients[-1].kwargs["password"] == "SYNTHETIC-PASSWORD"
            clients[-1].error = ConnectionError("never expose service details")
            await service.tick_once()
            status = await service.status()
            assert status["state"] == "degraded" and "details" not in json.dumps(status)
            for _ in range(3):
                await service.tick_once()
            assert len(clients) == 1  # 熔断期间没有无限隐式重连。
            assert (await service.probe())["state"] == "connected"
            clients[-1].error = AuthenticationError("SYNTHETIC-PASSWORD")
            await service.tick_once()
            assert (await service.status())["reason"] == "authentication_failed"
            await service.replace_password(None)
            assert not (await service.status())["password_configured"]
            await service.close()
            service = AuxiliaryService(store)
            await service.open()
            status = await service.status()
            assert status["enabled"] and status["state"] == "degraded"
            assert not status["password_configured"]
            async with store._db().execute("SELECT config_json FROM auxiliary_config") as cursor:
                assert "PASSWORD" not in (await cursor.fetchone())[0]
        finally:
            await service.close()
            await store.close()
    asyncio.run(scenario())
