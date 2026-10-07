"""V4-008 真实SQLite与合成脚本；默认无模型、云请求或用户文件。"""

import asyncio
import copy
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest

from orvia_backend.shell import ShellService, ShellError
from orvia_backend.memory.service import size
from test_chat import setup, create


class Runner:
    def __init__(self):
        self.identity={'id':'powershell','label':'合成PowerShell','executable':'D:\\synthetic\\pwsh.exe','version':'7.4','sha256':'1'*64,'available':True,'reason':None,'distro':None}
        self.calls=0
        self.stdout='合成核验成功'
        self.result={'state':'completed','exit_code':0,'stdout':'','stderr':'','stdout_truncated':False,'stderr_truncated':False,'children_reaped':True,'started_at':'2026-10-08T00:00:00Z','finished_at':'2026-10-08T00:00:01Z'}
        self.callback=None
        self.outputs={'合成.txt':b'synthetic output'}
        self.wait=False
        self.entered=asyncio.Event()

    async def detect(self):
        return {'interpreters':[copy.deepcopy(self.identity)]}

    async def run(self,interpreter,script_path,cwd,timeout_seconds,cancel_event,output_root=None,*,input_root=None):
        self.calls+=1
        self.entered.set()
        self.script=Path(script_path).read_text(encoding='utf-8-sig')
        self.cwd=cwd
        self.inputs={p.name:p.read_bytes() for p in Path(input_root).iterdir()}
        if self.callback:
            await self.callback()
        for name,data in self.outputs.items():
            (Path(output_root)/name).write_bytes(data)
        value=copy.deepcopy(self.result)
        value['stdout']=self.stdout
        if self.wait:
            await cancel_event.wait()
            value.update(state='cancelled',exit_code=None)
        return value


async def prepare(tmp_path):
    app=await setup(tmp_path)
    cid=(await create(app))['id']
    runner=Runner()
    service=ShellService(app.store,app.chat,app.computer,runner)
    await service.open()
    return app,service,cid,runner


def test_sqlite_single_approval_before_start_and_exit_not_business_completion(tmp_path):
    async def run():
        app,s,cid,r=await prepare(tmp_path)
        try:
            p=await s.preview(cid,'powershell','Write-Output 合成',expected_stdout='合成核验',output_names=['合成.txt'])
            assert r.calls==0 and await s.review(cid,p['run_id'])==p
            async def check():
                async with app.store._lock:
                    rows=await s._rows(app.store._db(),'SELECT state FROM shell_attempts WHERE cid=? AND run_id=?',(cid,p['run_id']))
                assert [tuple(row) for row in rows]==[('running',)]
            r.callback=check
            result=await s.execute(cid,p['run_id'],p['revision'])
            assert result['status']=='exited' and result['verification']['status']=='passed' and r.calls==1
            assert result['outputs'][0]['sha256']==hashlib.sha256(b'synthetic output').hexdigest()
            s._previews.clear()
            with pytest.raises(ShellError,match='SHELL_ALREADY_ATTEMPTED'):
                await s.execute(cid,p['run_id'],p['revision'])
            assert (await s.history(cid))['executions']==[result]
        finally:
            await s.close();await app.close()
    asyncio.run(run())


@pytest.mark.parametrize('changes',[
    {'script':''},{'script':'x'*16385},{'script':'synthetic API_KEY=badvalue'},{'script':'a\x00b'},
    {'timeout_seconds':0},{'timeout_seconds':61},{'timeout_seconds':True},
    {'expected_stdout':''},{'expected_stdout':'x'*1001},
    {'output_names':['../file']},{'output_names':['CON']},{'output_names':['a','A']},{'output_names':['a']*11},
    {'inputs':['a','b','c','d']}, {'interpreter_id':'unknown'},
])
def test_preparation_rejects_invalid_limits_without_start(tmp_path,changes):
    async def run():
        app,s,cid,r=await prepare(tmp_path)
        try:
            args={'cid':cid,'interpreter_id':'powershell','script':'Write-Output 合成'}
            args.update(changes)
            with pytest.raises(Exception):
                await s.preview(**args)
            assert r.calls==0
        finally:
            await s.close();await app.close()
    asyncio.run(run())


