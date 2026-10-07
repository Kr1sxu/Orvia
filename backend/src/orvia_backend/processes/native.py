"""V4-009 Windows普通进程原生层；没有提权、递归终止或关闭升级。"""
import builtins
from contextlib import contextmanager
import ctypes
from ctypes import wintypes as w
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import threading
from time import monotonic
import psutil
from ..computer.paths import ToolError,PathPolicy


class ProcessNativeError(ToolError):
    """稳定错误码，不回传SID、命令行、环境或私有系统异常。"""


QUERY=0x1000;SYNC=0x100000;TERMINATE=1
PROTECTION_LEVEL_NONE=0xfffffffe
EPOCH=116444736000000000
_cache={};_owned=set();_lock=threading.RLock()
DENIED_NAMES={'orvia.exe','orvia-backend.exe','electron.exe','system','registry','smss.exe','csrss.exe','wininit.exe','services.exe','lsass.exe','winlogon.exe','svchost.exe','explorer.exe','dwm.exe','fontdrvhost.exe','audiodg.exe'}


def _api():
    if os.name!='nt':raise ProcessNativeError('PROCESS_PLATFORM','进程管理仅支持Windows')
    k=ctypes.WinDLL('kernel32',use_last_error=True);a=ctypes.WinDLL('advapi32',use_last_error=True);u=ctypes.WinDLL('user32',use_last_error=True)
    signatures={
        'OpenProcess':([w.DWORD,w.BOOL,w.DWORD],w.HANDLE),'CloseHandle':([w.HANDLE],w.BOOL),
        'GetCurrentProcess':([],w.HANDLE),'GetProcessId':([w.HANDLE],w.DWORD),
        'GetProcessTimes':([w.HANDLE,*([ctypes.POINTER(w.FILETIME)]*4)],w.BOOL),
        'QueryFullProcessImageNameW':([w.HANDLE,w.DWORD,w.LPWSTR,ctypes.POINTER(w.DWORD)],w.BOOL),
        'IsProcessCritical':([w.HANDLE,ctypes.POINTER(w.BOOL)],w.BOOL),
        'GetProcessInformation':([w.HANDLE,ctypes.c_int,w.LPVOID,w.DWORD],w.BOOL),
        'WaitForSingleObject':([w.HANDLE,w.DWORD],w.DWORD),'GetExitCodeProcess':([w.HANDLE,ctypes.POINTER(w.DWORD)],w.BOOL),
        'TerminateProcess':([w.HANDLE,w.UINT],w.BOOL),'ResumeThread':([w.HANDLE],w.DWORD),
        'IsProcessInJob':([w.HANDLE,w.HANDLE,ctypes.POINTER(w.BOOL)],w.BOOL)}
    for name,(args,result) in signatures.items():
        try:fn=getattr(k,name)
        except AttributeError:raise ProcessNativeError('PROCESS_API','系统缺少必要保护核验接口，能力关闭') from None
        fn.argtypes=args;fn.restype=result
    for name,args,result in (
        ('OpenProcessToken',[w.HANDLE,w.DWORD,ctypes.POINTER(w.HANDLE)],w.BOOL),
        ('GetTokenInformation',[w.HANDLE,ctypes.c_int,w.LPVOID,w.DWORD,ctypes.POINTER(w.DWORD)],w.BOOL),
        ('GetLengthSid',[w.LPVOID],w.DWORD),('IsValidSid',[w.LPVOID],w.BOOL),
        ('GetSidSubAuthorityCount',[w.LPVOID],ctypes.POINTER(ctypes.c_ubyte)),
        ('GetSidSubAuthority',[w.LPVOID,w.DWORD],ctypes.POINTER(w.DWORD))):
        fn=getattr(a,name);fn.argtypes=args;fn.restype=result
    u.GetWindowThreadProcessId.argtypes=[w.HWND,ctypes.POINTER(w.DWORD)];u.GetWindowThreadProcessId.restype=w.DWORD
    u.PostMessageW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM];u.PostMessageW.restype=w.BOOL
    return k,a,u


def _token_data(a,token,kind):
    needed=w.DWORD()
    a.GetTokenInformation(token,kind,None,0,ctypes.byref(needed))
    if not 1<=needed.value<=16384:raise ProcessNativeError('PROCESS_TOKEN','令牌信息不可核验')
    data=ctypes.create_string_buffer(needed.value)
    if not a.GetTokenInformation(token,kind,data,needed.value,ctypes.byref(needed)):
        raise ProcessNativeError('PROCESS_TOKEN','令牌信息不可核验')
    return data


