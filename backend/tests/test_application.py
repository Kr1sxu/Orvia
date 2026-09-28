"""应用接口与真实临时数据库集成；不连接模型，不读取开发凭据。"""

import asyncio
import json
import sqlite3
from uuid import uuid4

from orvia_backend.application import Application

SYNTHETIC_KEY = "synthetic-application-secret-marker"


async def call(app, method, params=None):
    return await app.handle(json.dumps({"v": 1, "id": "test", "method": method, "params": params or {}}).encode())


def test_handshake_and_initialization_boundaries(tmp_path):
    async def scenario():
        app = Application()
        init = {"data_directory": str(tmp_path), "credentials": {"main": SYNTHETIC_KEY}}
        try:
            assert (await call(app, "initialize", init))["error"]["code"] == "NOT_READY"
            assert not (tmp_path / "app.sqlite").exists()
            assert (await call(app, "hello"))["ok"]
            assert (await call(app, "missions.create", {"client_request_id": str(uuid4()), "title": "合成"}))["error"]["code"] == "NOT_INITIALIZED"
            assert (await call(app, "initialize", init))["result"] == {"initialized": True}
            assert (await call(app, "initialize", init))["error"]["code"] == "ALREADY_INITIALIZED"
        finally:
            await app.close()
    asyncio.run(scenario())


def test_mission_lifecycle_credentials_not_echoed_or_persisted(tmp_path):
    async def scenario():
        app = Application()
        replies = []
        try:
            await call(app, "hello")
            replies.append(await call(app, "initialize", {"data_directory": str(tmp_path), "credentials": {"main": SYNTHETIC_KEY}}))
            request = {"client_request_id": str(uuid4()), "title": "合成草稿"}
            created = await call(app, "missions.create", request)
            replies.append(created)
            assert created["ok"]
            assert (await call(app, "missions.create", request))["result"] == created["result"]
            assert (await call(app, "missions.get", {"id": created["result"]["id"]}))["result"] == created["result"]
            assert (await call(app, "missions.list"))["result"]["missions"] == [created["result"]]
            assert (await call(app, "missions.create", {**request, "title": "另一草稿"}))["error"]["code"] == "CONFLICT"
            replies.append(await call(app, "credentials.replace", {"credentials": {"main": "synthetic-other-secret"}}))
            replies.append(await call(app, "configuration.status"))
            assert (await call(app, "missions.get", {"id": created["result"]["id"]}))["result"]["models"] == created["result"]["models"]
            assert (await call(app, "missions.get", {"id": str(uuid4())}))["error"]["code"] == "NOT_FOUND"
            assert SYNTHETIC_KEY not in json.dumps(replies)
            assert "synthetic-other-secret" not in json.dumps(replies)
        finally:
            await app.close()
        for file in tmp_path.iterdir():
            if file.is_file():
                assert SYNTHETIC_KEY.encode() not in file.read_bytes()
                assert b"synthetic-other-secret" not in file.read_bytes()
        restored = Application()
        try:
            await call(restored, "hello")
            await call(restored, "initialize", {"data_directory": str(tmp_path), "credentials": {}})
            assert (await call(restored, "missions.list"))["result"]["missions"] == [created["result"]]
        finally:
            await restored.close()
    asyncio.run(scenario())


def test_invalid_params_are_sanitized(tmp_path):
    async def scenario():
        app = Application()
        try:
            await call(app, "hello")
            response = await call(app, "initialize", {"data_directory": str(tmp_path), "credentials": {"main": SYNTHETIC_KEY + "\n"}})
            assert response["error"]["code"] == "INVALID_PARAMS"
            assert SYNTHETIC_KEY not in json.dumps(response)
            await call(app, "initialize", {"data_directory": str(tmp_path), "credentials": {}})
            for method, params in [("missions.create", {"client_request_id": SYNTHETIC_KEY, "title": "合成"}), ("missions.get", {"id": []}), ("configuration.status", {"unexpected": SYNTHETIC_KEY})]:
                response = await call(app, method, params)
                assert response["error"]["code"] == "INVALID_PARAMS"
                assert SYNTHETIC_KEY not in json.dumps(response)
        finally:
            await app.close()
    asyncio.run(scenario())


def test_future_database_version_refused(tmp_path):
    with sqlite3.connect(tmp_path / "app.sqlite") as db:
        db.execute("PRAGMA user_version=2")
    async def scenario():
        app = Application()
        try:
            await call(app, "hello")
            response = await call(app, "initialize", {"data_directory": str(tmp_path), "credentials": {"main": SYNTHETIC_KEY}})
            assert response["error"]["code"] == "STORAGE_UNAVAILABLE"
            assert SYNTHETIC_KEY not in json.dumps(response)
            assert app.store is None
            assert (await call(app, "missions.list"))["error"]["code"] == "NOT_INITIALIZED"
        finally:
            await app.close()
    asyncio.run(scenario())
