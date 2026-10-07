"""V4-008：固定已安装Shell检测和普通令牌Job执行；没有LPAC或系统副作用撤销。"""
import asyncio
import base64
import ctypes
from ctypes import wintypes as w
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import stat
from time import monotonic
from uuid import uuid4
from ..computer.paths import ToolError
from ..mcp.transport import _JobProcess

OUTPUT_LIMIT=16*1024
class ShellRuntimeError(ToolError):
    """稳定运行边界错误，不暴露私有脚本正文或系统异常路径。"""


def utc():return datetime.now(timezone.utc).isoformat()


def is_elevated():
    """核验当前后端TokenElevation；不得意外继承管理员令牌执行用户Shell。"""
    if os.name!='nt':raise ShellRuntimeError('SHELL_PLATFORM','当前Shell运行器仅支持Windows')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);advapi=ctypes.WinDLL('advapi32',use_last_error=True)
    kernel.GetCurrentProcess.restype=w.HANDLE
    kernel.CloseHandle.argtypes=[w.HANDLE];kernel.CloseHandle.restype=w.BOOL
    advapi.OpenProcessToken.argtypes=[w.HANDLE,w.DWORD,ctypes.POINTER(w.HANDLE)];advapi.OpenProcessToken.restype=w.BOOL
    advapi.GetTokenInformation.argtypes=[w.HANDLE,ctypes.c_int,w.LPVOID,w.DWORD,ctypes.POINTER(w.DWORD)];advapi.GetTokenInformation.restype=w.BOOL
    token=w.HANDLE();elevation=w.DWORD();needed=w.DWORD()
    if not advapi.OpenProcessToken(kernel.GetCurrentProcess(),0x8,ctypes.byref(token)):
        raise ShellRuntimeError('SHELL_TOKEN','无法核验普通权限令牌，运行能力关闭')
    try:
        if not advapi.GetTokenInformation(token,20,ctypes.byref(elevation),ctypes.sizeof(elevation),ctypes.byref(needed)):
            raise ShellRuntimeError('SHELL_TOKEN','无法核验令牌提升状态，运行能力关闭')
        return elevation.value!=0
    finally:kernel.CloseHandle(token)


def file_identity(path):
    """逐级拒绝reparse后固定实际exe SHA-256；版本信息不代替执行身份。"""
    path=Path(path)
    if not path.is_absolute() or len(str(path))>1000:raise ShellRuntimeError('SHELL_IDENTITY','解释器必须是明确绝对路径')
    try:
        for part in (path,*path.parents):
            info=part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise ShellRuntimeError('SHELL_IDENTITY','解释器路径含重解析点，不能执行')
        if not path.is_file() or path.suffix.lower()!='.exe':raise ShellRuntimeError('SHELL_MISSING','指定解释器未安装')
        if path.stat().st_size>64*1024*1024:raise ShellRuntimeError('SHELL_IDENTITY','解释器超过64MiB身份核验预算')
        before=path.stat();digest=hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
        after=path.stat()
        if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):raise ShellRuntimeError('SHELL_CHANGED','解释器核验期间身份变化')
        return digest.hexdigest()
    except OSError:raise ShellRuntimeError('SHELL_MISSING','解释器不可访问或未安装') from None