def _token(k,a,handle):
    """SID只在内存比较；同时拒绝提升令牌及High以上完整性，未知也拒绝。"""
    token=w.HANDLE()
    if not a.OpenProcessToken(handle,8,ctypes.byref(token)):raise ProcessNativeError('PROCESS_TOKEN','进程令牌不可读取')
    try:
        owner=_token_data(a,token,1);sid=ctypes.cast(owner,ctypes.POINTER(ctypes.c_void_p))[0]
        if not sid or not a.IsValidSid(sid):raise ProcessNativeError('PROCESS_TOKEN','进程用户身份不可核验')
        length=a.GetLengthSid(sid)
        if not 8<=length<=256:raise ProcessNativeError('PROCESS_TOKEN','进程用户身份不可核验')
        sid_bytes=ctypes.string_at(sid,length)
        elevation=_token_data(a,token,20)
        label=_token_data(a,token,25);label_sid=ctypes.cast(label,ctypes.POINTER(ctypes.c_void_p))[0]
        if not label_sid or not a.IsValidSid(label_sid):raise ProcessNativeError('PROCESS_TOKEN','完整性级别不可核验')
        count=a.GetSidSubAuthorityCount(label_sid)[0]
        if not 1<=count<=15:raise ProcessNativeError('PROCESS_TOKEN','完整性级别不可核验')
        integrity=a.GetSidSubAuthority(label_sid,count-1)[0]
        if ctypes.cast(elevation,ctypes.POINTER(w.DWORD))[0] or integrity>=0x3000:
            raise ProcessNativeError('PROCESS_ELEVATED','提权或High完整性进程不能管理')
        app_container=_token_data(a,token,29);ui_access=_token_data(a,token,26)
        if len(app_container)<4 or len(ui_access)<4:
            raise ProcessNativeError('PROCESS_TOKEN','隔离/UIAccess令牌状态不可核验')
        if ctypes.cast(app_container,ctypes.POINTER(w.DWORD))[0] or ctypes.cast(ui_access,ctypes.POINTER(w.DWORD))[0]:
            raise ProcessNativeError('PROCESS_ISOLATED','AppContainer或UIAccess进程不属于普通进程管理范围')
        return sid_bytes
    finally:k.CloseHandle(token)


def _security(k,a,handle,*,permit_job=False):
    if _token(k,a,k.GetCurrentProcess())!=_token(k,a,handle):
        raise ProcessNativeError('PROCESS_USER','目标不是当前普通用户进程')
    critical=w.BOOL();protection=w.DWORD()
    if not k.IsProcessCritical(handle,ctypes.byref(critical)) or critical.value:
        raise ProcessNativeError('PROCESS_CRITICAL','关键进程或关键状态不可核验')
    if not k.GetProcessInformation(handle,7,ctypes.byref(protection),ctypes.sizeof(protection)) or protection.value!=PROTECTION_LEVEL_NONE:
        raise ProcessNativeError('PROCESS_PROTECTED','受保护进程或保护状态不可核验')
    in_job=w.BOOL()
    if not k.IsProcessInJob(handle,None,ctypes.byref(in_job)) or (in_job.value and not permit_job):
        raise ProcessNativeError('PROCESS_JOB','已有受控Job或Job状态不明的目标不能接管')


def _stat(path):
    try:
        path=Path(path)
        if not path.is_absolute() or len(str(path))>1000 or path.suffix.lower()!='.exe':raise ValueError
        for item in (path,*path.parents):
            st=item.lstat()
            if stat.S_ISLNK(st.st_mode) or getattr(st,'st_file_attributes',0)&0x400:raise ValueError
        st=path.stat()
        if not stat.S_ISREG(st.st_mode) or not 0<st.st_size<=64*1024*1024:raise ValueError
        return path,(st.st_size,st.st_mtime_ns,st.st_ino,st.st_ctime_ns)
    except (OSError,ValueError,TypeError):raise ProcessNativeError('PROCESS_EXE','程序必须是可核验且无重解析点的普通绝对.exe文件') from None


def _hash(path,*,fresh=True,deadline=None):
    path,key=_stat(path);cache_key=(str(path).casefold(),key)
    with _lock:cached=_cache.get(cache_key)
    if cached and not fresh:return cached
    digest=hashlib.sha256()
    try:
        with path.open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):
                if deadline is not None and monotonic()>=deadline:raise ProcessNativeError('PROCESS_BUDGET','进程扫描时间预算耗尽')
                digest.update(block)
    except OSError:raise ProcessNativeError('PROCESS_EXE','程序内容不可读取') from None
    if _stat(path)[1]!=key:raise ProcessNativeError('PROCESS_CHANGED','程序核验期间身份变化')
    value=digest.hexdigest()
    with _lock:
        if len(_cache)>=128:_cache.clear()
        _cache[cache_key]=value
    return value


