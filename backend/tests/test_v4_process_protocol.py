"""V4-009固定协议、实际自有合成程序和会话生命周期；零模型调用。"""
import asyncio
import io
import json
from pathlib import Path
import sys
from uuid import uuid4

import psutil
import pytest

from test_chat import setup, create, call


async def result(app,method,params=None):
    response=await call(app,method,params)
    assert response['ok'],response
    return response['result']


def test_process_private_protocol_rejects_authority_paths_and_missing_precise_identity(tmp_path):
    async def run():
        app=await setup(tmp_path)
        try:
            cid=(await create(app))['id'];oid=str(uuid4())
            invalid=[('process.list',{'id':cid,'env':{}}),('process.preview_launch',{'id':cid,'executable':sys.executable,'args':[],'approved':True}),('process.preview_launch',{'id':cid,'executable':sys.executable,'args':[],'wait_seconds':True}),('process.preview_action',{'id':cid,'pid':123,'create_time':1.0,'action':'terminate'}),('process.preview_action',{'id':cid,'pid':123,'create_time':True,'creation_ticks':'123','action':'wait'}),('process.preview_action',{'id':cid,'pid':123,'create_time':1.0,'creation_ticks':'123','action':'kill_tree'}),('process.execute',{'id':cid,'operation_id':oid,'revision':'1'*64,'model':'other'})]
            for method,params in invalid:
                response=await call(app,method,params)
                assert not response['ok'] and response['error']['code']=='INVALID_PARAMS'
            assert (await result(app,'process.history',{'id':cid}))['executions']==[]
        finally:await app.close()
    asyncio.run(run())


def test_real_process_launch_close_still_running_separate_terminate_and_purge(tmp_path):
    """只终止本用例新批准启动的合成程序，不枚举/结束用户既有应用。"""
    async def run():
        app=await setup(tmp_path);target=None
        work=tmp_path/'合成 工作目录';work.mkdir();marker=work/'合成启动.txt'
        try:
            cid=(await create(app))['id']
            args=['-I','-c',"import pathlib,time;pathlib.Path('合成启动.txt').write_text('合成普通进程',encoding='utf-8');time.sleep(60)"]
            packet=await result(app,'process.preview_launch',{'id':cid,'executable':sys._base_executable,'args':args,'cwd':str(work),'wait_seconds':1})
            assert packet['launch']['args']==args and not marker.exists()
            assert await result(app,'process.review',{'id':cid,'operation_id':packet['operation_id']})==packet
            launched=await result(app,'process.execute',{'id':cid,'operation_id':packet['operation_id'],'revision':packet['revision']})
            assert launched['status']=='still_running' and launched['verified']
            target=launched['target'];assert psutil.pid_exists(target['pid']) and marker.read_text(encoding='utf-8')=='合成普通进程'
            assert not (await call(app,'process.execute',{'id':cid,'operation_id':packet['operation_id'],'revision':packet['revision']}))['ok']
            request={'id':cid,'pid':target['pid'],'create_time':target['create_time'],'creation_ticks':target['creation_ticks'],'wait_seconds':1}
            changed=await call(app,'process.preview_action',{**request,'action':'terminate','creation_ticks':str(int(target['creation_ticks'])+1)})
            assert not changed['ok'] and psutil.pid_exists(target['pid'])
            gentle=await result(app,'process.preview_action',{**request,'action':'close'})
            close=await result(app,'process.execute',{'id':cid,'operation_id':gentle['operation_id'],'revision':gentle['revision']})
            assert close['status']=='still_running' and close['verified'] and not close['close_sent']
            assert psutil.pid_exists(target['pid'])
            terminate=await result(app,'process.preview_action',{**request,'action':'terminate'})
            ended=await result(app,'process.execute',{'id':cid,'operation_id':terminate['operation_id'],'revision':terminate['revision']})
            assert ended['status']=='exited' and ended['verified']
            for _ in range(100):
                if not psutil.pid_exists(target['pid']):break
                await asyncio.sleep(.02)
            assert not psutil.pid_exists(target['pid'])
            assert len((await result(app,'process.history',{'id':cid}))['executions'])==3
            await result(app,'chat.delete',{'id':cid});assert marker.exists()
            async with app.store._lock:
                for table in ('process_attempts','process_executions'):
                    async with app.store._db().execute(f'SELECT count(*) FROM {table} WHERE cid=?',(cid,)) as cursor:assert (await cursor.fetchone())[0]==0
        finally:
            # 测试回收仅限本次创建时间仍匹配的合成目标，不按名称或复用PID清理。
            if target:
                try:
                    process=psutil.Process(target['pid'])
                    if process.create_time()==target['create_time']:process.kill();process.wait(3)
                except psutil.Error:pass
            await app.close()
    asyncio.run(run())


def test_real_process_wait_returns_actual_nonzero_exit(tmp_path):
    async def run():
        app=await setup(tmp_path)
        try:
            cid=(await create(app))['id']
            packet=await result(app,'process.preview_launch',{'id':cid,'executable':sys._base_executable,'args':['-I','-c','raise SystemExit(7)'],'wait_seconds':3})
            exited=await result(app,'process.execute',{'id':cid,'operation_id':packet['operation_id'],'revision':packet['revision']})
            assert exited['status']=='exited' and exited['exit_code']==7 and exited['verified']
            assert not exited['close_sent']
        finally:await app.close()
    asyncio.run(run())