def test_input_full_hash_and_native_cwd_frozen_input_copies(tmp_path):
    async def run():
        app,s,cid,r=await prepare(tmp_path)
        native=tmp_path/'合成 空格目录';native.mkdir()
        inp=native/'合成输入.txt';inp.write_bytes(b'original')
        try:
            p=await s.preview(cid,'powershell','Write-Output 合成',cwd=str(native),inputs=[str(inp)])
            inp.write_bytes(b'changed')
            with pytest.raises(ShellError,match='SHELL_INPUT_CHANGED'):
                await s.review(cid,p['run_id'])
            with pytest.raises(ShellError,match='SHELL_INPUT_CHANGED'):
                await s.execute(cid,p['run_id'],p['revision'])
            assert r.calls==0
            inp.write_bytes(b'original')
            result=await s.execute(cid,p['run_id'],p['revision'])
            assert result['status']=='exited' and result['verification']['status']=='not_requested'
            assert r.cwd==str(native) and r.inputs=={'合成输入.txt':b'original'} and inp.read_bytes()==b'original'
        finally:
            await s.close();await app.close()
    asyncio.run(run())


def test_interpreter_changed_scope_wrong_revision_and_cwd_replacement_refuse(tmp_path):
    async def run():
        app,s,cid,r=await prepare(tmp_path)
        native=tmp_path/'native';native.mkdir()
        try:
            p=await s.preview(cid,'powershell','Write-Output 合成',cwd=str(native))
            other=(await create(app))['id']
            for c,revision in [(other,p['revision']),(cid,'0'*64)]:
                with pytest.raises(ShellError,match='SHELL_REVIEW'):
                    await s.execute(c,p['run_id'],revision)
            r.identity['sha256']='2'*64
            with pytest.raises(ShellError,match='SHELL_IDENTITY_CHANGED'):
                await s.execute(cid,p['run_id'],p['revision'])
            r.identity['sha256']='1'*64
            native.rename(tmp_path/'oldnative');native.mkdir()
            with pytest.raises(Exception):
                await s.execute(cid,p['run_id'],p['revision'])
            assert r.calls==0
        finally:
            await s.close();await app.close()
    asyncio.run(run())


@pytest.mark.parametrize('case',['exit1','timeout','cancel','unreaped','truncated','control','checkfailed','missing','large','total'])
def test_execution_verification_cannot_pass_uncertain_or_bad_outputs(tmp_path,case):
    async def run():
        app,s,cid,r=await prepare(tmp_path)
        try:
            outputs=[]
            if case=='exit1':r.result['exit_code']=1
            if case=='timeout':r.result.update(state='timeout',exit_code=None)
            if case=='cancel':r.result.update(state='cancelled',exit_code=None)
            if case=='unreaped':r.result['children_reaped']=False
            if case=='truncated':r.result['stdout_truncated']=True
            if case=='control':r.stdout='\x01'*16384;r.result['stderr']='\x01'*16384
            if case=='checkfailed':r.stdout='different'
            if case=='missing':outputs=['missing.txt']
            if case=='large':outputs=['合成.txt'];r.outputs['合成.txt']=b'a'*1048577
            if case=='total':outputs=['a','b','c'];r.outputs={n:b'a'*1048576 for n in outputs}
            p=await s.preview(cid,'powershell','Write-Output 合成',expected_stdout='合成核验',output_names=outputs)
            result=await s.execute(cid,p['run_id'],p['revision'])
            assert result['verification']['status']!='passed' and size(result)<=49152
            if case=='unreaped':assert result['status']=='unknown' and await s.has_unresolved(cid)
            if case=='control':assert result['stdout_truncated'] or result['stderr_truncated']
            if case=='timeout':assert result['status']=='timed_out'
        finally:
            await s.close();await app.close()
    asyncio.run(run())


def test_cancel_and_close_wait_for_self_owned_process_report(tmp_path):
    async def run():
        app,s,cid,r=await prepare(tmp_path)
        try:
            r.wait=True
            p=await s.preview(cid,'powershell','Write-Output 合成')
            task=asyncio.create_task(s.execute(cid,p['run_id'],p['revision']))
            await r.entered.wait()
            assert await s.has_unresolved(cid)
            assert (await s.cancel(cid,p['run_id']))['status']=='running'
            result=await task
            assert result['status']=='cancelled' and result['children_reaped'] and not await s.has_unresolved(cid)
            r.entered.clear()
            p=await s.preview(cid,'powershell','Write-Output 合成')
            task=asyncio.create_task(s.execute(cid,p['run_id'],p['revision']))
            await r.entered.wait();await s.close()
            assert (await task)['status']=='cancelled'
        finally:
            await s.close();await app.close()
    asyncio.run(run())


