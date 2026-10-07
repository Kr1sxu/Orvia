"""V4-011真实SQLite锁/无正文账本及有界异步边界；零模型、无用户文件。"""
import asyncio
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
import json
import sqlite3
from time import monotonic
import time
from uuid import uuid4

import httpx
import pytest

from orvia_backend.retry import HTTPTransient, RetryError, RetryService
from orvia_backend.retry.policy import classify, retry_after
from orvia_backend.storage import Store


async def stored(tmp_path):
    store=Store(tmp_path/'facts.sqlite3');await store.open()
    retry=RetryService(store);await retry.open()
    return store,retry


def test_real_sqlite_busy_retries_same_business_then_read(tmp_path):
    async def run():
        path=tmp_path/'locked.sqlite3'
        writer=sqlite3.connect(path);writer.execute('CREATE TABLE data(value TEXT)');writer.execute("INSERT INTO data VALUES('合成值')");writer.commit();writer.execute('BEGIN EXCLUSIVE')
        retry=RetryService();cid=str(uuid4());bid=str(uuid4());calls=[]
        async def read():
            calls.append(1)
            def query():
                with sqlite3.connect(path,timeout=0) as reader:return reader.execute('SELECT value FROM data').fetchone()[0]
            return await asyncio.to_thread(query)
        async def unlock():await asyncio.sleep(0.07);writer.rollback()
        release=asyncio.create_task(unlock())
        try:
            assert await retry.run('context.sqlite_read',{'query':'合成'},read,deadline=monotonic()+2,cid=cid,business_id=bid)=='合成值'
            rows=(await retry.history(cid))['runs'];assert len(rows)==1 and rows[0]['business_id']==bid
            assert [a['sequence'] for a in rows[0]['attempts']]==[1,2]
            assert rows[0]['attempts'][0]['reason']=='sqlite_busy' and len(calls)==2
        finally:await release;writer.close()
    asyncio.run(run())


def test_real_sqlite_lock_stops_at_three_attempts(tmp_path):
    async def run():
        path=tmp_path/'locked.sqlite3';writer=sqlite3.connect(path);writer.execute('CREATE TABLE data(value TEXT)');writer.commit();writer.execute('BEGIN EXCLUSIVE')
        retry=RetryService();cid=str(uuid4());calls=[]
        async def read():
            calls.append(1)
            with sqlite3.connect(path,timeout=0) as reader:return reader.execute('SELECT value FROM data').fetchall()
        try:
            with pytest.raises(sqlite3.OperationalError):await retry.run('context.sqlite_read',{},read,deadline=monotonic()+2,cid=cid)
            assert len(calls)==3 and (await retry.history(cid))['runs'][0]['state']=='failed'
        finally:writer.rollback();writer.close()
    asyncio.run(run())


@pytest.mark.parametrize('tool',['model.main','shell.run','process.terminate','files.move','browser.external','mcp.readOnlyHint','retrieval.search'])
def test_fixed_policy_rejects_unsafe_and_unconfirmed_operations(tool):
    async def run():
        calls=[]
        async def callback():calls.append(1)
        with pytest.raises(RetryError,match='程序确认'):await RetryService().run(tool,{},callback,deadline=monotonic()+1)
        assert calls==[]
    asyncio.run(run())


@pytest.mark.parametrize('error',[httpx.ReadTimeout('synthetic'),httpx.WriteError('synthetic'),httpx.RemoteProtocolError('synthetic'),ValueError('schema'),PermissionError('denied'),HTTPTransient(401),HTTPTransient(500),sqlite3.OperationalError('database is locked')])
def test_unknown_permission_format_and_message_only_lock_not_retry(error):
    async def run():
        service=RetryService();cid=str(uuid4());calls=[]
        async def fail():calls.append(1);raise error
        with pytest.raises(type(error)):await service.run('browser.static_read',{},fail,deadline=monotonic()+1,cid=cid)
        assert len(calls)==1 and (await service.history(cid))['runs'][0]['attempts'][0]['reason']=='not_retryable'
        if isinstance(error,(httpx.ReadTimeout,httpx.WriteError,httpx.RemoteProtocolError)):
            assert (await service.history(cid))['runs'][0]['state']=='unknown'
    asyncio.run(run())