def candidates():
    windows=Path(os.environ.get('SystemRoot',r'C:\Windows'))
    return {
        'powershell':[Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe',Path(r'C:\Program Files\PowerShell\7\pwsh.exe')],
        'windows_powershell':[windows/'System32/WindowsPowerShell/v1.0/powershell.exe'],
        'git_bash':[Path(r'C:\Program Files\Git\bin\bash.exe')],
        'wsl':[windows/'System32/wsl.exe']}


async def _capture(config,timeout,cancel_event,*,encoding='utf-8',before_close=None,on_spawned=None,launch_guard=None):
    """单次启动、持续有界排空；原生创建取消后仍保留后到Job所有权并回收。"""
    started=utc();deadline=monotonic()+timeout;process=None
    if cancel_event.is_set():return {'state':'cancelled','exit_code':None,'stdout':'','stderr':'','stdout_truncated':False,'stderr_truncated':False,'children_reaped':True,'started_at':started,'finished_at':utc()}
    def launch():
        if launch_guard:launch_guard()
        return _JobProcess(config)
    spawn=asyncio.create_task(asyncio.to_thread(launch));tasks=[];buffers=[bytearray(),bytearray()];totals=[0,0]
    async def drain(stream,index):
        while True:
            try:block=await asyncio.to_thread(stream.read,4096)
            except (OSError,ValueError):return
            if not block:return
            totals[index]+=len(block)
            if len(buffers[index])<OUTPUT_LIMIT:buffers[index].extend(block[:OUTPUT_LIMIT-len(buffers[index])])
    async def cleanup():
        nonlocal process
        if process is None:
            try:process=await asyncio.shield(spawn)
            except BaseException:return {'children_reaped':False}
        result=await asyncio.to_thread(process.close)
        if tasks:await asyncio.gather(*tasks,return_exceptions=True)
        return result
    async def close_group():
        # Linux核验异常不能阻止Windows Job释放，也不能伪造children_reaped。
        if not before_close:return True
        try:return bool(await before_close())
        except (OSError,ValueError,ToolError):return False
    try:
        process=await asyncio.shield(spawn)
        tasks=[asyncio.create_task(drain(process.stdout,0)),asyncio.create_task(drain(process.stderr,1))]
        if on_spawned:await on_spawned(process)
        import _winapi
        state='completed';exit_code=None
        while True:
            if cancel_event.is_set():state='cancelled';break
            if monotonic()>=deadline:state='timeout';break
            if _winapi.WaitForSingleObject(process.handle,0)==0:
                code=_winapi.GetExitCodeProcess(process.handle)
                exit_code=code;state='completed' if code==0 else 'failed';break
            await asyncio.sleep(.02)
        group_reaped=await close_group()
        closed=await cleanup()
        closed['children_reaped']=bool(closed.get('children_reaped')) and group_reaped
        if not closed.get('children_reaped'):state='failed'
        texts=[];truncated=[]
        for index in range(2):
            full=buffers[index].decode(encoding,errors='replace').encode('utf-8')
            texts.append(full[:OUTPUT_LIMIT].decode('utf-8',errors='ignore'))
            truncated.append(totals[index]>OUTPUT_LIMIT or len(full)>OUTPUT_LIMIT)
        return {'state':state,'exit_code':exit_code,'stdout':texts[0],'stderr':texts[1],
                'stdout_truncated':truncated[0],'stderr_truncated':truncated[1],'children_reaped':bool(closed.get('children_reaped')),'started_at':started,'finished_at':utc()}
    except asyncio.CancelledError:
        try:
            await asyncio.shield(close_group())
        finally:await asyncio.shield(cleanup())
        raise
    except (OSError,ValueError,ToolError):
        try:
            await asyncio.shield(close_group())
        finally:await asyncio.shield(cleanup())
        raise ShellRuntimeError('SHELL_START','解释器无法受控启动或回收，结果未核验') from None


def _ps_quote(value):return "'"+str(value).replace("'","''")+"'"
def _windows_path(value):return str(Path(value)).replace('\\','/')


def _arguments(interpreter,script,cwd,output_root,input_root):
    """固定host只设置目录环境/UTF8再执行批准脚本文件，路径用字面量或argv传递。"""
    if interpreter['id'] in {'powershell','windows_powershell'}:
        command="$enc=New-Object System.Text.UTF8Encoding($false);[Console]::OutputEncoding=$enc;$OutputEncoding=$enc;"
        command+=f"$env:ORVIA_INPUT_DIR={_ps_quote(input_root)};$env:ORVIA_OUTPUT_DIR={_ps_quote(output_root)};"
        command+=f"try {{ & {_ps_quote(script)}; $ok=$?; $code=$LASTEXITCODE; if($null -ne $code){{exit [int]$code}}; if($ok){{exit 0}}else{{exit 1}} }} catch {{[Console]::Error.WriteLine($_.Exception.Message);exit 1}}"
        return ['-NoLogo','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-EncodedCommand',base64.b64encode(command.encode('utf-16-le')).decode('ascii')]
    if interpreter['id']=='git_bash':
        wrapper='export PATH="/usr/bin:/bin:$PATH"; export ORVIA_INPUT_DIR="$1" ORVIA_OUTPUT_DIR="$2"; exec "$0" --noprofile --norc "$3"'
        return ['--noprofile','--norc','-c',wrapper,_windows_path(interpreter['executable']),_windows_path(input_root),_windows_path(output_root),_windows_path(script)]
    raise ShellRuntimeError('SHELL_INTERPRETER','指定解释器不受当前运行器支持')


async def _probe(executable,args,timeout=5,*,encoding='utf-8'):
    return await _capture({'executable':str(executable),'args':args},timeout,asyncio.Event(),encoding=encoding)


def _row(identifier,label,path,version=None,sha=None,available=False,reason=None,distro=None):
    return {'id':identifier,'label':label,'executable':str(path),'version':version,'sha256':sha,'available':available,'reason':reason,'distro':distro}


def _distros(text):
    """只列本机已安装名字；Docker管理发行版和不明名称永不执行内部命令。"""
    names=[]
    for name in text.replace('\x00','').splitlines():
        name=name.strip().lstrip('\ufeff')
        if not name or name.casefold().startswith('docker-desktop'):continue
        if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_. -]{0,79}',name) and name not in names:names.append(name)
    return names[:8]