def executable(path):
    """程序预览只提供可执行身份；不能由程序路径或名称授予执行权限。"""
    path,_=_stat(path)
    if path.name.casefold() in DENIED_NAMES:raise ProcessNativeError('PROCESS_KEY','系统或Orvia关键程序不能启动')
    return {'name':path.name,'executable':str(path),'sha256':_hash(path)}


def _ticks(k,handle):
    times=[w.FILETIME() for _ in range(4)]
    if not k.GetProcessTimes(handle,*map(ctypes.byref,times)):raise ProcessNativeError('PROCESS_IDENTITY','创建时间不可核验')
    ticks=(times[0].dwHighDateTime<<32)|times[0].dwLowDateTime
    if ticks<=EPOCH:raise ProcessNativeError('PROCESS_IDENTITY','创建时间无效')
    return ticks


def _key_process(pid,ticks,name,*,new=False):
    if pid<=4 or pid==os.getpid() or name.casefold() in DENIED_NAMES:
        raise ProcessNativeError('PROCESS_KEY','自身、系统或Orvia关键进程不能管理')
    try:
        ancestors=psutil.Process(os.getpid()).parents()
        if pid in {p.pid for p in ancestors}:raise ProcessNativeError('PROCESS_KEY','Orvia祖先进程不能管理')
        target_parents=psutil.Process(pid).parents()
        if not new and os.getpid() in {p.pid for p in target_parents}:
            # 自有后端子进程默认保护，只有本模块已核验启动的普通应用链可管理。
            with _lock:owned=builtins.list(_owned)
            allowed=any(p==pid and t==str(ticks) for p,t in owned)
            if not allowed:raise ProcessNativeError('PROCESS_KEY','Orvia自有关键子进程不能管理')
    except psutil.Error:raise ProcessNativeError('PROCESS_IDENTITY','进程关系不可核验') from None


def _identity(k,a,handle,*,fresh=True,deadline=None,new=False):
    pid=k.GetProcessId(handle)
    if not pid:raise ProcessNativeError('PROCESS_IDENTITY','目标句柄身份不可读取')
    ticks=_ticks(k,handle);buffer=ctypes.create_unicode_buffer(1001);size=w.DWORD(1001)
    if not k.QueryFullProcessImageNameW(handle,0,buffer,ctypes.byref(size)):raise ProcessNativeError('PROCESS_IDENTITY','目标程序身份不可读取')
    path=Path(buffer.value);_key_process(pid,ticks,path.name,new=new)
    with _lock:owned=(pid,str(ticks)) in _owned
    _security(k,a,handle,permit_job=new or owned)
    sha=_hash(path,fresh=fresh,deadline=deadline)
    if _ticks(k,handle)!=ticks:raise ProcessNativeError('PROCESS_CHANGED','目标创建身份变化')
    return {'pid':pid,'name':path.name,'executable':str(path),'create_time':(ticks-EPOCH)/1e7,'creation_ticks':str(ticks),'sha256':sha}


def _pid(pid):
    if type(pid) is not int or not 4<pid<0xffffffff:raise ProcessNativeError('PROCESS_PID','PID无效')
    return pid


def inspect(pid,create_time,creation_ticks):
    """只能核对列表已有的准确创建身份；不接受只给PID的目标预览。"""
    if type(create_time) not in (int,float) or not math.isfinite(create_time) or not isinstance(creation_ticks,str) or not re.fullmatch(r'[1-9][0-9]{16,19}',creation_ticks):
        raise ProcessNativeError('PROCESS_IDENTITY','检查必须携带精确创建身份')
    k,a,_=_api();handle=k.OpenProcess(QUERY|SYNC,False,_pid(pid))
    if not handle:raise ProcessNativeError('PROCESS_UNAVAILABLE','目标已退出或身份不可读取')
    try:
        value=_identity(k,a,handle)
        if value['create_time']!=create_time:raise ProcessNativeError('PROCESS_CHANGED','目标创建时间变化')
        if value['creation_ticks']!=creation_ticks:raise ProcessNativeError('PROCESS_CHANGED','目标精确创建身份变化')
        return value
    finally:k.CloseHandle(handle)


