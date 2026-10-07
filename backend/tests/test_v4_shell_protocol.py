"""固定Shell IPC和真实解释器/回传/删除集成；只用合成数据，不调用模型。"""
import asyncio
import json
import io
from pathlib import Path
from uuid import uuid4
import pytest
from test_chat import setup, create, call


@pytest.mark.parametrize('control', ['shell.status', 'shell.history', 'shell.cancel'])
def test_private_stdio_shell_controls_do_not_wait_for_long_execution(monkeypatch, control):
    """真实serve调度/输出通道：长执行占普通锁时控制可达，后续写入口仍串行。"""
    from orvia_backend import server

    class ControlledApplication:
        def __init__(self, event_sink):
            self.started = asyncio.Event()
            self.cancelled = asyncio.Event()

        async def handle(self, line):
            request = json.loads(line)
            method = request['method']
            if method == 'shell.execute':
                self.started.set()
                await asyncio.wait_for(self.cancelled.wait(), 1)
            elif method in {'shell.status', 'shell.history', 'shell.cancel'}:
                await asyncio.wait_for(self.started.wait(), 1)
                if method == 'shell.cancel':
                    self.cancelled.set()
            elif method == 'shell.preview':
                assert self.cancelled.is_set(), '准备写入口仍必须等待已有执行结束'
            return {'v': 1, 'id': request['id'], 'ok': True, 'result': {'method': method}}

        async def close(self):
            assert self.cancelled.is_set()

    monkeypatch.setattr(server, 'Application', ControlledApplication)
    methods = ['shell.execute', 'shell.preview', control]
    if control != 'shell.cancel':
        methods.append('shell.cancel')
    frames = [json.dumps({'v': 1, 'id': str(uuid4()), 'method': method, 'params': {}}).encode() + b'\n' for method in methods]
    writer = io.BytesIO()
    asyncio.run(server.serve(io.BytesIO(b''.join(frames)), writer))
    responses = [json.loads(line) for line in writer.getvalue().splitlines()]
    assert len(responses) == len(methods) and all(item['ok'] for item in responses)
    order = [item['result']['method'] for item in responses]
    assert order.index(control) < order.index('shell.preview')


async def result(app,method,params=None):
    response=await call(app,method,params)
    assert response['ok'],response
    return response['result']


def test_shell_protocol_rejects_injected_authority_and_invalid_budget(tmp_path):
    async def run():
        app=await setup(tmp_path)
        try:
            cid=(await create(app))['id'];rid=str(uuid4())
            cases=[('shell.detect',{'path':'arbitrary.exe'}),('shell.preview',{'id':cid,'interpreter_id':'powershell','script':'synthetic','timeout_seconds':True}),('shell.preview',{'id':cid,'interpreter_id':'powershell','script':'synthetic','timeout_seconds':61}),('shell.preview',{'id':cid,'interpreter_id':'powershell','script':'synthetic','env':{}}),('shell.execute',{'id':cid,'run_id':rid,'revision':'0'*64,'approved':True}),('shell.status',{'id':cid,'run_id':rid,'model':'other'}),('shell.export',{'id':cid,'run_id':rid,'revision':'0'*64,'name':'a.txt','path':str(tmp_path/'a.txt'),'data':'injected'})]
            for method,params in cases:
                denied=await call(app,method,params)
                assert not denied['ok'] and denied['error']['code']=='INVALID_PARAMS'
            assert (await result(app,'shell.history',{'id':cid}))['executions']==[]
        finally:await app.close()
    asyncio.run(run())


@pytest.mark.parametrize('identifier',['powershell','windows_powershell','git_bash'])
def test_actual_shell_application_verified_output_export_and_purge(tmp_path,identifier):
    async def run():
        app=await setup(tmp_path)
        try:
            cid=(await create(app))['id'];detected=await result(app,'shell.detect')
            current=next(i for i in detected['interpreters'] if i['id']==identifier)
            assert current['available'],current['reason']
            script="printf '%s' '合成 Shell 产物' > \"$ORVIA_OUTPUT_DIR/合成结果.txt\"; printf '%s\\n' '合成 Shell 返回证据'" if identifier=='git_bash' else "$p=Join-Path $env:ORVIA_OUTPUT_DIR '合成结果.txt'; [IO.File]::WriteAllText($p,'合成 Shell 产物',[Text.UTF8Encoding]::new($false)); Write-Output '合成 Shell 返回证据'"
            packet=await result(app,'shell.preview',{'id':cid,'interpreter_id':identifier,'script':script,'expected_stdout':'合成 Shell 返回证据','output_names':['合成结果.txt']})
            assert await result(app,'shell.review',{'id':cid,'run_id':packet['run_id']})==packet
            execution=await result(app,'shell.execute',{'id':cid,'run_id':packet['run_id'],'revision':packet['revision']})
            assert execution['status']=='exited' and execution['exit_code']==0 and execution['children_reaped']
            assert execution['verification']['status']=='passed' and len(execution['outputs'])==1
            assert not (await call(app,'shell.execute',{'id':cid,'run_id':packet['run_id'],'revision':packet['revision']}))['ok']
            exported=await result(app,'shell.export_preview',{'id':cid,'run_id':packet['run_id'],'name':'合成结果.txt'})
            target=tmp_path/'合成 导出结果.txt'
            receipt=await result(app,'shell.export',{'id':cid,'run_id':packet['run_id'],'name':'合成结果.txt','revision':exported['revision'],'path':str(target)})
            assert receipt['verified'] and target.read_text(encoding='utf-8')=='合成 Shell 产物'
            assert (await result(app,'shell.history',{'id':cid}))['executions']==[execution]
            directory=app.shell.root/cid
            await result(app,'chat.delete',{'id':cid})
            assert not directory.exists() and target.exists()
            async with app.store._lock:
                for table in ('shell_attempts','shell_executions'):
                    async with app.store._db().execute(f'SELECT count(*) FROM {table} WHERE cid=?',(cid,)) as cursor:assert (await cursor.fetchone())[0]==0
        finally:await app.close()
    asyncio.run(run())