def test_export_separate_approval_hash_recheck_no_overwrite_and_user_files_preserved(tmp_path):
    async def run():
        app,s,cid,r=await prepare(tmp_path)
        inp=tmp_path/'合成输入.txt';inp.write_bytes(b'input')
        dest=tmp_path/'合成导出.txt'
        try:
            p=await s.preview(cid,'powershell','Write-Output 合成',inputs=[str(inp)],output_names=['合成.txt'])
            await s.execute(cid,p['run_id'],p['revision'])
            e=await s.export_preview(cid,p['run_id'],'合成.txt')
            receipt=await s.export(cid,p['run_id'],'合成.txt',str(dest),e['revision'])
            assert receipt['verified'] and dest.read_bytes()==b'synthetic output'
            e=await s.export_preview(cid,p['run_id'],'合成.txt')
            with pytest.raises(Exception,match='EXPORT_EXISTS'):
                await s.export(cid,p['run_id'],'合成.txt',str(dest),e['revision'])
            e=await s.export_preview(cid,p['run_id'],'合成.txt')
            (s._directory(cid,p['run_id'])/'output'/'合成.txt').write_bytes(b'mutated')
            with pytest.raises(ShellError,match='SHELL_OUTPUT_CHANGED'):
                await s.export(cid,p['run_id'],'合成.txt',str(tmp_path/'new.txt'),e['revision'])
            await s.purge_files(cid)
            assert inp.read_bytes()==b'input' and dest.read_bytes()==b'synthetic output' and not (s.root/cid).exists()
        finally:
            await s.close();await app.close()
    asyncio.run(run())


def test_pending_tombstone_late_result_does_not_restore_body(tmp_path):
    async def run():
        app,s,cid,r=await prepare(tmp_path)
        try:
            p=await s.preview(cid,'powershell','Write-Output 合成')
            async def erase():
                async with app.store._lock:
                    db=app.store._db()
                    await db.execute("INSERT INTO chat_deletions(id,state) VALUES(?,'pending')",(cid,))
                    await db.execute('DELETE FROM shell_attempts WHERE cid=?',(cid,))
                    await db.execute('DELETE FROM shell_executions WHERE cid=?',(cid,))
            r.callback=erase
            with pytest.raises(ShellError,match='SHELL_CONVERSATION'):
                await s.execute(cid,p['run_id'],p['revision'])
            async with app.store._lock:
                assert not await s._rows(app.store._db(),'SELECT 1 FROM shell_executions WHERE cid=?',(cid,))
            with pytest.raises(ShellError,match='SHELL_CONVERSATION'):
                await s.preview(cid,'powershell','Write-Output 合成')
        finally:
            await s.close();await app.close()
    asyncio.run(run())


def test_startup_unknown_no_automatic_execution_and_delete_blocked(tmp_path):
    async def run():
        app,s,cid,r=await prepare(tmp_path)
        try:
            p=await s.preview(cid,'powershell','Write-Output 合成')
            value=s._blank(p)
            async with app.store._lock:
                db=app.store._db()
                await db.execute('INSERT INTO shell_attempts VALUES(?,?,?,?)',(cid,p['run_id'],p['revision'],'running'))
                await db.execute('INSERT INTO shell_executions VALUES(?,?,?)',(cid,p['run_id'],json.dumps(value)))
            rebuilt=ShellService(app.store,app.chat,app.computer,r)
            await rebuilt.open()
            assert (await rebuilt.status(cid,p['run_id']))['status']=='unknown' and r.calls==0
            with pytest.raises(ShellError,match='SHELL_ALREADY_ATTEMPTED'):
                await rebuilt.execute(cid,p['run_id'],p['revision'])
            with pytest.raises(ShellError,match='SHELL_DELETE_BLOCKED'):
                await rebuilt.purge_files(cid)
        finally:
            await s.close();await app.close()
    asyncio.run(run())


def test_attempt_cap_history_budget_cache_eviction_and_no_replay(tmp_path):
    async def run():
        app,s,cid,r=await prepare(tmp_path)
        try:
            for _ in range(21):
                p=await s.preview(cid,'powershell','Write-Output 合成')
            assert len(s._previews)==20
            async with app.store._lock:
                db=app.store._db()
                for _ in range(128):
                    await db.execute('INSERT INTO shell_attempts VALUES(?,?,?,?)',(cid,str(uuid4()),'1'*64,'exited'))
            with pytest.raises(ShellError,match='SHELL_ATTEMPT_LIMIT'):
                await s.execute(cid,p['run_id'],p['revision'])
            assert r.calls==0
        finally:
            await s.close();await app.close()
    asyncio.run(run())


