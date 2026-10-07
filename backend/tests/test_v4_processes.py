"""V4-009临时SQLite/合成目标；默认不调用模型或用户真实应用。"""

import asyncio
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
from uuid import uuid4

import pytest

from orvia_backend.processes import ProcessService, ProcessError
from orvia_backend.computer.paths import ToolError
from orvia_backend.memory.service import size
from test_chat import setup,create
from test_v4_process_native import private_python,ready


class Native:
    def __init__(self,path):
        self.path=Path(path)
        self.target={'pid':4242,'create_time':1728000000.125,'creation_ticks':'133000000001250000','name':self.path.name,'executable':str(self.path),'sha256':hashlib.sha256(self.path.read_bytes()).hexdigest()}
        self.calls=[]
        self.callback=None
        self.failure=None
        self.state='running'
        self.entered,self.release=threading.Event(),threading.Event()
        self.block=False
        self.inspect_failure=None
        self.restored=[]

    def executable(self,path):
        return {'name':Path(path).name,'executable':str(Path(path)),'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest()}

    def inspect(self,pid,create_time=None,creation_ticks=None):
        if self.inspect_failure:raise ToolError(self.inspect_failure,'合成安全拒绝')
        if pid!=self.target['pid'] or create_time!=self.target['create_time'] or creation_ticks!=self.target['creation_ticks']:
            raise ToolError('PROCESS_IDENTITY','合成PID已复用')
        return copy.deepcopy(self.target)

    def list(self):
        return {'processes':[copy.deepcopy(self.target)],'truncated':False,'unavailable_reason':None}

    def restore_launched(self,identity):
        if identity!=self.target or identity['sha256']!=self.executable(identity['executable'])['sha256']:
            raise ToolError('PROCESS_CHANGED','合成旧启动身份变化')
        self.restored.append(copy.deepcopy(identity))
        self.inspect_failure=None
        return copy.deepcopy(identity)

    def _operation(self,action):
        self.calls.append(action)
        self.entered.set()
        if self.block:self.release.wait(10)
        if self.callback:self.callback()
        if self.failure:raise ToolError(self.failure,'合成原生操作拒绝')
        state='exited' if action=='terminate' else self.state
        return {'identity':copy.deepcopy(self.target),'state':state,'exit_code':7 if state=='exited' else None,'close_sent':action=='close'}

    def launch(self,path,args,cwd,wait_seconds=0,*,sha256=None):
        self.launch_args=(path,args,cwd,wait_seconds,sha256)
        return self._operation('launch')

    def wait(self,identity,wait_seconds=2):return self._operation('wait')
    def close(self,identity,wait_seconds=2):return self._operation('close')
    def terminate(self,identity,wait_seconds=2):return self._operation('terminate')


async def prepare(tmp_path):
    app=await setup(tmp_path)
    cid=(await create(app))['id']
    exe=tmp_path/'合成 程序.exe';exe.write_bytes(b'synthetic executable bytes')
    n=Native(exe)
    s=ProcessService(app.store,app.chat,app.computer,n)
    await s.open()
    return app,s,cid,n,exe


async def action(s,cid,n,kind='wait'):
    t=n.target
    return await s.preview_action(cid,kind,t['pid'],t['create_time'],t['creation_ticks'])


def test_sqlite_launch_freezes_exact_args_cwd_consumes_before_native_no_replay(tmp_path):
    async def run():
        app,s,cid,n,exe=await prepare(tmp_path)
        cwd=tmp_path/'合成 空格cwd';cwd.mkdir()
        try:
            p=await s.preview_launch(cid,str(exe),['合成 空格参数','--count=1'],str(cwd))
            assert n.calls==[] and await s.review(cid,p['operation_id'])==p
            def check():
                with sqlite3.connect(app.store.path) as db:
                    assert db.execute('SELECT state FROM process_attempts WHERE cid=? AND operation_id=?',(cid,p['operation_id'])).fetchone()==('running',)
            n.callback=check
            result=await s.execute(cid,p['operation_id'],p['revision'])
            assert result['status']=='still_running' and result['verified'] and not result['close_sent']
            assert n.launch_args==(str(exe),['合成 空格参数','--count=1'],str(cwd),3,p['launch']['sha256'])
            s._previews.clear()
            with pytest.raises(ProcessError,match='PROCESS_ALREADY_ATTEMPTED'):
                await s.execute(cid,p['operation_id'],p['revision'])
            assert not await s.has_unresolved(cid) and (await s.history(cid))['executions']==[result]
            await s.close()
            assert n.calls==['launch'],'Orvia关闭不能自动终止已启动程序'
        finally:
            await s.close();await app.close()
    asyncio.run(run())


def test_close_still_running_requires_distinct_terminate_approval_and_wait_is_observation(tmp_path):
    async def run():
        app,s,cid,n,exe=await prepare(tmp_path)
        try:
            p=await action(s,cid,n,'close')
            result=await s.execute(cid,p['operation_id'],p['revision'])
            assert result['status']=='still_running' and result['close_sent'] and n.calls==['close']
            wait=await action(s,cid,n)
            assert (await s.execute(cid,wait['operation_id'],wait['revision']))['status']=='still_running'
            assert n.calls==['close','wait']
            term=await action(s,cid,n,'terminate')
            assert term['operation_id']!=p['operation_id'] and '丢失未保存' in term['risk']
            result=await s.execute(cid,term['operation_id'],term['revision'])
            assert result['status']=='exited' and result['verified'] and result['exit_code']==7 and n.calls==['close','wait','terminate']
        finally:
            await s.close();await app.close()
    asyncio.run(run())


@pytest.mark.parametrize('changes',[{'args':['a']*17},{'args':['x'*1001]},{'args':['a\x00b']},{'args':['--api_key=synthetic']},{'args':'text'},{'wait_seconds':0},{'wait_seconds':16},{'wait_seconds':True}])
def test_launch_input_budget_and_sensitive_args_rejected_without_native_action(tmp_path,changes):
    async def run():
        app,s,cid,n,exe=await prepare(tmp_path)
        try:
            args={'cid':cid,'executable':str(exe),'args':[]};args.update(changes)
            with pytest.raises(ToolError):await s.preview_launch(**args)
            assert n.calls==[]
        finally:
            await s.close();await app.close()
    asyncio.run(run())


@pytest.mark.parametrize('denied',['PROCESS_TOKEN','PROCESS_USER','PROCESS_CRITICAL','PROCESS_PROTECTED','PROCESS_ELEVATED','PROCESS_UNAVAILABLE'])
def test_target_permission_denial_never_prepares_or_executes(tmp_path,denied):
    async def run():
        app,s,cid,n,exe=await prepare(tmp_path)
        try:
            n.inspect_failure=denied
            with pytest.raises(ToolError,match=denied):await action(s,cid,n,'terminate')
            assert not s._previews and n.calls==[]
        finally:
            await s.close();await app.close()
    asyncio.run(run())


def test_pid_reuse_exe_bytes_cwd_replacement_and_wrong_session_old_revision_refused(tmp_path):
    async def run():
        app,s,cid,n,exe=await prepare(tmp_path)
        cwd=tmp_path/'cwd';cwd.mkdir()
        try:
            target=await action(s,cid,n)
            n.target['creation_ticks']='133000000001250001'
            with pytest.raises(ToolError,match='PROCESS_IDENTITY'):
                await s.execute(cid,target['operation_id'],target['revision'])
            p=await s.preview_launch(cid,str(exe),[],str(cwd))
            other=(await create(app))['id']
            with pytest.raises(ProcessError,match='PROCESS_REVIEW'):
                await s.execute(other,p['operation_id'],p['revision'])
            with pytest.raises(ProcessError,match='PROCESS_REVIEW'):
                await s.execute(cid,p['operation_id'],'0'*64)
            exe.write_bytes(b'changed executable')
            with pytest.raises(ProcessError,match='PROCESS_IDENTITY_CHANGED'):
                await s.review(cid,p['operation_id'])
            exe.write_bytes(b'synthetic executable bytes')
            cwd.rename(tmp_path/'oldcwd');cwd.mkdir()
            with pytest.raises(ToolError):await s.execute(cid,p['operation_id'],p['revision'])
            assert n.calls==[]
        finally:
            await s.close();await app.close()
    asyncio.run(run())


@pytest.mark.parametrize('failure,expected',[('PROCESS_CHANGED','failed'),('PROCESS_USER','failed'),('PROCESS_UNKNOWN','unknown')])
def test_final_native_guard_failure_is_consumed_and_unknown_not_retried(tmp_path,failure,expected):
    async def run():
        app,s,cid,n,exe=await prepare(tmp_path)
        try:
            p=await s.preview_launch(cid,str(exe),[])
            n.failure=failure
            result=await s.execute(cid,p['operation_id'],p['revision'])
            assert result['status']==expected and not result['verified'] and await s.has_unresolved(cid)==(expected=='unknown')
            with pytest.raises(ProcessError,match='PROCESS_ALREADY_ATTEMPTED'):
                await s.execute(cid,p['operation_id'],p['revision'])
            assert n.calls==['launch']
        finally:
            await s.close();await app.close()
    asyncio.run(run())


def test_late_tombstone_and_purged_attempt_cannot_restore_execution_body(tmp_path):
    async def run():
        app,s,cid,n,exe=await prepare(tmp_path)
        try:
            p=await s.preview_launch(cid,str(exe),[])
            def erase():
                with sqlite3.connect(app.store.path) as db:
                    db.execute("INSERT INTO chat_deletions VALUES(?,'pending')",(cid,))
                    db.execute('DELETE FROM process_attempts WHERE cid=?',(cid,))
                    db.execute('DELETE FROM process_executions WHERE cid=?',(cid,))
            n.callback=erase
            with pytest.raises(ProcessError,match='PROCESS_CONVERSATION'):
                await s.execute(cid,p['operation_id'],p['revision'])
            async with app.store._lock:
                assert not await s._rows(app.store._db(),'SELECT 1 FROM process_executions WHERE cid=?',(cid,))
        finally:
            await s.close();await app.close()
    asyncio.run(run())


def test_startup_unknown_history_cache_and_128_attempt_cap(tmp_path):
    async def run():
        app,s,cid,n,exe=await prepare(tmp_path)
        try:
            p=await s.preview_launch(cid,str(exe),[])
            value=s._blank(p)
            async with app.store._lock:
                db=app.store._db()
                await db.execute('INSERT INTO process_attempts VALUES(?,?,?,?)',(cid,p['operation_id'],p['revision'],'running'))
                await db.execute('INSERT INTO process_executions VALUES(?,?,?)',(cid,p['operation_id'],json.dumps(value)))
            await s.open()
            assert (await s.status(cid,p['operation_id']))['status']=='unknown' and await s.has_unresolved(cid) and not n.calls
            with pytest.raises(ProcessError,match='PROCESS_ALREADY_ATTEMPTED'):
                await s.execute(cid,p['operation_id'],p['revision'])
            async with app.store._lock:
                for _ in range(127):
                    await app.store._db().execute('INSERT INTO process_attempts VALUES(?,?,?,?)',(cid,str(uuid4()),'1'*64,'exited'))
            new=await s.preview_launch(cid,str(exe),[])
            with pytest.raises(ProcessError,match='PROCESS_ATTEMPT_LIMIT'):
                await s.execute(cid,new['operation_id'],new['revision'])
            assert n.calls==[]
        finally:
            await s.close();await app.close()
    asyncio.run(run())


def test_repeated_communication_cancel_does_not_discard_native_thread_or_kill_target(tmp_path):
    async def run():
        app,s,cid,n,exe=await prepare(tmp_path)
        try:
            p=await s.preview_launch(cid,str(exe),[])
            n.block=True
            task=asyncio.create_task(s.execute(cid,p['operation_id'],p['revision']))
            assert await asyncio.to_thread(n.entered.wait,3)
            task.cancel();await asyncio.sleep(.05);task.cancel();await asyncio.sleep(.05)
            assert not task.done() and await s.has_unresolved(cid)
            n.release.set()
            with pytest.raises(asyncio.CancelledError):await task
            value=await s.status(cid,p['operation_id'])
            assert value['status']=='unknown' and value['target']==n.target and n.calls==['launch'] and not s._pending
            await s.close()
            assert n.calls==['launch']
        finally:
            n.release.set();await s.close();await app.close()
    asyncio.run(run())


def test_list_budget_history_eviction_preserves_attempts_and_preview_cap(tmp_path):
    async def run():
        app,s,cid,n,exe=await prepare(tmp_path)
        try:
            for _ in range(21):await s.preview_launch(cid,str(exe),[])
            assert len(s._previews)==20 and (await s.list(cid))['processes']==[n.target]
            first=None
            for _ in range(34):
                p=await action(s,cid,n)
                await s.execute(cid,p['operation_id'],p['revision'])
                first=first or p
            result=await s.history(cid)
            assert len(result['executions'])==10 and result['truncated'] and size(result)<=49152
            async with app.store._lock:
                db=app.store._db()
                assert (await s._rows(db,'SELECT count(*) FROM process_attempts WHERE cid=?',(cid,)))[0][0]==34
                assert (await s._rows(db,'SELECT count(*) FROM process_executions WHERE cid=?',(cid,)))[0][0]==32
            with pytest.raises(ProcessError,match='PROCESS_ALREADY_ATTEMPTED'):
                await s.execute(cid,first['operation_id'],first['revision'])
        finally:
            await s.close();await app.close()
    asyncio.run(run())


@pytest.mark.parametrize('mode',['exit','wait','window-ignore'])
def test_real_service_native_exact_launch_wait_close_and_separate_terminate(private_python,tmp_path,mode):
    async def run():
        from orvia_backend.processes import native
        import psutil
        app=await setup(tmp_path)
        cid=(await create(app))['id']
        s=ProcessService(app.store,app.chat,app.computer)
        await s.open()
        marker=tmp_path/'合成 marker 空格.json'
        cwd=tmp_path/'合成 cwd 空格';cwd.mkdir()
        fixture=Path(__file__).with_name('v4_process_fixture.py').resolve()
        target=None
        try:
            if mode=='wait':
                code="import os,time,json;from pathlib import Path;Path("+repr(str(marker))+").write_text(json.dumps({'pid':os.getpid(),'ready':True}),encoding='utf-8');time.sleep(3);raise SystemExit(9)"
                args=['-I','-u','-c',code]
            else:
                args=['-I','-u',str(fixture),mode,str(marker)] + (['7'] if mode=='exit' else [])
            p=await s.preview_launch(cid,str(private_python),args,str(cwd),wait_seconds=1)
            assert await s.review(cid,p['operation_id'])==p
            result=await s.execute(cid,p['operation_id'],p['revision'])
            target=result['target']
            observed=await asyncio.to_thread(ready,marker)
            assert observed['pid']==target['pid'] and observed['ready']
            assert result['verified'] and target['executable']==str(private_python) and target['sha256']==p['launch']['sha256']
            if mode=='exit':
                assert result['status']=='exited' and result['exit_code']==7
            else:
                assert result['status']=='still_running' and psutil.pid_exists(target['pid'])
                kind='wait' if mode=='wait' else 'close'
                q=await s.preview_action(cid,kind,target['pid'],target['create_time'],target['creation_ticks'],wait_seconds=3 if mode=='wait' else 1)
                result=await s.execute(cid,q['operation_id'],q['revision'])
                if mode=='wait':
                    assert result['status']=='exited' and result['exit_code']==9 and not result['close_sent']
                else:
                    assert result['status']=='still_running' and result['close_sent'] and psutil.pid_exists(target['pid'])
                    with pytest.raises(ProcessError,match='PROCESS_ALREADY_ATTEMPTED'):
                        await s.execute(cid,q['operation_id'],q['revision'])
                    term=await s.preview_action(cid,'terminate',target['pid'],target['create_time'],target['creation_ticks'],wait_seconds=2)
                    result=await s.execute(cid,term['operation_id'],term['revision'])
                    assert result['status']=='exited' and result['verified'] and result['exit_code']==0xE009
            assert not await s.has_unresolved(cid)
            assert len((await s.history(cid))['executions'])==(1 if mode=='exit' else 2 if mode=='wait' else 3)
        finally:
            if target is not None:
                try:
                    await asyncio.to_thread(native.terminate,target,2)
                except ToolError as exc:
                    if exc.code not in {'PROCESS_UNAVAILABLE','PROCESS_IDENTITY','PROCESS_CHANGED'}:
                        raise
            await s.close();await app.close()
    asyncio.run(run())


def test_revocation_during_review_to_consume_prevents_native_action(tmp_path):
    async def run():
        app,s,cid,n,exe=await prepare(tmp_path)
        original=s.review
        try:
            p=await s.preview_launch(cid,str(exe),[])
            async def revoked(owner,oid):
                packet=await original(owner,oid)
                s.forget_previews(owner)
                return packet
            s.review=revoked
            with pytest.raises(ProcessError,match='PROCESS_REVIEW'):
                await s.execute(cid,p['operation_id'],p['revision'])
            assert n.calls==[]
            async with app.store._lock:
                assert not await s._rows(app.store._db(),'SELECT 1 FROM process_attempts WHERE cid=?',(cid,))
        finally:
            await s.close();await app.close()
    asyncio.run(run())


@pytest.mark.parametrize('reason',['PROCESS_JOB','PROCESS_KEY'])
def test_only_current_verified_launch_fact_restores_lost_native_registry_for_new_approval(tmp_path,reason):
    async def run():
        app,s,cid,n,exe=await prepare(tmp_path)
        try:
            p=await s.preview_launch(cid,str(exe),[])
            result=await s.execute(cid,p['operation_id'],p['revision'])
            await s.open()
            n.inspect_failure=reason
            next_packet=await action(s,cid,n)
            assert n.restored==[result['target']] and n.calls==['launch']
            assert next_packet['operation_id']!=p['operation_id']
            value=await s.execute(cid,next_packet['operation_id'],next_packet['revision'])
            assert value['status']=='still_running' and n.calls==['launch','wait']
            with pytest.raises(ProcessError,match='PROCESS_ALREADY_ATTEMPTED'):
                await s.execute(cid,p['operation_id'],p['revision'])
        finally:
            await s.close();await app.close()
    asyncio.run(run())


@pytest.mark.parametrize('case',['unknown','unverified','cross_cid','changed_ticks','forged_pid','body_evicted','changed_exe'])
def test_unknown_cross_scope_changed_or_missing_launch_fact_cannot_restore_job_qualification(tmp_path,case):
    async def run():
        app,s,cid,n,exe=await prepare(tmp_path)
        try:
            p=await s.preview_launch(cid,str(exe),[])
            await s.execute(cid,p['operation_id'],p['revision'])
            owner=cid;t=copy.deepcopy(n.target)
            if case=='unknown':
                async with app.store._lock:
                    await app.store._db().execute("UPDATE process_executions SET data_json=json_set(data_json,'$.status','unknown') WHERE cid=?",(cid,))
            if case=='unverified':
                async with app.store._lock:
                    await app.store._db().execute("UPDATE process_executions SET data_json=json_set(data_json,'$.verified',json('false')) WHERE cid=?",(cid,))
            if case=='cross_cid':owner=(await create(app))['id']
            if case=='changed_ticks':t['creation_ticks']='133000000001250001'
            if case=='forged_pid':t['pid']+=1
            if case=='body_evicted':
                async with app.store._lock:
                    await app.store._db().execute('DELETE FROM process_executions WHERE cid=?',(cid,))
            if case=='changed_exe':exe.write_bytes(b'mutated executable')
            n.inspect_failure='PROCESS_JOB'
            with pytest.raises(ToolError):
                await s.preview_action(owner,'terminate',t['pid'],t['create_time'],t['creation_ticks'])
            assert n.restored==[] and n.calls==['launch']
        finally:
            await s.close();await app.close()
    asyncio.run(run())


def test_real_service_restart_native_registry_restoration_requires_new_approved_action(private_python,tmp_path):
    async def run():
        from orvia_backend.processes import native
        app=await setup(tmp_path)
        cid=(await create(app))['id']
        s=ProcessService(app.store,app.chat,app.computer)
        await s.open()
        fixture=Path(__file__).with_name('v4_process_fixture.py').resolve()
        marker=tmp_path/'restart-marker.json'
        target=None
        try:
            p=await s.preview_launch(cid,str(private_python),['-I','-u',str(fixture),'sleep',str(marker)],str(tmp_path),1)
            value=await s.execute(cid,p['operation_id'],p['revision'])
            target=value['target']
            assert value['status']=='still_running' and (await asyncio.to_thread(ready,marker))['pid']==target['pid']
            with native._lock:
                native._owned.discard((target['pid'],target['creation_ticks']))
            with pytest.raises(ToolError):
                await asyncio.to_thread(native.inspect,target['pid'],target['create_time'],target['creation_ticks'])
            rebuilt=ProcessService(app.store,app.chat,app.computer)
            await rebuilt.open()
            q=await rebuilt.preview_action(cid,'terminate',target['pid'],target['create_time'],target['creation_ticks'],2)
            assert (target['pid'],target['creation_ticks']) in native._owned
            assert (await rebuilt.status(cid,p['operation_id']))['status']=='still_running'
            value=await rebuilt.execute(cid,q['operation_id'],q['revision'])
            assert value['status']=='exited' and value['verified'] and value['exit_code']==0xE009
        finally:
            if target:
                try:await asyncio.to_thread(native.terminate,target,2)
                except ToolError as exc:
                    if exc.code not in {'PROCESS_UNAVAILABLE','PROCESS_IDENTITY','PROCESS_CHANGED'}:raise
            await s.close();await app.close()
    asyncio.run(run())
