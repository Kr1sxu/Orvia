"""V4-008真实普通Windows Shell与有界回收；WSL只测合成边界，不冒充真实发行版。"""
import asyncio
from pathlib import Path
import time
import pytest
import psutil
from orvia_backend.shell import runtime as r


@pytest.fixture(scope='module')
def installed():
    return {item['id']:item for item in asyncio.run(r.detect())['interpreters']}


def interpreter(installed,identifier):
    row=installed[identifier]
    if not row['available']:pytest.skip(row['reason'])
    return row


def script(tmp_path,identifier,body):
    work=tmp_path/"合成 cwd 空格'引号";work.mkdir(exist_ok=True)
    inputs=tmp_path/'inputs';outputs=tmp_path/'outputs'
    inputs.mkdir(exist_ok=True);outputs.mkdir(exist_ok=True)
    path=tmp_path/('合成 script 空格.sh' if identifier=='git_bash' else "合成 script 空格'引号.ps1")
    path.write_text(body,encoding='utf-8' if identifier=='git_bash' else 'utf-8-sig')
    return path,work,inputs,outputs


def execute(row,paths,timeout=10,event=None):
    path,work,inputs,outputs=paths
    async def invoke():
        return await r.run(row,path,work,timeout,event or asyncio.Event(),outputs,input_root=inputs)
    return asyncio.run(invoke())


async def gone(pid):
    # TerminateJob完成与Windows PID对象最终释放存在短暂时间差；实际有限回查。
    deadline=time.monotonic()+2
    while psutil.pid_exists(pid) and time.monotonic()<deadline:await asyncio.sleep(.02)
    assert not psutil.pid_exists(pid)


def test_actual_detect_fixed_identity_and_docker_exclusion(installed):
    assert not r.is_elevated()
    for key in ('powershell','windows_powershell','git_bash'):
        row=interpreter(installed,key)
        assert row['sha256']==r.file_identity(row['executable']) and row['version']
        assert set(row)=={'id','label','executable','version','sha256','available','reason','distro'}
    assert all(not str(item['distro']).casefold().startswith('docker-desktop') for item in installed.values())


@pytest.mark.parametrize('identifier',['powershell','windows_powershell','git_bash'])
def test_real_unicode_paths_env_input_and_output(installed,tmp_path,identifier,monkeypatch):
    monkeypatch.setenv('ORVIA_SYNTHETIC_API_KEY','never-inherit')
    monkeypatch.setenv('HTTPS_PROXY','http://synthetic.invalid')
    if identifier=='git_bash':
        body='printf "合成输出\\n"\nprintf "合成错误\\n" >&2\n[ -z "$ORVIA_SYNTHETIC_API_KEY" ] && [ -z "$HTTPS_PROXY" ] || exit 91\ncat "$ORVIA_INPUT_DIR/输入 空格.txt" > "$ORVIA_OUTPUT_DIR/产物.txt"\npwd\n'
    else:
        body="if($env:ORVIA_SYNTHETIC_API_KEY -or $env:HTTPS_PROXY){exit 91}\nWrite-Output '合成输出'\n[Console]::Error.WriteLine('合成错误')\n$b=[IO.File]::ReadAllText((Join-Path $env:ORVIA_INPUT_DIR '输入 空格.txt'))\n[IO.File]::WriteAllText((Join-Path $env:ORVIA_OUTPUT_DIR '产物.txt'),$b,(New-Object Text.UTF8Encoding($false)))\nWrite-Output (Get-Location).Path\n"
    paths=script(tmp_path,identifier,body)
    (paths[2]/'输入 空格.txt').write_text('合成输入',encoding='utf-8')
    result=execute(interpreter(installed,identifier),paths)
    assert result['state']=='completed' and result['exit_code']==0 and result['children_reaped'],result
    assert '合成输出' in result['stdout'] and '合成错误' in result['stderr']
    assert "合成 cwd 空格'引号" in result['stdout']
    assert (paths[3]/'产物.txt').read_text(encoding='utf-8')=='合成输入'