def restore_launched(identity):
    """仅可信服务从SQLite已核验launch事实恢复来源登记，不授予任何动作审批。

    未知/取消来源不得调用此入口；renderer、Skills和模型不能指定恢复资格。
    同一HANDLE fresh核验全部身份，Job特例只给准确已启动目标；关键PID仍拒绝。
    """
    _exact(identity);k,a,_=_api();handle=k.OpenProcess(QUERY|SYNC,False,identity['pid'])
    if not handle:raise ProcessNativeError('PROCESS_UNAVAILABLE','已启动目标已退出或不可核验')
    try:
        actual=_identity(k,a,handle,new=True)
        if actual!=identity:raise ProcessNativeError('PROCESS_CHANGED','原生launch来源身份变化，不能恢复登记')
        _security(k,a,handle,permit_job=True)
        with _lock:
            if len(_owned)>=256:_owned.clear()
            _owned.add((identity['pid'],identity['creation_ticks']))
        return actual
    finally:k.CloseHandle(handle)


def list():
    """最多扫描2000项/2秒，只发送50个普通同用户身份，超额明确truncated。"""
    values=[];truncated=False;deadline=monotonic()+2;budget=0
    try:
        k,a,_=_api();_token(k,a,k.GetCurrentProcess())
    except ToolError as exc:return {'processes':[],'truncated':False,'unavailable_reason':exc.message}
    try:
        for index,pid in enumerate(psutil.pids()):
            if index>=2000 or monotonic()>=deadline or len(values)>=50:truncated=True;break
            handle=k.OpenProcess(QUERY|SYNC,False,pid)
            if not handle:continue
            try:
                value=_identity(k,a,handle,fresh=False,deadline=deadline)
                encoded=len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf-8'))
                if budget+encoded>48*1024-256:truncated=True;break
                values.append(value);budget+=encoded+1
            except ToolError as exc:
                if exc.code=='PROCESS_BUDGET':truncated=True;break
            finally:k.CloseHandle(handle)
    except psutil.Error:truncated=True
    return {'processes':values,'truncated':truncated,'unavailable_reason':None}


def _wait_seconds(value):
    if type(value) is not int or not 0<=value<=15:raise ProcessNativeError('PROCESS_BUDGET','等待预算必须为0～15秒')
    return value


def _result(k,handle,identity,seconds,close_sent=False):
    outcome=k.WaitForSingleObject(handle,_wait_seconds(seconds)*1000)
    code=w.DWORD();state='unknown';exit_code=None
    if outcome==0 and k.GetExitCodeProcess(handle,ctypes.byref(code)):state='exited';exit_code=code.value
    elif outcome==258:state='running'
    return {'identity':identity,'state':state,'exit_code':exit_code,'close_sent':close_sent}


def _exact(identity):
    if type(identity) is not dict or set(identity)!={'pid','name','executable','create_time','creation_ticks','sha256'}:
        raise ProcessNativeError('PROCESS_IDENTITY','动作必须绑定完整进程身份')
    _pid(identity['pid'])
    if type(identity['create_time']) not in (int,float) or not math.isfinite(identity['create_time']) or not isinstance(identity['creation_ticks'],str) or not re.fullmatch(r'[1-9][0-9]{16,19}',identity['creation_ticks']):raise ProcessNativeError('PROCESS_IDENTITY','创建身份字段无效')


@contextmanager
def _target(identity,rights=0):
    """每个动作只打开一次句柄；完成复核后所有等待/信号操作沿用该HANDLE。"""
    _exact(identity);k,a,u=_api();handle=k.OpenProcess(QUERY|SYNC|rights,False,identity['pid'])
    if not handle:raise ProcessNativeError('PROCESS_UNAVAILABLE','目标已退出或授权访问不可用')
    try:
        actual=_identity(k,a,handle)
        if actual!=identity:raise ProcessNativeError('PROCESS_CHANGED','PID、精确创建时间或可执行身份变化，旧批准失效')
        with _lock:owned=(identity['pid'],identity['creation_ticks']) in _owned
        # SHA读取完成后仍在同一HANDLE上紧贴动作复核普通权限/保护状态。
        _security(k,a,handle,permit_job=owned)
        yield k,a,u,handle
    finally:k.CloseHandle(handle)


def wait(identity,wait_seconds=2):
    """等待只观察该句柄退出，不取消、不终止、超时仍运行。"""
    _wait_seconds(wait_seconds)
    with _target(identity) as (k,a,u,handle):return _result(k,handle,identity,wait_seconds)