def test_real_known_running_process_survives_app_close_and_conversation_purge(tmp_path):
    """删除应用事实不是进程权限；程序保持运行，后续终止须新会话新批准。"""
    async def run():
        app=await setup(tmp_path);target=None
        try:
            cid=(await create(app))['id']
            packet=await result(app,'process.preview_launch',{'id':cid,'executable':sys._base_executable,'args':['-I','-c','import time;time.sleep(60)'],'wait_seconds':1})
            started=await result(app,'process.execute',{'id':cid,'operation_id':packet['operation_id'],'revision':packet['revision']});target=started['target']
            assert started['status']=='still_running'
            await app.close();assert psutil.pid_exists(target['pid'])
            app=await setup(tmp_path)
            assert (await result(app,'process.history',{'id':cid}))['executions']==[started]
            await result(app,'chat.delete',{'id':cid});assert psutil.pid_exists(target['pid'])
            new=(await create(app))['id']
            terminate=await result(app,'process.preview_action',{'id':new,'pid':target['pid'],'create_time':target['create_time'],'creation_ticks':target['creation_ticks'],'action':'terminate','wait_seconds':2})
            ended=await result(app,'process.execute',{'id':new,'operation_id':terminate['operation_id'],'revision':terminate['revision']})
            assert ended['status']=='exited' and ended['verified']
        finally:
            if target:
                try:
                    process=psutil.Process(target['pid'])
                    if process.create_time()==target['create_time']:process.kill();process.wait(3)
                except psutil.Error:pass
            await app.close()
    asyncio.run(run())


def test_process_running_restart_unknown_blocks_delete_and_old_approval(tmp_path):
    async def run():
        app=await setup(tmp_path);cid=(await create(app))['id'];oid=str(uuid4())
        packet={'id':cid,'operation_id':oid,'revision':'1'*64,'action':'launch','target':None}
        value=app.processes._blank(packet)
        async with app.store._lock:
            await app.store._db().execute('INSERT INTO process_attempts VALUES(?,?,?,?)',(cid,oid,'1'*64,'running'))
            await app.store._db().execute('INSERT INTO process_executions VALUES(?,?,?)',(cid,oid,json.dumps(value)))
        await app.close();app=await setup(tmp_path)
        try:
            state=await result(app,'process.status',{'id':cid,'operation_id':oid});assert state['status']=='unknown' and not state['verified']
            assert not (await call(app,'process.execute',{'id':cid,'operation_id':oid,'revision':'1'*64}))['ok']
            deleted=await call(app,'chat.delete',{'id':cid});assert not deleted['ok'] and deleted['error']['code']=='DELETE_BLOCKED'
            assert not app.processes._active
        finally:await app.close()
    asyncio.run(run())


def test_pending_delete_journal_purges_process_facts_on_startup(tmp_path):
    async def run():
        app=await setup(tmp_path);cid=(await create(app))['id'];oid=str(uuid4())
        packet={'id':cid,'operation_id':oid,'revision':'1'*64,'action':'launch','target':None};value=app.processes._blank(packet);value['status']='still_running'
        async with app.store._lock:
            await app.store._db().execute('INSERT INTO process_attempts VALUES(?,?,?,?)',(cid,oid,'1'*64,'still_running'))
            await app.store._db().execute('INSERT INTO process_executions VALUES(?,?,?)',(cid,oid,json.dumps(value)))
            await app.store._db().execute("INSERT INTO chat_deletions VALUES(?,'pending')",(cid,))
        await app.close();app=await setup(tmp_path)
        try:
            assert not (await call(app,'chat.get',{'id':cid}))['ok']
            async with app.store._lock:
                for table in ('process_attempts','process_executions'):
                    async with app.store._db().execute(f'SELECT count(*) FROM {table} WHERE cid=?',(cid,)) as cursor:assert (await cursor.fetchone())[0]==0
        finally:await app.close()
    asyncio.run(run())


@pytest.mark.parametrize('control',['process.list','process.status','process.history'])
def test_private_stdio_process_facts_available_while_waiting(monkeypatch,control):
    """实测serve调度/输出；已有有限等待不能阻塞事实，后续动作仍串行。"""
    from orvia_backend import server
    class ControlledApplication:
        def __init__(self,event_sink):self.started=asyncio.Event();self.observed=asyncio.Event()
        async def handle(self,line):
            request=json.loads(line);method=request['method']
            if method=='process.execute':
                self.started.set();await asyncio.wait_for(self.observed.wait(),1)
            elif method==control:
                await asyncio.wait_for(self.started.wait(),1);self.observed.set()
            elif method=='process.preview_action':assert self.observed.is_set()
            return {'v':1,'id':request['id'],'ok':True,'result':{'method':method}}
        async def close(self):pass
    monkeypatch.setattr(server,'Application',ControlledApplication)
    methods=['process.execute','process.preview_action',control]
    reader=io.BytesIO(b''.join((json.dumps({'v':1,'id':str(uuid4()),'method':m,'params':{}})+'\n').encode() for m in methods));writer=io.BytesIO()
    asyncio.run(server.serve(reader,writer))
    responses=[json.loads(line) for line in writer.getvalue().splitlines()]
    assert len(responses)==3 and all(r['ok'] for r in responses)
    order=[r['result']['method'] for r in responses]
    assert order.index(control)<order.index('process.preview_action')