@pytest.mark.parametrize('value,expected',[('0',0.0),('1',1.0),('-1',None),('NaN',None),('1e309',None),('0.3',None),('',None)])
def test_retry_after_seconds_strict(value,expected):assert retry_after(value)==expected


def test_retry_after_httpdate_and_future_budget():
    now=datetime(2026,10,8,tzinfo=UTC)
    assert retry_after(format_datetime(now+timedelta(seconds=2),usegmt=True),now=now)==2
    assert retry_after(format_datetime(now-timedelta(seconds=2),usegmt=True),now=now)==0
    async def run():
        service=RetryService();cid=str(uuid4());calls=[]
        async def fail():calls.append(1);raise HTTPTransient(429,'2')
        started=monotonic()
        with pytest.raises(HTTPTransient):await service.run('browser.static_read',{},fail,deadline=monotonic()+0.1,cid=cid)
        assert len(calls)==1 and monotonic()-started<0.2
        assert (await service.history(cid))['runs'][0]['attempts'][0]['reason']=='budget_exhausted'
    asyncio.run(run())


def test_cancellation_during_backoff_stops_future_attempt():
    async def run():
        service=RetryService();cid=str(uuid4());event=asyncio.Event();calls=[]
        async def fail():calls.append(1);raise httpx.ConnectError('synthetic')
        task=asyncio.create_task(service.run('browser.static_read',{},fail,deadline=monotonic()+3,cid=cid,cancel_event=event))
        await asyncio.sleep(0.04);event.set()
        with pytest.raises(asyncio.CancelledError):await task
        assert len(calls)==1 and (await service.history(cid))['runs'][0]['state']=='cancelled'
    asyncio.run(run())


@pytest.mark.parametrize('terminal',['timeout','cancel','close'])
def test_late_success_never_resurrects_terminal(terminal):
    async def run():
        service=RetryService();cid=str(uuid4());event=asyncio.Event();finished=asyncio.Event();entered=asyncio.Event()
        async def late():
            entered.set()
            try:await asyncio.sleep(10)
            except asyncio.CancelledError:await asyncio.sleep(0.02)
            finished.set();return '晚到值必须丢弃'
        task=asyncio.create_task(service.run('browser.static_read',{},late,deadline=monotonic()+(.05 if terminal=='timeout' else 3),cid=cid,cancel_event=event))
        await asyncio.wait_for(entered.wait(),.5)
        if terminal=='cancel':event.set()
        elif terminal=='close':await service.close()
        with pytest.raises(TimeoutError if terminal=='timeout' else asyncio.CancelledError):await task
        await asyncio.wait_for(finished.wait(),.2)
        record=(await service.history(cid))['runs'][0]
        assert record['state']==('timed_out' if terminal=='timeout' else 'cancelled')
        assert record['attempts'][0]['state']==record['state'] and '晚到值' not in json.dumps(record,ensure_ascii=False)
    asyncio.run(run())


def test_sqlite_ledger_reopen_duplicate_and_no_body(tmp_path):
    async def run():
        store,service=await stored(tmp_path);cid=str(uuid4());bid=str(uuid4());calls=[]
        async def once():calls.append(1);return {'secret':'合成输出不得持久化'}
        try:
            await service.run('context.sqlite_read',{'query':'合成输入不得持久化'},once,deadline=monotonic()+1,cid=cid,business_id=bid)
            reopened=RetryService(store);await reopened.open()
            with pytest.raises(RetryError) as caught:await reopened.run('context.sqlite_read',{'query':'合成输入不得持久化'},once,deadline=monotonic()+1,cid=cid,business_id=bid)
            assert caught.value.code=='RETRY_TERMINAL' and len(calls)==1
            body=json.dumps(await reopened.history(cid),ensure_ascii=False)
            assert '合成输入' not in body and '合成输出' not in body
            assert (await reopened.history(str(uuid4())))['runs']==[]
        finally:await store.close()
    asyncio.run(run())


