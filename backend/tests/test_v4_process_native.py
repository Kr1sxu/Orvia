"""V4-009：只对自有合成Python副本/窗口做真实操作，其它安全边界使用mock。"""
import ctypes
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import time
from types import SimpleNamespace
import pytest
import psutil
from orvia_backend.processes import native as n


@pytest.fixture
def private_python(tmp_path):
    folder=tmp_path/'合成 program 空格';folder.mkdir()
    base=Path(sys._base_executable)
    for name in (base.name,'python312.dll','vcruntime140.dll','vcruntime140_1.dll'):
        source=base.parent/name
        if source.is_file():shutil.copy2(source,folder/name)
    (folder/'pyvenv.cfg').write_text('home = '+str(base.parent)+'\ninclude-system-site-packages = false\n',encoding='utf-8')
    return folder/base.name


def launched(private_python,tmp_path,mode,*extra,wait=0):
    marker=tmp_path/'synthetic.json';fixture=Path(__file__).with_name('v4_process_fixture.py').resolve()
    result=n.launch(str(private_python),['-I','-u',str(fixture),mode,str(marker),*map(str,extra)],str(tmp_path),wait,sha256=n.executable(private_python)['sha256'])
    return result,marker


def ready(marker):
    deadline=time.monotonic()+3
    while time.monotonic()<deadline:
        try:
            value=json.loads(marker.read_text(encoding='utf-8'))
            if value['ready']:return value
        except (OSError,ValueError):pass
        time.sleep(.02)
    raise AssertionError('合成程序未ready')


def cleanup(identity):
    try:n.terminate(identity,2)
    except n.ProcessNativeError as exc:
        if exc.code not in ('PROCESS_UNAVAILABLE','PROCESS_IDENTITY'):raise


@pytest.mark.parametrize('code',[0,7,259])
def test_real_private_launch_wait_precise_identity_and_exit(private_python,tmp_path,code):
    result,marker=launched(private_python,tmp_path,'exit',code,wait=2)
    assert result['state']=='exited' and result['exit_code']==code and not result['close_sent']
    assert result['identity']['creation_ticks'].isdigit()
    assert result['identity']['sha256']==n.executable(private_python)['sha256']
    assert ready(marker)['pid']==result['identity']['pid']


def test_real_wait_timeout_never_terminates(private_python,tmp_path):
    result,marker=launched(private_python,tmp_path,'sleep');identity=result['identity']
    try:
        assert ready(marker)['pid']==identity['pid']
        assert n.inspect(identity['pid'],identity['create_time'],identity['creation_ticks'])==identity
        value=n.wait(identity,0)
        assert value['state']=='running' and value['exit_code'] is None and psutil.pid_exists(identity['pid'])
    finally:cleanup(identity)


def test_real_close_without_window_stays_running_until_separate_terminate(private_python,tmp_path):
    result,marker=launched(private_python,tmp_path,'sleep');identity=result['identity']
    try:
        ready(marker);value=n.close(identity,0)
        assert value['state']=='running' and not value['close_sent']
        ended=n.terminate(identity,2)
        assert ended['state']=='exited' and ended['exit_code']==0xE009
    finally:cleanup(identity)


@pytest.mark.parametrize('mode',['window-close','window-ignore'])
def test_real_wm_close_is_targeted_and_not_upgraded(private_python,tmp_path,mode):
    result,marker=launched(private_python,tmp_path,mode);identity=result['identity']
    try:
        ready(marker);value=n.close(identity,1)
        assert value['close_sent']
        assert ready(marker)['messages']==1
        if mode=='window-close':assert value['state']=='exited' and value['exit_code']==0
        else:
            assert value['state']=='running' and psutil.pid_exists(identity['pid'])
            assert n.terminate(identity,2)['state']=='exited'
    finally:cleanup(identity)


def test_real_clean_env_and_unicode_args_cwd(private_python,tmp_path,monkeypatch):
    for name in ('ORVIA_SYNTHETIC_API_KEY','ORVIA_SYNTHETIC_TOKEN','HTTPS_PROXY'):monkeypatch.setenv(name,'synthetic-only')
    result,marker=launched(private_python,tmp_path,'env',tmp_path,wait=2)
    assert result['state']=='exited' and result['exit_code']==0
    assert ready(marker)['clean'] and ready(marker)['cwd_matches']