def close(identity,wait_seconds=2):
    """向目标的顶层窗口投递WM_CLOSE；不读取标题，不能因未退出自动强杀。"""
    _wait_seconds(wait_seconds)
    with _target(identity) as (k,a,u,handle):
        sent=False;count=0
        callback_type=ctypes.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
        def visit(hwnd,param):
            nonlocal sent,count
            if count>=2000:return False
            count+=1;pid=w.DWORD();u.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
            if pid.value==identity['pid'] and k.WaitForSingleObject(handle,0)==258:
                # HWND发送前再查所属PID，不广播，不发送WM_QUIT/其它应用命令。
                again=w.DWORD();u.GetWindowThreadProcessId(hwnd,ctypes.byref(again))
                if again.value==identity['pid']:sent=bool(u.PostMessageW(hwnd,0x10,0,0)) or sent
            return True
        callback=callback_type(visit);u.EnumWindows.argtypes=[callback_type,w.LPARAM];u.EnumWindows.restype=w.BOOL
        u.EnumWindows(callback,0)
        return _result(k,handle,identity,wait_seconds,sent)


def terminate(identity,wait_seconds=2):
    """仅独立批准的准确句柄单目标TerminateProcess；不递归、不能通用撤销。"""
    _wait_seconds(wait_seconds)
    with _target(identity,TERMINATE) as (k,a,u,handle):
        if k.WaitForSingleObject(handle,0)==258 and not k.TerminateProcess(handle,0xE009):
            return {'identity':identity,'state':'unknown','exit_code':None,'close_sent':False}
        return _result(k,handle,identity,wait_seconds)


def launch(executable_path,args,cwd,wait_seconds=0,*,sha256=None):
    """普通CreateProcess挂起后复核实际句柄再恢复；已释放应用不会被超时/服务关闭杀死。"""
    _wait_seconds(wait_seconds);program=executable(executable_path)
    if sha256 is not None and program['sha256']!=sha256:raise ProcessNativeError('PROCESS_CHANGED','批准程序内容变化')
    if type(args) is not builtins.list or len(args)>16 or any(not isinstance(arg,str) or len(arg)>1000 or '\x00' in arg for arg in args) or sum(len(arg.encode('utf-8')) for arg in args)>8192:
        raise ProcessNativeError('PROCESS_ARGS','参数超过16项/8KiB或包含无效字符')
    try:cwd_policy=PathPolicy(str(cwd));cwd=cwd_policy.resolve('.','directory')
    except ToolError:raise ProcessNativeError('PROCESS_CWD','工作目录必须是准确且无重解析点的普通绝对目录') from None
    k,a,_=_api();_token(k,a,k.GetCurrentProcess());import _winapi
    env={key:os.environ[key] for key in ('SystemRoot','WINDIR','TEMP','TMP','COMSPEC') if key in os.environ}
    env['PATH']=str(Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32')+os.pathsep+str(Path(program['executable']).parent)
    env['PYTHONUTF8']='1';env['PYTHONUNBUFFERED']='1'
    handle=None;thread=None;released=False
    try:
        try:cwd=cwd_policy.resolve('.','directory')
        except ToolError:raise ProcessNativeError('PROCESS_CWD','启动前工作目录身份已变化') from None
        handle,thread,pid,_=_winapi.CreateProcess(program['executable'],subprocess.list2cmdline([program['executable'],*args]),None,None,False,subprocess.CREATE_NO_WINDOW|0x4|0x400,env,str(cwd),subprocess.STARTUPINFO())
        identity=_identity(k,a,handle,new=True)
        if identity['executable'].casefold()!=program['executable'].casefold() or identity['sha256']!=program['sha256']:
            raise ProcessNativeError('PROCESS_CHANGED','挂起新进程的程序身份不符合批准')
        if k.ResumeThread(thread)==0xffffffff:raise ProcessNativeError('PROCESS_LAUNCH','受控新进程无法恢复')
        released=True
        with _lock:
            if len(_owned)>=256:_owned.clear()
            _owned.add((identity['pid'],identity['creation_ticks']))
        return _result(k,handle,identity,wait_seconds)
    except (OSError,ValueError):raise ProcessNativeError('PROCESS_LAUNCH','程序不能以普通权限启动，不自动重试') from None
    finally:
        reaped=True
        if handle and not released:
            k.TerminateProcess(handle,0xE009)
            reaped=k.WaitForSingleObject(handle,2000)==0
        if thread:k.CloseHandle(thread)
        if handle:k.CloseHandle(handle)
        if not reaped:raise ProcessNativeError('PROCESS_UNKNOWN','未释放新进程回收无法核验，结果未知')