@pytest.mark.parametrize('identifier',['powershell','windows_powershell','git_bash'])
def test_real_continuous_drain_keeps_each_utf8_budget(installed,tmp_path,identifier):
    body='for ((i=0;i<20000;i++)); do printf "界"; printf "界" >&2; done' if identifier=='git_bash' else "$s='界'*20000;[Console]::Write($s);[Console]::Error.Write($s)"
    result=execute(interpreter(installed,identifier),script(tmp_path,identifier,body),20)
    assert result['state']=='completed' and result['children_reaped'],result
    for channel in ('stdout','stderr'):
        assert result[channel] and len(result[channel].encode('utf-8'))<=16384
        assert result[channel+'_truncated']


@pytest.mark.parametrize('identifier',['powershell','windows_powershell','git_bash'])
def test_real_nonzero_exit_is_failure(installed,tmp_path,identifier):
    result=execute(interpreter(installed,identifier),script(tmp_path,identifier,'exit 7'))
    assert result['state']=='failed' and result['exit_code']==7 and result['children_reaped']


def test_real_exit_259_is_exited_not_still_active(installed,tmp_path):
    result=execute(interpreter(installed,'powershell'),script(tmp_path,'powershell','exit 259'),2)
    assert result['state']=='failed' and result['exit_code']==259 and result['children_reaped']


@pytest.mark.parametrize('identifier',['powershell','windows_powershell','git_bash'])
def test_real_timeout_job_receipt(installed,tmp_path,identifier):
    body='sleep 30' if identifier=='git_bash' else 'Start-Sleep -Seconds 30'
    result=execute(interpreter(installed,identifier),script(tmp_path,identifier,body),1)
    assert result['state']=='timeout' and result['exit_code'] is None and result['children_reaped'],result


@pytest.mark.parametrize('identifier',['powershell','windows_powershell','git_bash'])
def test_real_cancel_event_job_receipt(installed,tmp_path,identifier):
    body='sleep 30' if identifier=='git_bash' else 'Start-Sleep -Seconds 30'
    paths=script(tmp_path,identifier,body)
    async def invoke():
        event=asyncio.Event()
        task=asyncio.create_task(r.run(interpreter(installed,identifier),paths[0],paths[1],10,event,paths[3],input_root=paths[2]))
        await asyncio.sleep(.6);event.set()
        return await task
    result=asyncio.run(invoke())
    assert result['state']=='cancelled' and result['children_reaped'],result


def test_real_cancel_reaps_known_windows_child(installed,tmp_path):
    marker=tmp_path/'child.pid';row=interpreter(installed,'powershell')
    child=r._ps_quote(marker)
    child_command=f'[IO.File]::WriteAllText({child},[string]$PID);Start-Sleep -Seconds 30'
    import base64
    encoded=base64.b64encode(child_command.encode('utf-16-le')).decode()
    body=f"Start-Process -FilePath (Join-Path $PSHOME 'pwsh.exe') -ArgumentList '-NoLogo','-NoProfile','-NonInteractive','-EncodedCommand','{encoded}' -PassThru | Out-Null;Start-Sleep -Seconds 30"
    paths=script(tmp_path,'powershell',body)
    async def invoke():
        event=asyncio.Event();task=asyncio.create_task(r.run(row,paths[0],paths[1],10,event))
        try:
            end=time.monotonic()+5
            while not marker.exists() and time.monotonic()<end:await asyncio.sleep(.02)
            assert marker.exists(),'真实child未生成PID回执'
            pid=int(marker.read_text());assert psutil.pid_exists(pid)
            event.set();result=await task
            assert result['state']=='cancelled' and result['children_reaped']
            await gone(pid)
        finally:
            event.set();await task
    asyncio.run(invoke())


def test_preset_cancel_zero_start(installed,tmp_path,monkeypatch):
    def forbidden(_):raise AssertionError('不应启动')
    monkeypatch.setattr(r,'_JobProcess',forbidden)
    event=asyncio.Event();event.set()
    result=execute(interpreter(installed,'powershell'),script(tmp_path,'powershell','exit 0'),event=event)
    assert result['state']=='cancelled' and result['children_reaped']


def test_elevated_token_refuses_before_spawn(installed,tmp_path,monkeypatch):
    monkeypatch.setattr(r,'is_elevated',lambda:True)
    with pytest.raises(r.ShellRuntimeError,match='SHELL_ELEVATED'):
        execute(interpreter(installed,'powershell'),script(tmp_path,'powershell','exit 0'))


def test_changed_exe_identity_refuses_before_spawn(installed,tmp_path):
    row={**interpreter(installed,'powershell'),'sha256':'0'*64}
    with pytest.raises(r.ShellRuntimeError,match='SHELL_CHANGED'):
        execute(row,script(tmp_path,'powershell','exit 0'))