def test_real_list_synthetic_only_and_no_private_fields(private_python,tmp_path,monkeypatch):
    result,marker=launched(private_python,tmp_path,'sleep');identity=result['identity']
    try:
        ready(marker);monkeypatch.setattr(n.psutil,'pids',lambda:[identity['pid']])
        value=n.list()
        assert value['processes']==[identity] and not value['truncated'] and value['unavailable_reason'] is None
        assert set(identity)=={'pid','name','executable','create_time','creation_ticks','sha256'}
    finally:cleanup(identity)


def fake_identity():
    return {'pid':123456,'name':'synthetic.exe','executable':r'C:\synthetic.exe','create_time':1.0,'creation_ticks':'134000000000000001','sha256':'0'*64}


def fake_kernel():
    calls=[]
    class Kernel:
        def OpenProcess(self,*args):calls.append(('open',args));return 111
        def CloseHandle(self,h):calls.append(('close',h));return True
        def WaitForSingleObject(self,h,ms):calls.append(('wait',h));return 0 if any(c[0]=='terminate' for c in calls) else 258
        def GetExitCodeProcess(self,h,out):ctypes.cast(out,ctypes.POINTER(w.DWORD))[0]=0xE009;return True
        def TerminateProcess(self,h,code):calls.append(('terminate',h));return True
    return Kernel(),calls


def test_mock_pid_reuse_refuses_before_termination(monkeypatch):
    identity=fake_identity();k,calls=fake_kernel();monkeypatch.setattr(n,'_api',lambda:(k,None,None))
    monkeypatch.setattr(n,'_identity',lambda *a,**kw:{**identity,'creation_ticks':'134000000000000002'})
    with pytest.raises(n.ProcessNativeError,match='PROCESS_CHANGED'):n.terminate(identity,0)
    assert len([c for c in calls if c[0]=='open'])==1 and not any(c[0]=='terminate' for c in calls)


def test_mock_terminate_uses_exact_verified_handle_once(monkeypatch):
    identity=fake_identity();k,calls=fake_kernel();monkeypatch.setattr(n,'_api',lambda:(k,None,None));monkeypatch.setattr(n,'_identity',lambda *a,**kw:identity)
    monkeypatch.setattr(n,'_security',lambda *a,**kw:None)
    value=n.terminate(identity,0)
    assert value['state']=='exited'
    assert len([c for c in calls if c[0]=='open'])==1
    assert [c[1] for c in calls if c[0] in ('terminate','wait','close')]==[111,111,111,111]


@pytest.mark.parametrize('critical,protection,known,expected',[(True,0xfffffffe,True,'PROCESS_CRITICAL'),(False,0,True,'PROCESS_PROTECTED'),(False,0xfffffffe,False,'PROCESS_CRITICAL')])
def test_mock_critical_protection_unknown_fail_closed(monkeypatch,critical,protection,known,expected):
    class K:
        def GetCurrentProcess(self):return 1
        def IsProcessCritical(self,h,out):ctypes.cast(out,ctypes.POINTER(w.BOOL))[0]=critical;return known
        def GetProcessInformation(self,h,kind,out,size):ctypes.cast(out,ctypes.POINTER(w.DWORD))[0]=protection;return True
    monkeypatch.setattr(n,'_token',lambda *args:b'synthetic-SID')
    with pytest.raises(n.ProcessNativeError,match=expected):n._security(K(),None,2)


def test_mock_other_sid_fail_closed(monkeypatch):
    k=SimpleNamespace(GetCurrentProcess=lambda:1)
    monkeypatch.setattr(n,'_token',lambda k,a,h:b'synthetic-A' if h==1 else b'synthetic-B')
    with pytest.raises(n.ProcessNativeError,match='PROCESS_USER'):n._security(k,None,2)


@pytest.mark.parametrize('elevated,rid',[(1,0x2000),(0,0x3000),(0,0x4000)])
def test_mock_elevation_and_high_integrity_rejected(monkeypatch,elevated,rid):
    sid=ctypes.create_string_buffer(b'synthetic');ptr=ctypes.create_string_buffer(struct.pack('P',ctypes.addressof(sid)))
    def data(a,t,kind):return ctypes.create_string_buffer(struct.pack('I',elevated)) if kind==20 else ptr
    monkeypatch.setattr(n,'_token_data',data)
    count=ctypes.c_ubyte(1);integrity=w.DWORD(rid)
    a=SimpleNamespace(OpenProcessToken=lambda *args:True,IsValidSid=lambda sid:True,GetLengthSid=lambda sid:8,GetSidSubAuthorityCount=lambda sid:ctypes.pointer(count),GetSidSubAuthority=lambda sid,i:ctypes.pointer(integrity))
    k=SimpleNamespace(CloseHandle=lambda h:True)
    with pytest.raises(n.ProcessNativeError,match='PROCESS_ELEVATED'):n._token(k,a,1)