def test_contextvars_multiple_calls_and_concurrent_cids(tmp_path):
    async def run():
        store,service=await stored(tmp_path);cids=[str(uuid4()),str(uuid4())]
        async def invoke(cid):
            with service.activate(cid,'parent-id'):
                for _ in range(2):
                    async def read():await asyncio.sleep(.01);return cid
                    assert await service.run('context.sqlite_read',{'query':'同查询'},read,deadline=monotonic()+1)==cid
        try:
            await asyncio.gather(*(invoke(cid) for cid in cids))
            records=[(await service.history(cid))['runs'] for cid in cids]
            assert all(len(rows)==2 and len({r['business_id'] for r in rows})==2 for rows in records)
            assert {r['business_id'] for r in records[0]}=={r['business_id'] for r in records[1]},'业务identity只在cid内唯一'
        finally:await store.close()
    asyncio.run(run())


def test_startup_marks_running_interrupted_without_callback(tmp_path):
    async def run():
        store,service=await stored(tmp_path);cid=str(uuid4());bid=str(uuid4())
        try:
            async with store._lock:
                await store._db().execute('INSERT INTO retry_runs VALUES(?,?,?,?,?,?,?)',(cid,bid,'context.sqlite_read','a'*64,'running','2026-10-08T00:00:00+00:00',None))
                await store._db().execute('INSERT INTO retry_attempts VALUES(?,?,?,?,?,?,?,?,?)',(cid,bid,1,'running','2026-10-08T00:00:00+00:00',None,'initial',0,None))
            await service.open();record=(await service.history(cid))['runs'][0]
            assert record['state']=='interrupted' and record['attempts'][0]['reason']=='interrupted'
        finally:await store.close()
    asyncio.run(run())


def test_deleted_chat_rejects_history_and_late_write(tmp_path):
    async def run():
        store,service=await stored(tmp_path);cid=str(uuid4());entered=asyncio.Event();release=asyncio.Event()
        try:
            async with store._lock:
                await store._db().execute('CREATE TABLE chat_conversations(id TEXT PRIMARY KEY)')
                await store._db().execute('CREATE TABLE chat_deletions(id TEXT PRIMARY KEY)')
                await store._db().execute('INSERT INTO chat_conversations VALUES(?)',(cid,))
            async def read():entered.set();await release.wait();return '不应重建'
            task=asyncio.create_task(service.run('context.sqlite_read',{},read,deadline=monotonic()+1,cid=cid))
            await entered.wait()
            async with store._lock:
                db=store._db();await db.execute('INSERT INTO chat_deletions VALUES(?)',(cid,))
                await db.execute('DELETE FROM retry_attempts WHERE cid=?',(cid,));await db.execute('DELETE FROM retry_runs WHERE cid=?',(cid,))
            release.set()
            with pytest.raises(RetryError):await task
            with pytest.raises(RetryError):await service.history(cid)
            async with store._lock:
                async with store._db().execute('SELECT count(*) FROM retry_runs') as cursor:assert (await cursor.fetchone())[0]==0
        finally:await store.close()
    asyncio.run(run())


def test_total_deadline_includes_execution_and_backoff():
    async def run():
        service=RetryService();cid=str(uuid4());calls=[];started=monotonic()
        async def fail():calls.append(1);await asyncio.sleep(.06);raise httpx.ConnectError('synthetic')
        with pytest.raises(httpx.ConnectError):await service.run('browser.static_read',{},fail,deadline=started+.15,cid=cid)
        assert len(calls)==1 and monotonic()-started<.25
        assert (await service.history(cid))['runs'][0]['attempts'][0]['reason']=='budget_exhausted'
    asyncio.run(run())