def test_preview_late_tombstone_clears_private_directory(tmp_path):
    async def run():
        app,s,cid,r=await prepare(tmp_path)
        original=s._alive
        calls=0
        async def late(db,owner):
            nonlocal calls
            calls+=1
            if calls==2:
                await db.execute("INSERT INTO chat_deletions VALUES(?,'pending')",(owner,))
            await original(db,owner)
        s._alive=late
        try:
            with pytest.raises(ShellError,match='SHELL_CONVERSATION'):
                await s.preview(cid,'powershell','Write-Output 合成')
            assert not s._previews and not list((s.root/cid).iterdir()) and r.calls==0
        finally:
            await s.close();await app.close()
    asyncio.run(run())


def test_runtime_exception_is_unknown_not_retried_or_deletable(tmp_path):
    async def run():
        app,s,cid,r=await prepare(tmp_path)
        async def broken():
            raise OSError('synthetic error')
        r.callback=broken
        try:
            p=await s.preview(cid,'powershell','Write-Output 合成')
            value=await s.execute(cid,p['run_id'],p['revision'])
            assert value['status']=='unknown' and r.calls==1 and await s.has_unresolved(cid)
            await s.open()
            assert await s.status(cid,p['run_id'])==value
            with pytest.raises(ShellError,match='SHELL_ALREADY_ATTEMPTED'):
                await s.execute(cid,p['run_id'],p['revision'])
            with pytest.raises(ShellError,match='SHELL_DELETE_BLOCKED'):
                await s.purge_files(cid)
        finally:
            await s.close();await app.close()
    asyncio.run(run())


def test_hardlinked_output_cannot_be_verified_or_exported(tmp_path):
    async def run():
        import os
        app,s,cid,r=await prepare(tmp_path)
        src=tmp_path/'outside.txt';src.write_bytes(b'private')
        r.outputs={}
        try:
            p=await s.preview(cid,'powershell','Write-Output 合成',output_names=['linked.txt'])
            async def link():
                os.link(src,s._directory(cid,p['run_id'])/'output'/'linked.txt')
            r.callback=link
            value=await s.execute(cid,p['run_id'],p['revision'])
            assert value['verification']['status']=='failed' and value['outputs']==[]
            with pytest.raises(ShellError,match='SHELL_OUTPUT_CHANGED'):
                await s.export_preview(cid,p['run_id'],'linked.txt')
            await s.purge_files(cid)
            assert src.read_bytes()==b'private'
        finally:
            await s.close();await app.close()
    asyncio.run(run())


def test_history_bytes_cap_and_body_eviction_never_remove_attempt_fact(tmp_path):
    async def run():
        app,s,cid,r=await prepare(tmp_path)
        r.stdout='合成'*2500
        try:
            first=None
            for _ in range(34):
                p=await s.preview(cid,'powershell','Write-Output 合成')
                await s.execute(cid,p['run_id'],p['revision'])
                first=first or p
            history=await s.history(cid)
            assert len(history['executions'])<=10 and size(history)<=49152 and history['truncated']
            async with app.store._lock:
                db=app.store._db()
                assert (await s._rows(db,'SELECT count(*) FROM shell_attempts WHERE cid=?',(cid,)))[0][0]==34
                assert (await s._rows(db,'SELECT count(*) FROM shell_executions WHERE cid=?',(cid,)))[0][0]==32
            with pytest.raises(ShellError,match='SHELL_ALREADY_ATTEMPTED'):
                await s.execute(cid,first['run_id'],first['revision'])
            await s.purge_files(cid)
        finally:
            await s.close();await app.close()
    asyncio.run(run())