def test_mock_existing_job_rejected(monkeypatch):
    class K:
        def GetCurrentProcess(self):return 1
        def IsProcessCritical(self,h,out):return True
        def GetProcessInformation(self,h,kind,out,size):ctypes.cast(out,ctypes.POINTER(w.DWORD))[0]=n.PROTECTION_LEVEL_NONE;return True
        def IsProcessInJob(self,h,j,out):ctypes.cast(out,ctypes.POINTER(w.BOOL))[0]=True;return True
    monkeypatch.setattr(n,'_token',lambda *args:b'synthetic-SID')
    with pytest.raises(n.ProcessNativeError,match='PROCESS_JOB'):n._security(K(),None,2)


def test_current_ancestor_and_named_orvia_keys_rejected():
    for pid,name in ((os.getpid(),'python.exe'),(os.getppid(),'synthetic.exe'),(123456,'electron.exe'),(123456,'orvia.exe')):
        with pytest.raises(n.ProcessNativeError,match='PROCESS_KEY'):n._key_process(pid,134000000000000001,name)


def test_real_changed_hash_blocks_launch_before_create(private_python,tmp_path):
    with pytest.raises(n.ProcessNativeError,match='PROCESS_CHANGED'):
        n.launch(str(private_python),[],str(tmp_path),0,sha256='0'*64)


def test_list_count_and_bytes_bound_synthetic_rows(monkeypatch):
    k,calls=fake_kernel();k.GetCurrentProcess=lambda:1
    monkeypatch.setattr(n,'_api',lambda:(k,None,None));monkeypatch.setattr(n,'_token',lambda *args:b'synthetic-SID')
    monkeypatch.setattr(n.psutil,'pids',lambda:range(10000,10100))
    monkeypatch.setattr(n,'_identity',lambda *a,**kw:fake_identity())
    value=n.list()
    assert len(value['processes'])==50 and value['truncated'] and len(json.dumps(value).encode())<=49152


def test_pid_without_exact_ticks_cannot_action():
    identity=fake_identity();identity.pop('creation_ticks')
    with pytest.raises(n.ProcessNativeError,match='PROCESS_IDENTITY'):n.terminate(identity,0)


def test_list_scan_2000_bound_with_synthetic_denied_targets(monkeypatch):
    k,calls=fake_kernel();k.GetCurrentProcess=lambda:1
    monkeypatch.setattr(n,'_api',lambda:(k,None,None));monkeypatch.setattr(n,'_token',lambda *args:b'synthetic-SID')
    monkeypatch.setattr(n.psutil,'pids',lambda:range(10000,14000))
    def denied(*args,**kw):raise n.ProcessNativeError('PROCESS_KEY','合成拒绝')
    monkeypatch.setattr(n,'_identity',denied)
    value=n.list()
    assert value['processes']==[] and value['truncated']
    assert len([c for c in calls if c[0]=='open'])==2000


def test_list_scan_2_second_budget_with_synthetic_clock(monkeypatch):
    k,calls=fake_kernel();k.GetCurrentProcess=lambda:1;clock=[0.0]
    monkeypatch.setattr(n,'_api',lambda:(k,None,None));monkeypatch.setattr(n,'_token',lambda *args:b'synthetic-SID')
    monkeypatch.setattr(n.psutil,'pids',lambda:range(10000,14000));monkeypatch.setattr(n,'monotonic',lambda:clock[0])
    def delayed(*args,**kw):clock[0]+=.8;return fake_identity()
    monkeypatch.setattr(n,'_identity',delayed)
    value=n.list()
    assert len(value['processes'])==3 and value['truncated']


def test_list_utf8_48k_cap_with_synthetic_long_names(monkeypatch):
    k,calls=fake_kernel();k.GetCurrentProcess=lambda:1
    monkeypatch.setattr(n,'_api',lambda:(k,None,None));monkeypatch.setattr(n,'_token',lambda *args:b'synthetic-SID')
    monkeypatch.setattr(n.psutil,'pids',lambda:range(10000,10100))
    monkeypatch.setattr(n,'_identity',lambda *args,**kw:{**fake_identity(),'executable':'C:\\'+'合成'*450+'.exe'})
    value=n.list()
    assert len(value['processes'])<50 and value['truncated']
    assert len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf-8'))<=49152