def test_running_shell_blocks_delete_and_control_cancel_remains_available(tmp_path):
    async def run():
        app=await setup(tmp_path);started=asyncio.Event()
        class Runner:
            async def detect(self):return {'interpreters':[{'id':'powershell','label':'合成 PowerShell','executable':'C:/synthetic.exe','version':'1','sha256':'1'*64,'available':True,'reason':None,'distro':None}]}
            async def run(self,interpreter,script,cwd,timeout,event,output_root,*,input_root):
                started.set();await event.wait()
                return {'state':'cancelled','exit_code':None,'stdout':'','stderr':'','stdout_truncated':False,'stderr_truncated':False,'children_reaped':True,'started_at':'2026-10-08T00:00:00Z','finished_at':'2026-10-08T00:00:01Z'}
        app.shell.runner=Runner()
        try:
            cid=(await create(app))['id'];packet=await result(app,'shell.preview',{'id':cid,'interpreter_id':'powershell','script':'合成取消测试'})
            request={'id':cid,'run_id':packet['run_id']}
            task=asyncio.create_task(result(app,'shell.execute',{**request,'revision':packet['revision']}))
            await started.wait();denied=await call(app,'chat.delete',{'id':cid})
            assert not denied['ok'] and denied['error']['code']=='DELETE_BLOCKED'
            assert (await result(app,'shell.cancel',request))['status']=='running'
            ended=await task;assert ended['status']=='cancelled' and ended['verification']['status']=='unknown'
            await result(app,'chat.delete',{'id':cid})
        finally:await app.close()
    asyncio.run(run())


def test_restart_running_attempt_unknown_no_replay_or_delete(tmp_path):
    async def run():
        app=await setup(tmp_path)
        cid=(await create(app))['id'];rid=str(uuid4())
        packet={'id':cid,'run_id':rid,'revision':'1'*64,'interpreter':{'id':'powershell'}}
        value=app.shell._blank(packet)
        async with app.store._lock:
            await app.store._db().execute('INSERT INTO shell_attempts VALUES(?,?,?,?)',(cid,rid,'1'*64,'running'))
            await app.store._db().execute('INSERT INTO shell_executions VALUES(?,?,?)',(cid,rid,json.dumps(value)))
        await app.close();app=await setup(tmp_path)
        try:
            state=await result(app,'shell.status',{'id':cid,'run_id':rid})
            assert state['status']=='unknown' and not state['children_reaped'] and not app.shell._active
            assert not (await call(app,'shell.execute',{'id':cid,'run_id':rid,'revision':'1'*64}))['ok']
            denied=await call(app,'chat.delete',{'id':cid});assert not denied['ok'] and denied['error']['code']=='DELETE_BLOCKED'
        finally:await app.close()
    asyncio.run(run())


def test_restart_pending_delete_cleans_private_shell_body_before_journal_completion(tmp_path):
    async def run():
        app=await setup(tmp_path);cid=(await create(app))['id']
        directory=app.shell.root/cid/str(uuid4());directory.mkdir(parents=True)
        (directory/'script.ps1').write_text('合成待删除正文',encoding='utf-8')
        async with app.store._lock:
            await app.store._db().execute("INSERT INTO chat_deletions VALUES (?,'pending')",(cid,))
        await app.close();app=await setup(tmp_path)
        try:
            assert not (app.shell.root/cid).exists()
            assert not (await call(app,'chat.get',{'id':cid}))['ok']
            async with app.store._lock:
                async with app.store._db().execute('SELECT state FROM chat_deletions WHERE id=?',(cid,)) as cursor:assert (await cursor.fetchone())[0]=='completed'
        finally:await app.close()
    asyncio.run(run())