async def detect():
    """检测固定可信候选与普通令牌；缺环境只报告不可用，不安装或静默换Shell。"""
    rows=[];deadline=monotonic()+25
    try:elevated=is_elevated()
    except ShellRuntimeError:
        elevated=True
    labels={'powershell':'PowerShell 7','windows_powershell':'Windows PowerShell','git_bash':'Git Bash'}
    paths=candidates()
    for identifier in labels:
        path=next((candidate for candidate in paths[identifier] if candidate.is_file()),paths[identifier][0])
        try:
            sha=file_identity(path)
            if elevated:raise ShellRuntimeError('SHELL_ELEVATED','当前后端令牌已提升或无法核验普通权限，拒绝执行')
            args=['--version'] if identifier=='git_bash' else ['-NoLogo','-NoProfile','-NonInteractive','-Command','[Console]::OutputEncoding=[Text.UTF8Encoding]::new();$PSVersionTable.PSVersion.ToString()']
            remaining=deadline-monotonic()
            if remaining<=0:raise ShellRuntimeError('SHELL_DETECT_TIMEOUT','25秒总检测预算已耗尽')
            probe=await _probe(path,args,min(5,remaining))
            version=probe['stdout'].splitlines()[0][:200] if probe['stdout'].splitlines() else None
            if probe['state']!='completed' or not version or not probe['children_reaped']:raise ShellRuntimeError('SHELL_VERSION','解释器版本探测失败或超时')
            rows.append(_row(identifier,labels[identifier],path,version,sha,True))
        except ToolError as exc:rows.append(_row(identifier,labels[identifier],path,reason=exc.message))
    wsl=paths['wsl'][0]
    try:
        sha=file_identity(wsl)
        if elevated:raise ShellRuntimeError('SHELL_ELEVATED','当前后端令牌已提升，不能检测或执行WSL')
        remaining=deadline-monotonic()
        if remaining<=0:raise ShellRuntimeError('SHELL_DETECT_TIMEOUT','25秒总检测预算已耗尽')
        result=await _probe(wsl,['--list','--quiet'],min(5,remaining),encoding='utf-16-le')
        distributions=_distros(result['stdout'])
        if result['state']!='completed':raise ShellRuntimeError('SHELL_WSL','WSL发行版列表不可用')
        if not distributions:rows.append(_row('wsl:none','WSL',wsl,sha=sha,reason='没有适用的普通WSL发行版；Docker管理发行版已排除'))
        for distro in distributions:
            remaining=deadline-monotonic()
            row=await _detect_wsl(wsl,distro,sha,min(5,remaining)) if remaining>0 else _row('wsl:'+distro,'WSL · '+distro,wsl,sha=sha,distro=distro,reason='25秒总检测预算已耗尽')
            rows.append(row)
    except ToolError as exc:rows.append(_row('wsl:none','WSL',wsl,reason=exc.message))
    return {'interpreters':rows}