def test_actual_hash_cache_changed_stat_invalidates(private_python):
    old=n._hash(private_python,fresh=False)
    with private_python.open('ab') as stream:stream.write(b'synthetic-not-for-execution')
    assert n._hash(private_python,fresh=False)!=old


def test_launch_last_cwd_check_rejects_before_create(private_python,tmp_path,monkeypatch):
    calls=[]
    class Policy:
        def __init__(self,path):pass
        def resolve(self,*args):
            calls.append(1)
            if len(calls)>1:raise n.ToolError('permission_denied','合成目录更换')
            return tmp_path
    import _winapi
    monkeypatch.setattr(n,'PathPolicy',Policy)
    monkeypatch.setattr(_winapi,'CreateProcess',lambda *args:pytest.fail('目录变化不应启动'))
    with pytest.raises(n.ProcessNativeError,match='PROCESS_CWD'):n.launch(str(private_python),[],str(tmp_path))


def test_real_suspended_identity_refusal_reaps_only_unreleased_new_process(private_python,tmp_path,monkeypatch):
    original=n._identity;pid=[];marker=tmp_path/'synthetic.json'
    def refuse(*args,**kwargs):
        identity=original(*args,**kwargs);pid.append(identity['pid'])
        raise n.ProcessNativeError('PROCESS_PROTECTED','合成启动身份拒绝')
    monkeypatch.setattr(n,'_identity',refuse)
    with pytest.raises(n.ProcessNativeError,match='PROCESS_PROTECTED'):
        launched(private_python,tmp_path,'sleep')
    assert len(pid)==1 and not marker.exists()
    deadline=time.monotonic()+2
    while psutil.pid_exists(pid[0]) and time.monotonic()<deadline:time.sleep(.02)
    assert not psutil.pid_exists(pid[0])


def test_terminate_api_false_is_unknown_never_safe_success(monkeypatch):
    identity=fake_identity();k,calls=fake_kernel();k.TerminateProcess=lambda h,c:False
    monkeypatch.setattr(n,'_api',lambda:(k,None,None));monkeypatch.setattr(n,'_identity',lambda *args,**kw:identity)
    monkeypatch.setattr(n,'_security',lambda *a,**kw:None)
    value=n.terminate(identity,0)
    assert value['state']=='unknown' and value['exit_code'] is None


def test_missing_exit_code_even_signaled_is_unknown(monkeypatch):
    k,calls=fake_kernel();k.WaitForSingleObject=lambda h,ms:0;k.GetExitCodeProcess=lambda *args:False
    assert n._result(k,111,fake_identity(),0)['state']=='unknown'


def test_unknown_protection_query_rejected(monkeypatch):
    class K:
        def GetCurrentProcess(self):return 1
        def IsProcessCritical(self,h,out):return True
        def GetProcessInformation(self,*args):return False
    monkeypatch.setattr(n,'_token',lambda *args:b'synthetic-SID')
    with pytest.raises(n.ProcessNativeError,match='PROCESS_PROTECTED'):n._security(K(),None,2)


def test_inspect_missing_exact_creation_binding_refuses_before_open(monkeypatch):
    monkeypatch.setattr(n,'_api',lambda:pytest.fail('不应打开目标'))
    with pytest.raises(n.ProcessNativeError,match='PROCESS_IDENTITY'):n.inspect(123456,1.0,None)


def test_permission_change_after_hash_refuses_before_termination(monkeypatch):
    identity=fake_identity();k,calls=fake_kernel();monkeypatch.setattr(n,'_api',lambda:(k,None,None));monkeypatch.setattr(n,'_identity',lambda *a,**kw:identity)
    def elevated(*args,**kw):raise n.ProcessNativeError('PROCESS_ELEVATED','合成hash期间权限变化')
    monkeypatch.setattr(n,'_security',elevated)
    with pytest.raises(n.ProcessNativeError,match='PROCESS_ELEVATED'):n.terminate(identity,0)
    assert not any(c[0]=='terminate' for c in calls)


def test_real_restore_precise_native_launch_source_after_memory_loss(private_python,tmp_path):
    result,marker=launched(private_python,tmp_path,'sleep');identity=result['identity']
    try:
        ready(marker)
        with n._lock:n._owned.discard((identity['pid'],identity['creation_ticks']))
        with pytest.raises(n.ProcessNativeError,match='PROCESS_KEY'):
            n.inspect(identity['pid'],identity['create_time'],identity['creation_ticks'])
        # 此入口只代表可信服务拿到上方实际原生launch事实；它没有终止/关闭作用。
        assert n.restore_launched(identity)==identity and psutil.pid_exists(identity['pid'])
        assert n.inspect(identity['pid'],identity['create_time'],identity['creation_ticks'])==identity
        assert n.terminate(identity,2)['state']=='exited'
    finally:cleanup(identity)