def test_unknown_interpreter_no_fallback(installed,tmp_path):
    row={**interpreter(installed,'powershell'),'id':'unknown'}
    with pytest.raises(r.ShellRuntimeError,match='SHELL_IDENTITY'):
        execute(row,script(tmp_path,'powershell','exit 0'))


def test_native_spawn_cancellation_retains_late_job_ownership(installed,tmp_path,monkeypatch):
    original=r._JobProcess;spawned=[]
    def delayed(config):
        time.sleep(.3);process=original(config);spawned.append(process);return process
    monkeypatch.setattr(r,'_JobProcess',delayed)
    paths=script(tmp_path,'powershell','Start-Sleep -Seconds 30')
    async def invoke():
        task=asyncio.create_task(r.run(interpreter(installed,'powershell'),paths[0],paths[1],10,asyncio.Event()))
        await asyncio.sleep(.05);task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
        assert len(spawned)==1 and spawned[0].job is None
        await gone(spawned[0].pid)
    asyncio.run(invoke())


@pytest.mark.parametrize('bad',['0:2:n','1:2:wrong','1:2:n:extra','../:2:n','1:NaN:n'])
def test_wsl_control_rejects_untrusted_pid_receipt(bad):
    with pytest.raises(r.ShellRuntimeError,match='SHELL_WSL_CONTROL'):r._control(bad,'n')


def test_wsl_docker_and_command_names_never_execute():
    assert r._distros('docker-desktop\r\ndocker-desktop-data\r\nUbuntu\r\n$(evil)')==['Ubuntu']
    for distro in ('docker-desktop','docker-desktop-data','$(evil)'):
        with pytest.raises(r.ShellRuntimeError,match='SHELL_WSL'):r._wsl_args(distro,'exit 0')


def test_wsl_missing_prerequisite_and_root_remain_unavailable(monkeypatch):
    async def unavailable(*args,**kw):return {'state':'failed','children_reaped':True,'stdout':''}
    monkeypatch.setattr(r,'_probe',unavailable)
    row=asyncio.run(r._detect_wsl('synthetic.exe','Ubuntu','0'*64))
    assert not row['available'] and row['reason']


def test_wsl_identity_rejection_never_claims_linux_reaped(monkeypatch):
    async def rejected(executable,args,*rest,**kw):
        command=args[args.index('-c')+1]
        assert "awk '{print $22}'" in command and "'$1==p" in command
        assert '/usr/bin/kill -KILL -- "-$pid"' in command
        return {'state':'failed','children_reaped':True,'stdout':'0'}
    monkeypatch.setattr(r,'_probe',rejected)
    assert not asyncio.run(r._wsl_group('synthetic.exe','Ubuntu',123,'456','nonce',terminate=True))


def test_reparse_interpreter_identity_refuses(installed,monkeypatch):
    from types import SimpleNamespace
    original=Path.lstat;exe=Path(interpreter(installed,'powershell')['executable'])
    def lstat(path,*args,**kwargs):
        item=original(path,*args,**kwargs)
        if path==exe:return SimpleNamespace(st_mode=item.st_mode,st_file_attributes=0x400)
        return item
    monkeypatch.setattr(Path,'lstat',lstat)
    with pytest.raises(r.ShellRuntimeError,match='SHELL_IDENTITY'):r.file_identity(exe)


def test_wsl_positive_prerequisites_freeze_uid_and_four_actual_tool_hashes(monkeypatch):
    async def prerequisites(executable,args,*rest,**kw):
        assert '/usr/bin/kill' in args[args.index('-c')+1]
        return {'state':'completed','children_reaped':True,'stdout':'1000\nGNU bash 5.2\n'+''.join('a'*64+'  /synthetic/tool'+str(i)+'\n' for i in range(4))}
    monkeypatch.setattr(r,'_probe',prerequisites)
    row=asyncio.run(r._detect_wsl('synthetic.exe','Ubuntu','0'*64))
    assert row['available'] and 'uid=1000' in row['version'] and 'tools=' in row['version']