def test_close_waits_sqlite_receipt_before_store_shutdown(tmp_path):
    async def run():
        store,service=await stored(tmp_path);cid=str(uuid4());entered=asyncio.Event()
        async def wait():entered.set();await asyncio.sleep(10)
        task=asyncio.create_task(service.run('context.sqlite_read',{},wait,deadline=monotonic()+20,cid=cid))
        try:
            await entered.wait();await service.close()
            assert not service._active and not service._settled
            assert (await service.history(cid))['runs'][0]['state']=='cancelled'
            await store.close()
            with pytest.raises(asyncio.CancelledError):await task
        finally:await store.close()
    asyncio.run(run())


def test_forget_only_selected_cid_and_independent_mission_allowed(tmp_path):
    async def run():
        store,service=await stored(tmp_path);cid=str(uuid4());other=str(uuid4())
        try:
            async with store._lock:
                db=store._db();await db.execute('CREATE TABLE chat_conversations(id TEXT PRIMARY KEY)');await db.execute('CREATE TABLE chat_deletions(id TEXT PRIMARY KEY)')
                await db.execute('INSERT INTO missions VALUES(?,?,?,?,?,?)',(cid,str(uuid4()),'合成独立Mission','draft','2026-10-08T00:00:00+00:00','{}'))
                await db.execute('INSERT INTO chat_conversations VALUES(?)',(other,))
            async def read():return '合成只读'
            for identity in (cid,other):assert await service.run('context.sqlite_read',{},read,deadline=monotonic()+1,cid=identity)=='合成只读'
            await service.forget(cid)
            assert not any(key[0]==cid for key in service._runs) and any(key[0]==other for key in service._runs)
            assert (await service.history(cid))['runs'][0]['state']=='succeeded','forget不代替SQLite所属业务删除事务'
        finally:await store.close()
    asyncio.run(run())


def test_duplicate_concurrent_callback_once_even_initial_sqlite_wait(tmp_path):
    async def run():
        store,service=await stored(tmp_path);cid=str(uuid4());bid=str(uuid4());calls=[]
        async def read():calls.append(1);await asyncio.sleep(.03);return '一次'
        try:
            await store._lock.acquire()
            first=asyncio.create_task(service.run('context.sqlite_read',{},read,deadline=monotonic()+1,cid=cid,business_id=bid))
            await asyncio.sleep(.01)
            with pytest.raises(RetryError):await service.run('context.sqlite_read',{},read,deadline=monotonic()+1,cid=cid,business_id=bid)
            store._lock.release()
            assert await first=='一次' and calls==[1]
        finally:
            if store._lock.locked():store._lock.release()
            await store.close()
    asyncio.run(run())


def test_blocking_callback_completed_after_deadline_is_not_success():
    async def run():
        service=RetryService();cid=str(uuid4())
        async def blocked():time.sleep(.07);return '超deadline值'
        with pytest.raises(TimeoutError):await service.run('context.sqlite_read',{},blocked,deadline=monotonic()+.02,cid=cid)
        record=(await service.history(cid))['runs'][0]
        assert record['state']=='timed_out' and record['attempts'][0]['state']=='timed_out'
    asyncio.run(run())


@pytest.mark.parametrize('boundary',['deadline','cancel'])
def test_success_receipt_wait_cannot_return_after_deadline_or_cancel(tmp_path,boundary,monkeypatch):
    async def run():
        store,service=await stored(tmp_path);cid=str(uuid4());event=asyncio.Event();original=service._save
        async def delayed(identity,record,**kwargs):
            await original(identity,record,**kwargs)
            if record['state']=='succeeded':
                if boundary=='cancel':event.set()
                else:await asyncio.sleep(.09)
        monkeypatch.setattr(service,'_save',delayed)
        async def read():return '不应交回'
        try:
            with pytest.raises(TimeoutError if boundary=='deadline' else asyncio.CancelledError):
                await service.run('context.sqlite_read',{},read,deadline=monotonic()+(.04 if boundary=='deadline' else 1),cid=cid,cancel_event=event)
            record=(await service.history(cid))['runs'][0]
            assert record['state']==('timed_out' if boundary=='deadline' else 'cancelled')
            assert record['attempts'][0]['state']==record['state']
            assert not await service.has_unresolved(cid)
        finally:await store.close()
    asyncio.run(run())


