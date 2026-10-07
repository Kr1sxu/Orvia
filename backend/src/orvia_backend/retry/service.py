"""有限重试执行器及无正文SQLite尝试账本；取消与终态拒绝晚到成功。"""
import asyncio
import copy
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
import hashlib
import json
import math
import re
from time import monotonic
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from .policy import BACKOFF, TOOLS, RetryError, classify


def stamp():
    return datetime.now(UTC).isoformat()


class RetryService:
    """可信适配器保留原deadline；不接收renderer安全分类或任何自动批准。"""
    def __init__(self, store=None):
        self.store = store
        self._scope = ContextVar(f"orvia_retry_scope_{id(self)}", default=None)
        self._runs = {}
        self._active = {}
        self._settled = {}
        self._closed = False

    @contextmanager
    def activate(self, cid, business_id):
        """可信handler绑定会话及请求身份；ContextVar防止并发会话串账。"""
        self._identity(cid, business_id)
        token = self._scope.set({'cid':cid,'parent':business_id,'sequence':0})
        try:
            yield
        finally:
            self._scope.reset(token)

    @staticmethod
    def _identity(cid, business_id):
        if cid is not None:
            try:
                if not isinstance(cid, str) or str(UUID(cid)) != cid:
                    raise ValueError()
            except ValueError:
                raise RetryError("RETRY_IDENTITY", "重试会话身份无效") from None
        if not isinstance(business_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", business_id):
            raise RetryError("RETRY_IDENTITY", "重试业务身份无效")

    async def _alive(self, db, cid):
        async with db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('chat_conversations','chat_deletions')") as cursor:
            tables={row[0] for row in await cursor.fetchall()}
        if 'chat_deletions' in tables:
            async with db.execute('SELECT 1 FROM chat_deletions WHERE id=?',(cid,)) as cursor:
                if await cursor.fetchone():
                    raise RetryError('RETRY_CONVERSATION','所属会话正在删除，拒绝重试及迟到记录')
        if 'chat_conversations' in tables:
            async with db.execute('SELECT 1 FROM chat_conversations WHERE id=? UNION SELECT 1 FROM missions WHERE id=?',(cid,cid)) as cursor:
                if not await cursor.fetchone():
                    raise RetryError('RETRY_CONVERSATION','所属会话或独立Mission不存在，拒绝迟到记录')

    async def open(self):
        """启动标记遗留尝试中断；不恢复执行，不保存旧响应或参数正文。"""
        self._closed = False
        if self.store is None:
            return
        async with self.store._lock:
            db = self.store._db()
            await db.execute("CREATE TABLE IF NOT EXISTS retry_runs(cid TEXT NOT NULL,business_id TEXT NOT NULL,tool TEXT NOT NULL,parameter_digest TEXT NOT NULL,state TEXT NOT NULL,started_at TEXT NOT NULL,finished_at TEXT,PRIMARY KEY(cid,business_id))")
            await db.execute("CREATE TABLE IF NOT EXISTS retry_attempts(cid TEXT NOT NULL,business_id TEXT NOT NULL,sequence INTEGER NOT NULL,state TEXT NOT NULL,started_at TEXT NOT NULL,finished_at TEXT,reason TEXT,delay_seconds REAL NOT NULL,error_code TEXT,PRIMARY KEY(cid,business_id,sequence))")
            await db.execute("BEGIN IMMEDIATE")
            try:
                now = stamp()
                await db.execute("UPDATE retry_runs SET state='interrupted',finished_at=? WHERE state='running'", (now,))
                await db.execute("UPDATE retry_attempts SET state='interrupted',finished_at=?,reason='interrupted',error_code='RETRY_INTERRUPTED' WHERE state='running'", (now,))
                await db.commit()
            except BaseException:
                await db.rollback()
                raise

    async def _save(self, cid, record, *, initial=False, revoke=False):
        if self.store is None or cid is None:
            return
        async with self.store._lock:
            db = self.store._db()
            await db.execute("BEGIN IMMEDIATE")
            try:
                await self._alive(db, cid)
                if initial:
                    async with db.execute("SELECT 1 FROM retry_runs WHERE cid=? AND business_id=?", (cid, record['business_id'])) as cursor:
                        if await cursor.fetchone():
                            raise RetryError("RETRY_TERMINAL", "该业务已有尝试事实，不能自动重新执行")
                    # 最多32个并发；保留无正文身份事实，避免清理历史后重放旧业务ID。
                    async with db.execute("SELECT count(*) FROM retry_runs WHERE cid=? AND state='running'", (cid,)) as cursor:
                        if (await cursor.fetchone())[0] >= 32:
                            raise RetryError("RETRY_LIMIT", "当前会话运行重试数已达上限")
                    await db.execute("INSERT INTO retry_runs VALUES(?,?,?,?,?,?,?)", (cid, record['business_id'], record['tool'], record['parameter_digest'], record['state'], record['started_at'], record['finished_at']))
                else:
                    # 删除后不晚写重建；CAS终态保证重复回调不能复活原业务。
                    async with db.execute("SELECT state FROM retry_runs WHERE cid=? AND business_id=?", (cid,record['business_id'])) as cursor:
                        old = await cursor.fetchone()
                    if not old or (old[0] != 'running' and not (revoke and old[0]=='succeeded')):
                        raise RetryError("RETRY_TERMINAL", "业务已终止或删除，拒绝迟到事实")
                    await db.execute("UPDATE retry_runs SET state=?,finished_at=? WHERE cid=? AND business_id=? AND (state='running' OR (? AND state='succeeded'))", (record['state'],record['finished_at'],cid,record['business_id'],revoke))
                for attempt in record['attempts']:
                    await db.execute("INSERT INTO retry_attempts VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(cid,business_id,sequence) DO UPDATE SET state=excluded.state,finished_at=excluded.finished_at,reason=excluded.reason,delay_seconds=excluded.delay_seconds,error_code=excluded.error_code WHERE retry_attempts.state='running' OR (? AND retry_attempts.state='succeeded')", (cid,record['business_id'],attempt['sequence'],attempt['state'],attempt['started_at'],attempt['finished_at'],attempt['reason'],attempt['delay_seconds'],attempt['error_code'],revoke))
                await db.commit()
            except BaseException:
                await db.rollback()
                raise

    async def _finish(self, cid, record, state, *, reason=None, code=None):
        if record['state'] != 'running':
            return
        candidate=copy.deepcopy(record)
        candidate.update(state=state,finished_at=stamp())
        if candidate['attempts'] and candidate['attempts'][-1]['state']=='running':
            candidate['attempts'][-1].update(state=state,finished_at=candidate['finished_at'],reason=reason,error_code=code)
        await self._save(cid,candidate,revoke=state in {'cancelled','timed_out'})
        record.update(candidate)

    @staticmethod
    def _discard(task):
        if not task.cancelled():
            task.exception()

    async def _bounded(self, awaitable, deadline, cancel_event):
        """不等取消抵抗协程的晚响应；终态先确定，晚值只排空且不会成为业务事实。"""
        task = asyncio.create_task(awaitable)
        waiter = asyncio.create_task(cancel_event.wait())
        consumed=False
        try:
            done, _ = await asyncio.wait((task,waiter),timeout=max(0.0,deadline-monotonic()),return_when=asyncio.FIRST_COMPLETED)
            if waiter in done or cancel_event.is_set():
                raise asyncio.CancelledError
            if task not in done or monotonic()>=deadline:
                raise TimeoutError
            consumed=True
            return task.result()
        finally:
            waiter.cancel()
            if not task.done():
                task.cancel()
                task.add_done_callback(self._discard)
            elif not consumed:
                self._discard(task)

    async def _revoke_success(self,cid,record,state,reason,code):
        """仅当前finalizer可保守撤回返回资格；不会复活终态、接收晚值或新增尝试。"""
        if record['state']=='succeeded':
            candidate=copy.deepcopy(record)
            candidate.update(state=state,finished_at=stamp())
            candidate['attempts'][-1].update(state=state,finished_at=candidate['finished_at'],reason=reason,error_code=code)
            await self._save(cid,candidate,revoke=True)
            record.update(candidate)

    async def run(self, tool, parameters, callback, *, deadline, cid=None, business_id=None, cancel_event=None):
        """最多三次同业务尝试；返回成功值只说明操作返回，完成判断仍由原业务核验。"""
        if tool not in TOOLS:
            raise RetryError("RETRY_POLICY", "该操作不具有程序确认的自动重试资格")
        if self._closed:
            raise RetryError("RETRY_CLOSED", "重试服务已关闭")
        if type(deadline) not in (int,float) or not math.isfinite(deadline):
            raise RetryError("RETRY_BUDGET", "必须沿用原业务有限deadline")
        try:
            digest = hashlib.sha256(json.dumps(parameters,ensure_ascii=False,sort_keys=True,allow_nan=False,separators=(',',':')).encode('utf-8')).hexdigest()
        except (TypeError,ValueError,UnicodeError,RecursionError):
            raise RetryError("RETRY_PARAMETERS", "重试参数须为有限JSON") from None
        scope = self._scope.get()
        if cid is None and scope is not None:
            cid = scope['cid']
        elif cid is not None and scope is not None and cid != scope['cid']:
            raise RetryError('RETRY_IDENTITY','可信请求与读取所属会话不一致')
        if business_id is None:
            # 同一请求内重复只读调用是不同业务，只有单业务内部三attempt共享身份。
            if scope is not None:
                scope['sequence'] += 1
                business_id = str(uuid5(NAMESPACE_URL,f"{scope['parent']}:{scope['sequence']}:{tool}:{digest}"))
            else:
                business_id = str(uuid4())
        self._identity(cid,business_id)
        key = (cid,business_id)
        if key in self._runs or key in self._active:
            raise RetryError("RETRY_TERMINAL", "同一业务已开始或结束，不重新调用")
        event = cancel_event or asyncio.Event()
        record = {'business_id':business_id,'tool':tool,'parameter_digest':digest,'state':'running','started_at':stamp(),'finished_at':None,'attempts':[]}
        self._active[key] = event
        settled=asyncio.get_running_loop().create_future()
        self._settled[key]=settled
        registered=False
        try:
            initial=asyncio.create_task(self._save(cid,record,initial=True))
            try:
                await asyncio.shield(initial)
            except asyncio.CancelledError:
                # 初始事务若已入队，等其落定再记录取消；不能留后台晚写越过close/Store关闭。
                await initial
                registered=True
                self._runs[key]=record
                raise
            registered=True
            self._runs[key] = record
            for sequence in range(1,4):
                if event.is_set():
                    raise asyncio.CancelledError
                if deadline <= monotonic():
                    raise TimeoutError
                attempt = {'sequence':sequence,'state':'running','started_at':stamp(),'finished_at':None,'reason':'initial' if sequence==1 else record['attempts'][-1]['reason'],'delay_seconds':0.0,'error_code':None}
                record['attempts'].append(attempt)
                await self._save(cid,record)
                if event.is_set():
                    raise asyncio.CancelledError
                if deadline <= monotonic():
                    raise TimeoutError
                try:
                    value = await self._bounded(callback(),deadline,event)
                except (asyncio.CancelledError,TimeoutError):
                    raise
                except Exception as error:
                    reason, code, requested = classify(tool,error)
                    delay = max(BACKOFF[min(sequence-1,1)],requested or 0.0)
                    failure_state='unknown' if code=='NETWORK_UNKNOWN' else 'failed'
                    attempt.update(state=failure_state,finished_at=stamp(),reason=reason,error_code=code)
                    can_retry = (reason!='not_retryable' and requested is not None and sequence<3
                                 and delay<=0.5 and delay<deadline-monotonic())
                    if not can_retry:
                        if requested is None:
                            attempt['reason']='not_retryable'
                        elif reason!='not_retryable' and sequence<3:
                            attempt['reason']='budget_exhausted'
                        await self._finish(cid,record,failure_state)
                        raise
                    attempt['delay_seconds']=delay
                    await self._save(cid,record)
                    await self._bounded(asyncio.sleep(delay),deadline,event)
                    continue
                if event.is_set() or self._closed:
                    raise asyncio.CancelledError
                if monotonic()>=deadline:
                    raise TimeoutError
                await self._finish(cid,record,'succeeded',reason='success')
                # 保存账本亦消耗原预算；存储锁等候后不能把超时/取消的值交回业务。
                if event.is_set() or self._closed:
                    await self._revoke_success(cid,record,'cancelled','cancelled','RETRY_CANCELLED')
                    raise asyncio.CancelledError
                if monotonic()>=deadline:
                    await self._revoke_success(cid,record,'timed_out','budget_exhausted','RETRY_TIMEOUT')
                    raise TimeoutError
                return value
            raise AssertionError('bounded attempt loop')
        except asyncio.CancelledError:
            if registered:
                finish=self._revoke_success(cid,record,'cancelled','cancelled','RETRY_CANCELLED') if record['state']=='succeeded' else self._finish(cid,record,'cancelled',reason='cancelled',code='RETRY_CANCELLED')
                await asyncio.shield(finish)
            raise
        except TimeoutError:
            if registered:
                if record['state']=='succeeded':
                    await self._revoke_success(cid,record,'timed_out','budget_exhausted','RETRY_TIMEOUT')
                else:
                    await self._finish(cid,record,'timed_out',reason='budget_exhausted',code='RETRY_TIMEOUT')
            raise
        except BaseException:
            if registered:
                await self._finish(cid,record,'failed',reason='not_retryable',code='NOT_RETRYABLE')
            raise
        finally:
            self._active.pop(key,None)
            self._settled.pop(key,None)
            if not settled.done():
                settled.set_result(None)
            # 内存无正文回执最多128；不保留返回值、不缓存失败参数。
            for old in list(self._runs):
                if len(self._runs)<=128:
                    break
                if old not in self._active:
                    del self._runs[old]

    async def history(self, cid):
        """只投影无正文尝试；跨会话由精确cid查询，最多32run/32KiB。"""
        self._identity(cid,'history')
        if self.store is None:
            runs = [dict(r,attempts=[dict(a) for a in r['attempts']]) for (c,_),r in self._runs.items() if c==cid]
            runs.reverse()
        else:
            async with self.store._lock:
                db=self.store._db();await self._alive(db,cid)
                async with db.execute("SELECT business_id,tool,parameter_digest,state,started_at,finished_at FROM retry_runs WHERE cid=? ORDER BY started_at DESC LIMIT 33",(cid,)) as cursor:
                    runs=[dict(row) for row in await cursor.fetchall()]
                for run in runs:
                    async with db.execute("SELECT sequence,state,started_at,finished_at,reason,delay_seconds,error_code FROM retry_attempts WHERE cid=? AND business_id=? ORDER BY sequence",(cid,run['business_id'])) as cursor:
                        run['attempts']=[dict(row) for row in await cursor.fetchall()]
        truncated = len(runs)>32
        runs=runs[:32]
        result={'id':cid,'runs':runs,'truncated':truncated}
        while len(json.dumps(result,separators=(',',':')).encode())>32768:
            runs.pop();result['truncated']=True
        return result

    async def has_unresolved(self,cid):
        """只阻止真实running尝试的删除；启动interrupted不代表仍有执行或需要重放。"""
        if any(key[0]==cid for key in self._active):
            return True
        if self.store is None:
            return False
        async with self.store._lock:
            async with self.store._db().execute("SELECT 1 FROM retry_runs WHERE cid=? AND state='running' LIMIT 1",(cid,)) as cursor:
                return await cursor.fetchone() is not None

    async def forget(self,cid):
        """删除生命周期清理内存投影并停止未来尝试；SQLite正文清除仍由原事务负责。"""
        waiting=[]
        for key,event in tuple(self._active.items()):
            if key[0]==cid:
                event.set();waiting.append(self._settled[key])
        if waiting:
            await asyncio.gather(*waiting)
        for key in tuple(self._runs):
            if key[0]==cid:
                del self._runs[key]

    async def close(self):
        """停止等待并等账本收尾；返回前无run再写Store，不等待取消抵抗的晚响应。"""
        self._closed=True
        for event in tuple(self._active.values()):
            event.set()
        if self._settled:
            await asyncio.gather(*tuple(self._settled.values()))