def test_restore_stale_ticks_cannot_register_ownership(monkeypatch):
    identity=fake_identity();k,calls=fake_kernel();monkeypatch.setattr(n,'_api',lambda:(k,None,None))
    monkeypatch.setattr(n,'_identity',lambda *a,**kw:{**identity,'creation_ticks':'134000000000000002'})
    with pytest.raises(n.ProcessNativeError,match='PROCESS_CHANGED'):n.restore_launched(identity)
    with n._lock:assert (identity['pid'],identity['creation_ticks']) not in n._owned


@pytest.mark.parametrize('kind',[26,29])
def test_mock_appcontainer_and_uiaccess_are_not_ordinary(monkeypatch,kind):
    sid=ctypes.create_string_buffer(b'synthetic');ptr=ctypes.create_string_buffer(struct.pack('P',ctypes.addressof(sid)))
    def data(a,t,requested):
        return ctypes.create_string_buffer(struct.pack('I',int(requested==kind))) if requested in (20,26,29) else ptr
    monkeypatch.setattr(n,'_token_data',data)
    count=ctypes.c_ubyte(1);integrity=w.DWORD(0x2000)
    a=SimpleNamespace(OpenProcessToken=lambda *args:True,IsValidSid=lambda sid:True,GetLengthSid=lambda sid:8,GetSidSubAuthorityCount=lambda sid:ctypes.pointer(count),GetSidSubAuthority=lambda sid,i:ctypes.pointer(integrity))
    k=SimpleNamespace(CloseHandle=lambda h:True)
    with pytest.raises(n.ProcessNativeError,match='PROCESS_ISOLATED'):n._token(k,a,1)


def test_mock_unreadable_appcontainer_or_uiaccess_fail_closed(monkeypatch):
    sid=ctypes.create_string_buffer(b'synthetic');ptr=ctypes.create_string_buffer(struct.pack('P',ctypes.addressof(sid)))
    def data(a,t,kind):
        if kind==29:raise n.ProcessNativeError('PROCESS_TOKEN','合成未知隔离状态')
        return ctypes.create_string_buffer(struct.pack('I',0)) if kind==20 else ptr
    monkeypatch.setattr(n,'_token_data',data)
    count=ctypes.c_ubyte(1);integrity=w.DWORD(0x2000)
    a=SimpleNamespace(OpenProcessToken=lambda *args:True,IsValidSid=lambda sid:True,GetLengthSid=lambda sid:8,GetSidSubAuthorityCount=lambda sid:ctypes.pointer(count),GetSidSubAuthority=lambda sid,i:ctypes.pointer(integrity))
    with pytest.raises(n.ProcessNativeError,match='PROCESS_TOKEN'):n._token(SimpleNamespace(CloseHandle=lambda h:True),a,1)


@pytest.mark.parametrize('pid',['self','ancestor'])
def test_real_restore_source_never_bypasses_current_or_ancestor_key(pid):
    identity={**fake_identity(),'pid':os.getpid() if pid=='self' else os.getppid()}
    with pytest.raises(n.ProcessNativeError,match='PROCESS_KEY'):n.restore_launched(identity)


def test_real_unregistered_backend_worker_remains_protected(private_python,tmp_path):
    import subprocess
    fixture=Path(__file__).with_name('v4_process_fixture.py').resolve();marker=tmp_path/'worker.json'
    env={key:os.environ[key] for key in ('SystemRoot','WINDIR','TEMP','TMP') if key in os.environ}
    process=subprocess.Popen([str(private_python),'-I','-u',str(fixture),'sleep',str(marker)],cwd=tmp_path,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        assert ready(marker)['pid']==process.pid
        k,a,u=n._api();handle=k.OpenProcess(n.QUERY|n.SYNC,False,process.pid)
        try:ticks=n._ticks(k,handle)
        finally:k.CloseHandle(handle)
        with pytest.raises(n.ProcessNativeError,match='PROCESS_KEY'):
            n.inspect(process.pid,(ticks-n.EPOCH)/1e7,str(ticks))
    finally:
        # 仅自有合成Popen的原始HANDLE收尾；不操作任何用户已有进程。
        process.terminate();process.wait(timeout=3)