@pytest.mark.parametrize('stop',['close','task_cancel'])
def test_initial_pending_ledger_is_settled_before_shutdown(tmp_path,stop):
    async def run():
        store,service=await stored(tmp_path);cid=str(uuid4());calls=[]
        async def read():calls.append(1);return '不能开始'
        try:
            await store._lock.acquire()
            task=asyncio.create_task(service.run('context.sqlite_read',{},read,deadline=monotonic()+1,cid=cid))
            await asyncio.sleep(.01)
            assert await service.has_unresolved(cid)
            if stop=='close':
                closing=asyncio.create_task(service.close());await asyncio.sleep(.01);assert not closing.done()
            else:task.cancel()
            store._lock.release()
            if stop=='close':await closing
            with pytest.raises(asyncio.CancelledError):await task
            assert calls==[] and not await service.has_unresolved(cid)
            assert (await service.history(cid))['runs'][0]['state']=='cancelled'
            await store.close();assert not service._active and not service._settled
        finally:
            if store._lock.locked():store._lock.release()
            await store.close()
    asyncio.run(run())


def test_task_cancel_during_final_sqlite_save_reconciles_cancelled(tmp_path,monkeypatch):
    async def run():
        store,service=await stored(tmp_path);cid=str(uuid4());saved=asyncio.Event();original=service._save
        async def paused(identity,record,**kwargs):
            await original(identity,record,**kwargs)
            if record['state']=='succeeded':saved.set();await asyncio.sleep(10)
        monkeypatch.setattr(service,'_save',paused)
        async def read():return '取消后不得交回'
        try:
            task=asyncio.create_task(service.run('context.sqlite_read',{},read,deadline=monotonic()+1,cid=cid))
            await saved.wait();task.cancel()
            with pytest.raises(asyncio.CancelledError):await task
            record=(await service.history(cid))['runs'][0]
            assert record['state']=='cancelled' and record['attempts'][0]['state']=='cancelled'
            assert not await service.has_unresolved(cid)
        finally:await store.close()
    asyncio.run(run())


def test_initial_storage_wait_consumes_deadline_without_callback(tmp_path):
    async def run():
        store,service=await stored(tmp_path);cid=str(uuid4());calls=[]
        async def read():calls.append(1)
        try:
            await store._lock.acquire()
            task=asyncio.create_task(service.run('context.sqlite_read',{},read,deadline=monotonic()+.02,cid=cid))
            await asyncio.sleep(.05);store._lock.release()
            with pytest.raises(TimeoutError):await task
            assert calls==[] and (await service.history(cid))['runs'][0]['state']=='timed_out'
        finally:
            if store._lock.locked():store._lock.release()
            await store.close()
    asyncio.run(run())


def test_history_display_limit_does_not_allow_old_business_replay(tmp_path):
    async def run():
        store,service=await stored(tmp_path);cid=str(uuid4());bids=[str(uuid4()) for _ in range(35)];calls=[]
        async def read():calls.append(1);return '合成值'
        try:
            for bid in bids:await service.run('context.sqlite_read',{},read,deadline=monotonic()+1,cid=cid,business_id=bid)
            history=await service.history(cid)
            assert len(history['runs'])==32 and history['truncated'] and len(json.dumps(history).encode())<=32768
            assert bids[0] not in [r['business_id'] for r in history['runs']]
            reopened=RetryService(store);await reopened.open()
            with pytest.raises(RetryError):await reopened.run('context.sqlite_read',{},read,deadline=monotonic()+1,cid=cid,business_id=bids[0])
            assert len(calls)==35 and not await reopened.has_unresolved(cid)
        finally:await store.close()
    asyncio.run(run())