@pytest.mark.parametrize('interpreter_id',['powershell','windows_powershell','git_bash'])
def test_real_service_interpreter_unicode_inputs_artifact_and_native_export(tmp_path,interpreter_id):
    async def run():
        app=await setup(tmp_path)
        cid=(await create(app))['id']
        s=ShellService(app.store,app.chat,app.computer)
        await s.open()
        native=tmp_path/'合成 cwd 空格';native.mkdir()
        inp=tmp_path/'合成 input 空格.txt';inp.write_text('合成输入',encoding='utf-8')
        try:
            row=next((i for i in (await s.detect())['interpreters'] if i['id']==interpreter_id),None)
            if row is None or not row['available']:
                pytest.skip('本机解释器未安装或普通权限不可用')
            if interpreter_id=='git_bash':
                script='printf "合成执行\\n"\ncat "$ORVIA_INPUT_DIR/合成 input 空格.txt" > "$ORVIA_OUTPUT_DIR/合成产物.txt"\n'
            else:
                script="Write-Output '合成执行'\n$body=[IO.File]::ReadAllText((Join-Path $env:ORVIA_INPUT_DIR '合成 input 空格.txt'))\n[IO.File]::WriteAllText((Join-Path $env:ORVIA_OUTPUT_DIR '合成产物.txt'),$body,(New-Object Text.UTF8Encoding($false)))\n"
            p=await s.preview(cid,interpreter_id,script,expected_stdout='合成执行',output_names=['合成产物.txt'],cwd=str(native),inputs=[str(inp)])
            assert await s.review(cid,p['run_id'])==p
            value=await s.execute(cid,p['run_id'],p['revision'])
            assert value['status']=='exited' and value['exit_code']==0 and value['children_reaped'] and value['verification']['status']=='passed',value
            e=await s.export_preview(cid,p['run_id'],'合成产物.txt')
            target=tmp_path/'合成回传 空格.txt'
            receipt=await s.export(cid,p['run_id'],'合成产物.txt',str(target),e['revision'])
            assert receipt['verified'] and target.read_text(encoding='utf-8')=='合成输入'
            await s.purge_files(cid)
            assert native.exists() and inp.exists() and target.exists()
        finally:
            await s.close();await app.close()
    asyncio.run(run())


def test_startup_clears_only_unattempted_canonical_private_task_directories(tmp_path):
    async def run():
        app,s,cid,r=await prepare(tmp_path)
        try:
            draft=await s.preview(cid,'powershell','Write-Output 合成')
            attempted=await s.preview(cid,'powershell','Write-Output 合成')
            await s.execute(cid,attempted['run_id'],attempted['revision'])
            attempted_dir=s._directory(cid,attempted['run_id'])
            saved=attempted_dir/'output'/'合成.txt'
            unknown=s.root/cid/'not-an-execution';unknown.mkdir()
            (unknown/'user.txt').write_bytes(b'untouched')
            native=tmp_path/'native';native.mkdir();(native/'user.txt').write_bytes(b'untouched')
            async with app.store._lock:
                await app.store._db().execute('DELETE FROM shell_executions WHERE cid=?',(cid,))
            rebuilt=ShellService(app.store,app.chat,app.computer,r)
            await rebuilt.open()
            assert not s._directory(cid,draft['run_id']).exists()
            assert saved.read_bytes()==b'synthetic output'
            assert (unknown/'user.txt').read_bytes()==b'untouched' and (native/'user.txt').read_bytes()==b'untouched'
            assert r.calls==1
        finally:
            await s.close();await app.close()
    asyncio.run(run())


@pytest.mark.parametrize('mode',['timeout','cancel'])
def test_real_service_timeout_cancel_are_known_interrupts_not_business_success(tmp_path,mode):
    async def run():
        app=await setup(tmp_path)
        cid=(await create(app))['id']
        s=ShellService(app.store,app.chat,app.computer)
        await s.open()
        try:
            row=next((i for i in (await s.detect())['interpreters'] if i['id']=='powershell'),None)
            if row is None or not row['available']:
                pytest.skip('本机PowerShell7不可用')
            script="[IO.File]::WriteAllText((Join-Path $env:ORVIA_OUTPUT_DIR 'started.txt'),'started')\nStart-Sleep -Seconds 10\nWrite-Output '合成结束'"
            p=await s.preview(cid,'powershell',script,timeout_seconds=1 if mode=='timeout' else 20,expected_stdout='合成结束')
            task=asyncio.create_task(s.execute(cid,p['run_id'],p['revision']))
            if mode=='cancel':
                marker=s._directory(cid,p['run_id'])/'output'/'started.txt'
                for _ in range(400):
                    if marker.exists() or task.done():
                        break
                    await asyncio.sleep(.05)
                assert marker.exists(),'真实脚本未开始，不能冒充正在执行取消验证'
                await s.cancel(cid,p['run_id'])
            result=await task
            assert result['status']==('timed_out' if mode=='timeout' else 'cancelled') and result['children_reaped'] and result['verification']['status']=='unknown',result
            assert not await s.has_unresolved(cid)
            with pytest.raises(ShellError,match='SHELL_ALREADY_ATTEMPTED'):
                await s.execute(cid,p['run_id'],p['revision'])
            await s.purge_files(cid)
        finally:
            await s.close();await app.close()
    asyncio.run(run())