async def run(interpreter,script_path,cwd,timeout_seconds,cancel_event,output_root=None,*,input_root=None):
    """只消费服务已冻结批准的一次脚本文件；普通权限无网络/目录隔离保证。"""
    if is_elevated():raise ShellRuntimeError('SHELL_ELEVATED','当前后端持有管理员令牌，禁止运行Shell')
    if type(interpreter) is not dict or not interpreter.get('available') or type(timeout_seconds) is not int or not 1<=timeout_seconds<=60:
        raise ShellRuntimeError('SHELL_RUNTIME','解释器不可用或执行预算不是1～60秒')
    identifier=interpreter.get('id');path=Path(interpreter.get('executable',''))
    accepted=candidates()
    kind='wsl' if isinstance(identifier,str) and identifier.startswith('wsl:') else identifier
    if type(kind) is not str or kind not in accepted or str(path) not in {str(item) for item in accepted[kind]}:
        raise ShellRuntimeError('SHELL_IDENTITY','解释器不属于固定检测候选')
    if file_identity(path)!=interpreter.get('sha256'):raise ShellRuntimeError('SHELL_CHANGED','解释器内容变化，旧批准失效')
    script=Path(script_path);cwd=Path(cwd)
    if not script.is_absolute() or not script.is_file() or not cwd.is_absolute() or not cwd.is_dir():raise ShellRuntimeError('SHELL_RUNTIME','脚本或工作目录不可用')
    input_root=Path(input_root) if input_root is not None else cwd
    output_root=Path(output_root) if output_root is not None else cwd
    if not input_root.is_absolute() or not input_root.is_dir() or not output_root.is_absolute() or not output_root.is_dir():raise ShellRuntimeError('SHELL_RUNTIME','输入副本或隔离产物目录不可用')
    if kind=='wsl':return await _run_wsl(interpreter,script,cwd,timeout_seconds,cancel_event,output_root,input_root)
    args=_arguments(interpreter,script,cwd,output_root,input_root)
    return await _capture({'executable':str(path),'args':args,'cwd':str(cwd)},timeout_seconds,cancel_event,launch_guard=lambda:_launch_guard(interpreter))


def _launch_guard(interpreter):
    """native线程实际CreateProcess之前再次核对普通令牌及批准exe身份。"""
    if is_elevated():raise ShellRuntimeError('SHELL_ELEVATED','执行前普通权限令牌失效')
    if file_identity(interpreter['executable'])!=interpreter['sha256']:
        raise ShellRuntimeError('SHELL_CHANGED','执行前解释器身份变化，旧批准失效')


def _wsl_args(distro,command,*args):
    """明确发行版和零继承env，只运行固定host命令；不探测Docker内部。"""
    if not isinstance(distro,str) or distro not in _distros(distro):
        raise ShellRuntimeError('SHELL_WSL','不允许管理发行版或无效发行版身份')
    command='set -o pipefail; [ "$(id -u)" -ne 0 ] || exit 125; '+command
    return ['--distribution',distro,'--exec','/usr/bin/env','-i','PATH=/usr/bin:/bin','/bin/bash','--noprofile','--norc','-c',command,'orvia-shell',*map(str,args)]