def test_detect_total_budget_preserves_completed_rows_and_marks_unattempted(monkeypatch,installed):
    clock=[0.0];calls=[]
    monkeypatch.setattr(r,'monotonic',lambda:clock[0])
    async def consume(executable,args,timeout=5,**kw):
        calls.append(timeout);clock[0]+=9
        return {'state':'completed','children_reaped':True,'stdout':'1.0'}
    monkeypatch.setattr(r,'_probe',consume)
    rows=asyncio.run(r.detect())['interpreters']
    assert len(calls)==3 and all(timeout<=5 for timeout in calls)
    assert all(row['available'] for row in rows[:3])
    assert not rows[-1]['available'] and '25秒' in rows[-1]['reason']


def test_real_linux_receipt_error_still_closes_windows_job(installed):
    row=interpreter(installed,'powershell')
    async def failed():raise r.ShellRuntimeError('SHELL_WSL_CONTROL','合成Linux回查失败')
    result=asyncio.run(r._capture({'executable':row['executable'],'args':['-NoProfile','-NonInteractive','-Command','exit 0']},5,asyncio.Event(),before_close=failed))
    assert result['state']=='failed' and not result['children_reaped']
    # Windows真实Job已经完成，不把Linux错误误标为成功。
    assert result['exit_code']==0


def test_wsl_cancel_before_probe_starts_no_launcher(monkeypatch,tmp_path):
    async def forbidden(*args,**kw):raise AssertionError('预先取消不启动WSL launcher')
    monkeypatch.setattr(r,'_detect_wsl',forbidden)
    event=asyncio.Event();event.set()
    result=asyncio.run(r._run_wsl({'id':'wsl:Ubuntu','distro':'Ubuntu'},tmp_path/'synthetic.sh',tmp_path,1,event,tmp_path,tmp_path))
    assert result['state']=='cancelled' and result['children_reaped']


def test_wsl_total_timeout_consumed_by_prerequisites_never_releases_script(monkeypatch,tmp_path):
    clock=[0.0];monkeypatch.setattr(r,'monotonic',lambda:clock[0])
    async def consumed(*args,**kw):clock[0]+=2;return {'available':True,'version':'synthetic'}
    monkeypatch.setattr(r,'_detect_wsl',consumed)
    row={'id':'wsl:Ubuntu','distro':'Ubuntu','executable':'synthetic.exe','sha256':'0'*64,'version':'synthetic'}
    result=asyncio.run(r._run_wsl(row,tmp_path/'synthetic.sh',tmp_path,1,asyncio.Event(),tmp_path,tmp_path))
    assert result['state']=='timeout' and result['children_reaped']


def test_actual_git_bash_wsl_host_syntax_and_control_escaping(installed,tmp_path,monkeypatch):
    captured={};row={'id':'wsl:Ubuntu','distro':'Ubuntu','executable':'synthetic.exe','sha256':'0'*64,'version':'synthetic'}
    async def preflight(*args,**kw):return {'available':True,'version':'synthetic'}
    async def capture(config,*args,**kw):
        captured['args']=config['args'];captured['ready']=kw['on_spawned'];return {'state':'synthetic'}
    with monkeypatch.context() as patch:
        patch.setattr(r,'_detect_wsl',preflight);patch.setattr(r,'_capture',capture)
        asyncio.run(r._run_wsl(row,tmp_path/'synthetic.sh',tmp_path,10,asyncio.Event(),tmp_path,tmp_path))
    args=captured['args'];outer=args[args.index('-c')+1];inner=args[args.index('orvia-shell')+1]
    ready=next(value for value in captured['ready'].__code__.co_consts if isinstance(value,str) and value.startswith('pid=$1;'))
    template=inner.split('printf ',1)[1].split(' ',1)[0]
    translate=ready.rsplit('tr ',1)[1].split(' < ',1)[0]
    # 运行生成器实际控制格式/转义的无害片段；不运行WSL或Linux终止命令。
    body='printf '+template+' 123 456 nonce\nprintf "A\\000B" | tr '+translate+'\n'
    result=execute(interpreter(installed,'git_bash'),script(tmp_path,'git_bash',body))
    assert result['state']=='completed' and result['stdout']=='123:456:nonce\nA B',result
    for index,command in enumerate((outer,inner,ready)):
        path=tmp_path/('host-'+str(index)+'.sh');path.write_text(command,encoding='utf-8')
        value=asyncio.run(r._probe(interpreter(installed,'git_bash')['executable'],['--noprofile','--norc','-n',str(path)]))
        assert value['state']=='completed',value
