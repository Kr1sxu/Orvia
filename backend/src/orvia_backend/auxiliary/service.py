"""Redis 只携带随机任务标识和状态版本；通知永远不能触发业务执行。"""

import asyncio
import json
from typing import Literal
from uuid import UUID, uuid4

import aiosqlite
from pydantic import BaseModel, ConfigDict, Field
from redis.asyncio import Redis
from redis.backoff import NoBackoff
from redis.exceptions import AuthenticationError, RedisError
from redis.retry import Retry

from ..storage import Store


DEFAULT_CONFIG = {"enabled": False, "host": "127.0.0.1", "port": 6379, "db": 0}
STATUSES = {"pending", "waiting_input", "waiting_approval", "completed", "cancelled", "failed", "interrupted"}
UUID_SQL = "lower(hex(randomblob(4)))||'-'||lower(hex(randomblob(2)))||'-4'||substr(lower(hex(randomblob(2))),2)||'-'||substr('89ab',abs(random()%4)+1,1)||substr(lower(hex(randomblob(2))),2)||'-'||lower(hex(randomblob(6)))"


class AuxiliaryConfig(BaseModel):
    """跨进程配置严格限制类型和预算，拒绝任意连接 URL 或扩展 Redis 选项。"""

    model_config = ConfigDict(extra="forbid", strict=True)
    enabled: bool = False
    host: Literal["127.0.0.1", "::1"] = "127.0.0.1"
    port: int = Field(default=6379, ge=1, le=65535)
    db: int = Field(default=0, ge=0, le=15)


def validate_config(config):
    """只接受字面回环地址，不执行 DNS；拒绝 bool 冒充整数及额外选项。"""
    if not isinstance(config, dict) or set(config) != set(DEFAULT_CONFIG):
        raise ValueError("辅助服务配置必须包含 enabled、host、port、db")
    if type(config["enabled"]) is not bool or config["host"] not in ("127.0.0.1", "::1"):
        raise ValueError("辅助服务只允许字面回环地址")
    if type(config["port"]) is not int or not 1 <= config["port"] <= 65535:
        raise ValueError("辅助服务端口必须为 1～65535")
    if type(config["db"]) is not int or not 0 <= config["db"] <= 15:
        raise ValueError("辅助服务数据库必须为 0～15")
    return dict(config)