async def _detect_wsl(executable,distro,sha,timeout=5):
    """普通WSL须非root默认用户和明确进程组工具；Windows启动器本身不证明Linux回收。"""
    command='uid=$(id -u) || exit 125; [ "$uid" -ne 0 ] || exit 125; for p in bash setsid ps wslpath sha256sum awk tr sleep grep; do command -v "$p" >/dev/null || exit 126; done; [ -x /usr/bin/kill ] || exit 126; printf "%s\\n" "$uid"; /bin/bash --version | { read -r line; printf "%s\\n" "$line"; }; sha256sum /bin/bash "$(command -v setsid)" /usr/bin/kill "$(command -v ps)"'
    probe=await _probe(executable,_wsl_args(distro,command),timeout)
    if probe['state']!='completed' or not probe['children_reaped']:
        return _row('wsl:'+distro,'WSL · '+distro,executable,sha=sha,distro=distro,reason='普通WSL用户、bash或进程组工具先决条件未满足')
    lines=probe['stdout'].splitlines()
    if len(lines)<6 or not re.fullmatch(r'[1-9][0-9]{0,9}',lines[0]) or not all(re.match(r'^[0-9a-f]{64}  ',line) for line in lines[2:6]):
        return _row('wsl:'+distro,'WSL · '+distro,executable,sha=sha,distro=distro,reason='WSL工具身份/用户核验格式不受支持')
    signature=hashlib.sha256('\n'.join(lines[2:6]).encode()).hexdigest()
    version=lines[1][:80]+' · uid='+lines[0]+' · tools='+signature
    return _row('wsl:'+distro,'WSL · '+distro,executable,version,sha,True,distro=distro)


def _control(text,nonce):
    """控制文件仅作候选PID；还须Linux核验nonce、starttime、SID/PGID后才可发信号。"""
    parts=text.strip().split(':')
    if len(parts)!=3 or parts[2]!=nonce or not re.fullmatch(r'[1-9][0-9]{0,9}',parts[0]) or not re.fullmatch(r'[0-9]{1,20}',parts[1]):
        raise ShellRuntimeError('SHELL_WSL_CONTROL','WSL进程组控制身份无效，拒绝猜测PID')
    return int(parts[0]),parts[1]


async def _wsl_group(executable,distro,pid,start,nonce,*,terminate=False):
    """定点核对Linux自有组身份后只处理该组；不结束发行版或仅杀Windows启动器。"""
    command=r"""pid=$1; stamp=$2; nonce=$3; action=$4
if [ -r "/proc/$pid/stat" ]; then
 current=$(awk '{print $22}' "/proc/$pid/stat") || exit 125
 [ "$current" = "$stamp" ] || exit 125
 tr '\0' ' ' < "/proc/$pid/cmdline" | grep -F -- "$nonce" >/dev/null || exit 125
 group=$(ps -o pgid= -p "$pid" | tr -d ' '); sid=$(ps -o sid= -p "$pid" | tr -d ' ')
 [ "$group" = "$pid" ] && [ "$sid" = "$pid" ] || exit 125
 if [ "$action" = kill ]; then /usr/bin/kill -KILL -- "-$pid" 2>/dev/null || :; fi
elif ps -eo pgid=,stat= | awk -v p="$pid" '$1==p && $2 !~ /^Z/ {found=1} END {exit !found}'; then
 # leader已退出却有成员：无法核验nonce，禁止按候选PID猜测终止。
 exit 125
fi
alive=$(ps -eo pgid=,stat= | awk -v p="$pid" '$1==p && $2 !~ /^Z/ {n++} END {print n+0}') || exit 125
printf '%s\n' "$alive"
"""
    result=await _probe(executable,_wsl_args(distro,command,pid,start,nonce,'kill' if terminate else 'check'),5)
    return result['state']=='completed' and result['children_reaped'] and result['stdout'].strip()=='0'


async def _run_wsl(interpreter,script,cwd,timeout,cancel_event,output_root,input_root):
    """WSL独立setsid/nonce回查；任何Linux组核验失败都不能声明children_reaped。"""
    started=utc();deadline=monotonic()+timeout
    def untouched(state):
        return {'state':state,'exit_code':None,'stdout':'','stderr':'','stdout_truncated':False,'stderr_truncated':False,'children_reaped':True,'started_at':started,'finished_at':utc()}
    if cancel_event.is_set():return untouched('cancelled')
    distro=interpreter.get('distro')
    if interpreter['id']!='wsl:'+str(distro):raise ShellRuntimeError('SHELL_WSL','WSL发行版身份与批准不一致')
    fresh=await _detect_wsl(interpreter['executable'],distro,interpreter['sha256'],min(5,timeout))
    if cancel_event.is_set():return untouched('cancelled')
    if monotonic()>=deadline:return untouched('timeout')
    if not fresh['available'] or fresh['version']!=interpreter['version']:
        raise ShellRuntimeError('SHELL_WSL_CHANGED','WSL用户或工具身份变化，旧批准失效')
    nonce=uuid4().hex;control=script.parent/('.orvia-wsl-'+nonce+'.control');gate=script.parent/('.orvia-wsl-'+nonce+'.gate')
    identity=None
    # 内层bash保持nonce于argv；gate以前不启动用户脚本，等待至多10秒自行结束。
    inner=r"""[ "$(id -u)" -ne 0 ] || exit 125; work=$(wslpath -a -u "$1") || exit 125; script=$(wslpath -a -u "$2") || exit 125; input=$(wslpath -a -u "$3") || exit 125; output=$(wslpath -a -u "$4") || exit 125; marker=$(wslpath -a -u "$6") || exit 125; gate=$(wslpath -a -u "$7") || exit 125; stamp=$(awk '{print $22}' /proc/$$/stat) || exit 125; umask 077; printf "%s:%s:%s\\n" "$$" "$stamp" "$5" > "$marker"; end=$((SECONDS+10)); while [ ! -f "$gate" ]; do [ "$SECONDS" -lt "$end" ] || exit 124; sleep .02; done; export ORVIA_INPUT_DIR="$input" ORVIA_OUTPUT_DIR="$output"; cd -- "$work" || exit 125; /bin/bash --noprofile --norc "$script"; exit $?"""
    outer='exec setsid --wait /bin/bash --noprofile --norc -c "$1" "$2" "${@:3}"'
    args=_wsl_args(distro,outer,inner,'orvia-shell-'+nonce,_windows_path(cwd),_windows_path(script),_windows_path(input_root),_windows_path(output_root),nonce,_windows_path(control),_windows_path(gate))
    async def ready(process):
        nonlocal identity
        ready_deadline=min(deadline,monotonic()+5)
        while monotonic()<ready_deadline:
            if cancel_event.is_set():raise ShellRuntimeError('SHELL_WSL_CANCELLED','用户取消，WSL脚本没有被释放')
            if control.exists():
                try:identity=_control(control.read_text(encoding='utf-8')[:256],nonce)
                except (OSError,UnicodeError):raise ShellRuntimeError('SHELL_WSL_CONTROL','WSL控制回执无法读取') from None
                # ready阶段leader存活，以同一身份核对而非接受文件声明。
                pid,start=identity
                check=r"""pid=$1; stamp=$2; nonce=$3; [ "$(awk '{print $22}' /proc/$pid/stat)" = "$stamp" ] || exit 125; [ "$(ps -o pgid= -p "$pid" | tr -d " ")" = "$pid" ] || exit 125; [ "$(ps -o sid= -p "$pid" | tr -d " ")" = "$pid" ] || exit 125; tr "\\0" " " < /proc/$pid/cmdline | grep -F -- "$nonce" >/dev/null || exit 125"""
                result=await _probe(interpreter['executable'],_wsl_args(distro,check,pid,start,nonce),3)
                if result['state']!='completed':raise ShellRuntimeError('SHELL_WSL_CONTROL','WSL自有进程组nonce或创建身份核验失败')
                gate.write_text(nonce,encoding='utf-8');return
            await asyncio.sleep(.02)
        raise ShellRuntimeError('SHELL_WSL_CONTROL','未收到WSL自有组回执，用户脚本未被释放')
    async def reap():
        if identity is None:return False
        return await _wsl_group(interpreter['executable'],distro,*identity,nonce,terminate=True)
    try:
        return await _capture({'executable':interpreter['executable'],'args':args,'cwd':str(cwd)},max(.001,deadline-monotonic()),cancel_event,before_close=reap,on_spawned=ready,launch_guard=lambda:_launch_guard(interpreter))
    finally:
        for path in (control,gate):
            try:path.unlink(missing_ok=True)
            except OSError:pass