class AuxiliaryService:
    """有界辅助服务。配置/探测/轮询串行；失联熔断，须显式探测或配置恢复。"""

    def __init__(self, store: Store):
        self.store = store
        self._config = dict(DEFAULT_CONFIG)
        self._password = None
        self._namespace = str(uuid4())
        self._client = None
        self._task = None
        self._lock = asyncio.Lock()
        self._state = "disabled"
        self._reason = None
        self._counts = {name: 0 for name in ("cache_hits", "cache_misses", "notifications_published", "notifications_processed", "notifications_discarded", "local_notifications_processed")}
        self._recent = {}

    async def open(self):
        """迁移仅新增派生表和触发器；请求状态变化与修订在同一 SQLite 写入中完成。"""
        async with self.store._lock:
            db = self.store._db()
            await db.execute("CREATE TABLE IF NOT EXISTS auxiliary_config(id INTEGER PRIMARY KEY CHECK(id=1), config_json TEXT NOT NULL, namespace TEXT NOT NULL)")
            await db.execute("""CREATE TABLE IF NOT EXISTS auxiliary_tasks(
                task_id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, request_id TEXT NOT NULL,
                status TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1, sent_revision INTEGER NOT NULL DEFAULT 0,
                observed_revision INTEGER NOT NULL DEFAULT 0,
                UNIQUE(conversation_id,request_id))""")
            await db.execute(f"""CREATE TRIGGER IF NOT EXISTS auxiliary_request_insert AFTER INSERT ON chat_requests
                WHEN NEW.conversation_id NOT IN (SELECT id FROM chat_deletions)
                BEGIN INSERT OR IGNORE INTO auxiliary_tasks(task_id,conversation_id,request_id,status)
                VALUES ({UUID_SQL},NEW.conversation_id,NEW.request_id,NEW.status); END""")
            await db.execute("""CREATE TRIGGER IF NOT EXISTS auxiliary_request_update AFTER UPDATE OF status ON chat_requests
                WHEN OLD.status IS NOT NEW.status BEGIN UPDATE auxiliary_tasks SET status=NEW.status,revision=revision+1
                WHERE conversation_id=NEW.conversation_id AND request_id=NEW.request_id; END""")
            await db.execute("""CREATE TRIGGER IF NOT EXISTS auxiliary_request_delete AFTER DELETE ON chat_requests
                BEGIN DELETE FROM auxiliary_tasks WHERE conversation_id=OLD.conversation_id AND request_id=OLD.request_id; END""")
            await db.execute("""CREATE TRIGGER IF NOT EXISTS auxiliary_conversation_delete AFTER INSERT ON chat_deletions
                BEGIN DELETE FROM auxiliary_tasks WHERE conversation_id=NEW.id; END""")
            await db.execute("""DELETE FROM auxiliary_tasks WHERE conversation_id IN (SELECT id FROM chat_deletions)
                OR NOT EXISTS (SELECT 1 FROM chat_requests r WHERE r.conversation_id=auxiliary_tasks.conversation_id
                AND r.request_id=auxiliary_tasks.request_id)""")
            async with db.execute("SELECT config_json,namespace FROM auxiliary_config WHERE id=1") as cursor:
                row = await cursor.fetchone()
            if row:
                try:
                    config = validate_config(json.loads(row[0]))
                    namespace = str(UUID(row[1]))
                except (ValueError, TypeError, json.JSONDecodeError):
                    # 损坏的辅助配置仅关闭能力，不覆盖原记录或影响会话事实。
                    self._state, self._reason = "disabled", "unsupported"
                else:
                    self._config, self._namespace = config, namespace
            await db.execute("UPDATE auxiliary_tasks SET sent_revision=0,observed_revision=0")
        if self._config["enabled"]:
            self._state, self._reason = "degraded", "unavailable"
        await self._rebuild_batch()
        self._task = asyncio.create_task(self._poll(), name="orvia-auxiliary")

    async def _rebuild_batch(self):
        """每轮最多补建 100 条；只读取标识和状态，不读取请求正文。"""
        async with self.store._lock:
            db = self.store._db()
            await db.execute(f"""INSERT OR IGNORE INTO auxiliary_tasks(task_id,conversation_id,request_id,status)
                SELECT {UUID_SQL},r.conversation_id,r.request_id,r.status FROM chat_requests r
                WHERE r.conversation_id NOT IN (SELECT id FROM chat_deletions) AND NOT EXISTS
                (SELECT 1 FROM auxiliary_tasks a WHERE a.conversation_id=r.conversation_id AND a.request_id=r.request_id)
                LIMIT 100""")

    async def status(self):
        """状态查询不连接 Redis；计数是辅助诊断，不是任务完成数量。"""
        async with self.store._lock:
            async with self.store._db().execute("SELECT COUNT(*) FROM auxiliary_tasks") as cursor:
                count = (await cursor.fetchone())[0]
            # 即使轮询尚未来得及消费，状态接口也不返回已删除或旧版本投影。
            for task_id, item in list(self._recent.items()):
                async with self.store._db().execute("""SELECT a.status,a.revision FROM auxiliary_tasks a JOIN chat_requests r
                    ON r.conversation_id=a.conversation_id AND r.request_id=a.request_id
                    WHERE a.task_id=? AND a.status=r.status AND a.conversation_id NOT IN (SELECT id FROM chat_deletions)""", (task_id,)) as cursor:
                    row = await cursor.fetchone()
                if not row or row["revision"] != item["version"] or row["status"] != item["status"]:
                    self._recent.pop(task_id, None)
        return {**self._config, "state": self._state, "reason": self._reason,
                "password_configured": bool(self._password), **self._counts, "metadata_count": count,
                "recent_tasks": list(reversed(list(self._recent.values())))}

    async def configure(self, config, password=None):
        """显式启停并保存非敏感配置；密码只保留内存，不写 SQLite 或错误消息。"""
        parsed = validate_config(config)
        self._validate_password(password)
        async with self._lock:
            # 保存失败时保留旧配置和旧连接，避免响应失败却已暗中改变连接目标。
            async with self.store._lock:
                await self.store._db().execute("INSERT OR REPLACE INTO auxiliary_config VALUES (1,?,?)", (json.dumps(parsed), self._namespace))
            await self._disconnect()
            self._config = parsed
            if password is not None:
                self._password = password
            if parsed["enabled"]:
                await self._connect()
            else:
                self._state, self._reason = "disabled", None
        return await self.status()

    @staticmethod
    def _validate_password(password):
        if password is not None and (not isinstance(password, str) or not 1 <= len(password) <= 4096):
            raise ValueError("辅助服务凭据格式无效")

    async def replace_password(self, password):
        """凭据撤回/替换立即关闭旧连接；启用时只探测同一固定本地端点。"""
        self._validate_password(password)
        async with self._lock:
            await self._disconnect()
            self._password = password
            if self._config["enabled"]:
                await self._connect()
        return await self.status()

    async def probe(self):
        """熔断后仅用户显式入口调用探测；不重试任何业务或模型请求。"""
        async with self._lock:
            if self._config["enabled"]:
                await self._disconnect()
                await self._connect()
        return await self.status()

    async def _connect(self):
        self._client = Redis(host=self._config["host"], port=self._config["port"], db=self._config["db"],
                             password=self._password, decode_responses=True, socket_timeout=0.25,
                             socket_connect_timeout=0.25, retry=Retry(NoBackoff(), 0),
                             max_connections=1, health_check_interval=0)
        try:
            async with asyncio.timeout(0.5):
                await self._client.ping()
            async with self.store._lock:
                await self.store._db().execute("UPDATE auxiliary_tasks SET sent_revision=0")
        except (RedisError, OSError, TimeoutError) as error:
            await self._fail(error)
        except aiosqlite.Error:
            self._state, self._reason = "degraded", "storage_unavailable"
            await self._disconnect()
        else:
            self._state, self._reason = "connected", None

    async def _fail(self, error):
        """服务返回的错误文本可包含凭据，故只公开固定分类，绝不日志回显。"""
        if isinstance(error, AuthenticationError):
            reason = "authentication_failed" if self._password else "authentication_required"
        elif isinstance(error, TimeoutError):
            reason = "timeout"
        else:
            reason = "unavailable"
        self._state, self._reason = "degraded", reason
        await self._disconnect()

    async def _disconnect(self):
        client, self._client = self._client, None
        if client:
            try:
                async with asyncio.timeout(0.25):
                    await client.aclose()
            except (RedisError, OSError, TimeoutError):
                pass  # 已断开本地引用，关闭错误没有业务后果，也不带出服务端文本。

    @property
    def _queue_key(self):
        return f"orvia:aux:{self._namespace}:notifications"

    def _cache_key(self, task_id):
        return f"orvia:aux:{self._namespace}:task:{task_id}"

    async def _poll(self):
        try:
            while True:
                await asyncio.sleep(2)
                await self.tick()
        except asyncio.CancelledError:
            raise

    async def tick(self):
        """每轮总预算两秒；单次 Redis 操作无重试，异常熔断后停止网络轮询。"""
        async with self._lock:
            try:
                # 包含重建、SQL核对及网络，总工作1.5秒，另留0.25秒关闭连接。
                async with asyncio.timeout(1.5):
                    await self._rebuild_batch()
                    if self._state != "connected" or not self._client:
                        await self._consume_local()
                        return
                    await self._publish()
                    consumed = await self._consume()
                    # 队列被其他读者取走、TTL过期或批次裁剪均可从同一SQL派生通知恢复。
                    await self._consume_local(limit=100-consumed)
            except (RedisError, OSError, TimeoutError, UnicodeError) as error:
                await self._fail(error)
            except aiosqlite.Error:
                self._state, self._reason = "degraded", "storage_unavailable"
                await self._disconnect()

    async def tick_once(self):
        """维护及验收入口，执行一次同预算轮询；不向渲染进程暴露业务执行能力。"""
        await self.tick()
        return await self.status()

    async def _publish(self):
        async with self.store._lock:
            async with self.store._db().execute("SELECT task_id,status,revision FROM auxiliary_tasks WHERE revision!=sent_revision LIMIT 100") as cursor:
                rows = await cursor.fetchall()
        if not rows:
            return
        # 一个有界 pipeline 保存 TTL 元数据、256 条队列和60秒过期，减少每条网络往返。
        pipeline = self._client.pipeline(transaction=True)
        for row in rows:
            if row["status"] not in STATUSES:
                continue
            pipeline.set(self._cache_key(row["task_id"]), json.dumps({"task_id": row["task_id"], "version": row["revision"], "status": row["status"]}), ex=30)
            pipeline.rpush(self._queue_key, json.dumps({"task_id": row["task_id"], "version": row["revision"]}))
        pipeline.ltrim(self._queue_key, -256, -1)
        pipeline.expire(self._queue_key, 60)
        await pipeline.execute()
        async with self.store._lock:
            for row in rows:
                # 并发更新保留新版本待通知；通知成功也不能更改业务请求状态。
                await self.store._db().execute("UPDATE auxiliary_tasks SET sent_revision=? WHERE task_id=? AND revision=?", (row["revision"], row["task_id"], row["revision"]))
        self._counts["notifications_published"] += len(rows)

    @staticmethod
    def _notification(raw):
        if not isinstance(raw, str) or len(raw) > 128:
            return None
        try:
            value = json.loads(raw)
            if not isinstance(value, dict) or set(value) != {"task_id", "version"}:
                return None
            if str(UUID(value["task_id"])) != value["task_id"] or type(value["version"]) is not int or not 1 <= value["version"] <= 2**63 - 1:
                return None
            return value
        except (ValueError, TypeError, KeyError, AttributeError):
            return None

    async def _consume(self):
        # 固定脚本在服务端裁剪不可信值，避免单个恶意长条目扩大跨进程内存预算。
        raw = await self._client.eval("""local out={}; for i=1,100 do
            local v=redis.call('LPOP',KEYS[1]); if not v then break end
            if string.len(v)<=128 then table.insert(out,v) else table.insert(out,'') end
            end; return out""", 1, self._queue_key)
        if not raw:
            return 0
        notifications = [self._notification(item) for item in raw]
        pipeline = self._client.pipeline(transaction=False)
        valid = [item for item in notifications if item]
        for item in valid:
            pipeline.eval("local v=redis.call('GET',KEYS[1]); if v and string.len(v)<=256 then return v end; return false", 1, self._cache_key(item["task_id"]))
        cached = await pipeline.execute() if valid else []
        self._counts["notifications_discarded"] += len(notifications) - len(valid)
        for item, value in zip(valid, cached, strict=True):
            await self._reconcile(item, value)
        return len(raw)

    async def _consume_local(self, limit=100):
        """本地降级消费者刷新同一只读状态投影，不称作 Redis 通知或缓存命中。"""
        async with self.store._lock:
            async with self.store._db().execute("SELECT task_id,revision FROM auxiliary_tasks WHERE revision!=observed_revision LIMIT ?", (limit,)) as cursor:
                rows = await cursor.fetchall()
        for row in rows:
            await self._reconcile({"task_id": row["task_id"], "version": row["revision"]}, None, local=True)

    async def _reconcile(self, item, cached, local=False):
        """缓存即使命中也重新核对最新 SQL；删除、过期修订和伪造消息只丢弃。"""
        async with self.store._lock:
            async with self.store._db().execute("""SELECT a.status,a.revision FROM auxiliary_tasks a JOIN chat_requests r
                ON r.conversation_id=a.conversation_id AND r.request_id=a.request_id
                WHERE a.task_id=? AND a.status=r.status AND a.conversation_id NOT IN (SELECT id FROM chat_deletions)""", (item["task_id"],)) as cursor:
                row = await cursor.fetchone()
        if not row or row["revision"] != item["version"]:
            self._counts["notifications_discarded"] += 1
            return
        expected = {"task_id": item["task_id"], "version": row["revision"], "status": row["status"]}
        try:
            hit = isinstance(cached, str) and len(cached) <= 256 and json.loads(cached) == expected
        except (ValueError, TypeError):
            hit = False
        if local:
            self._counts["local_notifications_processed"] += 1
        else:
            self._counts["cache_hits" if hit else "cache_misses"] += 1
            self._counts["notifications_processed"] += 1
        self._recent.pop(item["task_id"], None)
        self._recent[item["task_id"]] = expected
        if len(self._recent) > 20:
            self._recent.pop(next(iter(self._recent)))
        async with self.store._lock:
            await self.store._db().execute("UPDATE auxiliary_tasks SET observed_revision=? WHERE task_id=? AND revision=?", (item["version"], item["task_id"], item["version"]))

    async def close(self):
        """先取消自身轮询再断连接、清除内存密码；不删除用户 Redis 服务或业务数据。"""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        async with self._lock:
            await self._disconnect()
            self._password = None
