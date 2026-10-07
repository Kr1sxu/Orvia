"""MCP有限stdio与HTTPS Streamable HTTP；不恢复断线、不执行服务器主动请求。"""
import asyncio
import ctypes
from ctypes import wintypes as w
import os
from pathlib import Path
import re
import ssl
import subprocess
from urllib.parse import urlsplit
import httpx
from .protocol import McpError, VERSION, WIRE_LIMIT, decode, encode

REQUEST_SECONDS=20
CONNECT_SECONDS=30
METHODS={'initialize','tools/list','tools/call'}
NOTIFICATIONS={'notifications/initialized','notifications/cancelled'}


def endpoint(url):
    """准确HTTPS身份；禁止userinfo/query/fragment和控制字符，不跟随重定向。"""
    if not isinstance(url,str) or len(url)>2048 or any(ord(c)<33 or ord(c)>126 for c in url):
        raise McpError('MCP_ENDPOINT','服务URL必须是明确ASCII HTTPS地址')
    try:
        parts=urlsplit(url);port=parts.port
        if parts.scheme!='https' or not parts.hostname or parts.username is not None or parts.password is not None or '?' in url or '#' in url or '\\' in url or not 1<=(443 if port is None else port)<=65535:
            raise ValueError
        if not re.fullmatch(r'[A-Za-z0-9.:-]+',parts.hostname):raise ValueError
        if str(httpx.URL(url)) != url:raise ValueError
    except ValueError:raise McpError('MCP_ENDPOINT','服务URL身份无效或包含未允许的成分') from None
    return url


class _BasicLimit(ctypes.Structure):
    _fields_=[('PerProcessUserTimeLimit',ctypes.c_int64),('PerJobUserTimeLimit',ctypes.c_int64),('LimitFlags',w.DWORD),('MinimumWorkingSetSize',ctypes.c_size_t),('MaximumWorkingSetSize',ctypes.c_size_t),('ActiveProcessLimit',w.DWORD),('Affinity',ctypes.c_size_t),('PriorityClass',w.DWORD),('SchedulingClass',w.DWORD)]
class _IoCounters(ctypes.Structure):
    _fields_=[(key,ctypes.c_uint64) for key in ('ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount')]
class _ExtendedLimit(ctypes.Structure):
    _fields_=[('BasicLimitInformation',_BasicLimit),('IoInfo',_IoCounters),('ProcessMemoryLimit',ctypes.c_size_t),('JobMemoryLimit',ctypes.c_size_t),('PeakProcessMemoryUsed',ctypes.c_size_t),('PeakJobMemoryUsed',ctypes.c_size_t)]
class _Accounting(ctypes.Structure):
    _fields_=[('TotalUserTime',ctypes.c_int64),('TotalKernelTime',ctypes.c_int64),('ThisPeriodTotalUserTime',ctypes.c_int64),('ThisPeriodTotalKernelTime',ctypes.c_int64),('TotalPageFaultCount',w.DWORD),('TotalProcesses',w.DWORD),('ActiveProcesses',w.DWORD),('TotalTerminatedProcesses',w.DWORD)]


class _JobProcess:
    """普通用户服务器先挂起入Job再恢复，Job内所有孩子由kill-on-close限制回收。"""
    def __init__(self,config):
        if os.name!='nt':raise McpError('MCP_PLATFORM','本版受控stdio启动仅支持Windows')
        import _winapi
        import msvcrt
        self.k=ctypes.WinDLL('kernel32',use_last_error=True)
        signatures={'CreateJobObjectW':([w.LPVOID,w.LPCWSTR],w.HANDLE),'SetInformationJobObject':([w.HANDLE,ctypes.c_int,w.LPVOID,w.DWORD],w.BOOL),'QueryInformationJobObject':([w.HANDLE,ctypes.c_int,w.LPVOID,w.DWORD,w.LPVOID],w.BOOL),'AssignProcessToJobObject':([w.HANDLE,w.HANDLE],w.BOOL),'ResumeThread':([w.HANDLE],w.DWORD),'TerminateJobObject':([w.HANDLE,w.UINT],w.BOOL),'CloseHandle':([w.HANDLE],w.BOOL)}
        for name,(args,result) in signatures.items():
            fn=getattr(self.k,name);fn.argtypes=args;fn.restype=result
        self.job=self.k.CreateJobObjectW(None,None);self.handle=None;self.pid=None;self.files=[]
        if not self.job:raise McpError('MCP_JOB','无法建立受控进程Job')
        fds=[];thread=None
        try:
            limit=_ExtendedLimit();limit.BasicLimitInformation.LimitFlags=0x2000
            if not self.k.SetInformationJobObject(self.job,9,ctypes.byref(limit),ctypes.sizeof(limit)):raise McpError('MCP_JOB','无法配置kill-on-close，stdio能力关闭')
            verify=_ExtendedLimit()
            if not self.k.QueryInformationJobObject(self.job,9,ctypes.byref(verify),ctypes.sizeof(verify),None) or verify.BasicLimitInformation.LimitFlags!=0x2000:raise McpError('MCP_JOB','Job限制核验失败')
            stdin_read,stdin_write=os.pipe();fds.extend((stdin_read,stdin_write))
            stdout_read,stdout_write=os.pipe();fds.extend((stdout_read,stdout_write))
            stderr_read,stderr_write=os.pipe();fds.extend((stderr_read,stderr_write))
            inherited=[msvcrt.get_osfhandle(fd) for fd in (stdin_read,stdout_write,stderr_write)]
            for handle in inherited:os.set_handle_inheritable(handle,True)
            si=subprocess.STARTUPINFO();si.dwFlags=subprocess.STARTF_USESTDHANDLES
            si.hStdInput,si.hStdOutput,si.hStdError=inherited;si.lpAttributeList={'handle_list':inherited}
            # 不继承PATH、密钥、TOKEN、代理、个人业务变量；仅Windows运行及指定可执行目录。
            env={key:os.environ[key] for key in ('SystemRoot','WINDIR','TEMP','TMP','COMSPEC') if key in os.environ}
            env['PATH']=str(Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32')+os.pathsep+str(Path(config['executable']).parent)
            env['PYTHONUTF8']='1';env['PYTHONUNBUFFERED']='1'
            flags=subprocess.CREATE_NO_WINDOW|0x4|0x400|0x80000
            self.handle,thread,self.pid,_=_winapi.CreateProcess(config['executable'],subprocess.list2cmdline([config['executable'],*config.get('args',[])]),None,None,True,flags,env,config.get('cwd'),si)
            if not self.k.AssignProcessToJobObject(self.job,self.handle):raise McpError('MCP_JOB','挂起服务器无法加入Job，未启动业务')
            for fd in (stdin_read,stdout_write,stderr_write):os.close(fd);fds.remove(fd)
            self.stdin=os.fdopen(stdin_write,'wb',buffering=0);fds.remove(stdin_write)
            self.stdout=os.fdopen(stdout_read,'rb',buffering=0);fds.remove(stdout_read)
            self.stderr=os.fdopen(stderr_read,'rb',buffering=0);fds.remove(stderr_read)
            self.files=[self.stdin,self.stdout,self.stderr]
            if self.k.ResumeThread(thread)==0xffffffff:raise McpError('MCP_JOB','无法恢复受控服务器')
        except BaseException:
            try:
                if self.handle:
                    _winapi.TerminateProcess(self.handle,0xE007)
                    _winapi.WaitForSingleObject(self.handle,2000)
            finally:
                self.k.TerminateJobObject(self.job,0xE007)
                for file in self.files:file.close()
                if self.handle:self.k.CloseHandle(self.handle);self.handle=None
                self.k.CloseHandle(self.job);self.job=None
            raise
        finally:
            if thread:self.k.CloseHandle(thread)
            for fd in fds:os.close(fd)

    def active(self):
        if not self.job:return 0
        value=_Accounting()
        if not self.k.QueryInformationJobObject(self.job,1,ctypes.byref(value),ctypes.sizeof(value),None):raise McpError('MCP_JOB','无法核验Job子进程回收')
        return value.ActiveProcesses

    def close(self):
        """关闭输入后有界等待，剩余整个Job终止并核验ActiveProcesses=0。"""
        import _winapi
        if not self.job:return {'closed':True,'children_reaped':True}
        self.stdin.close()
        if self.handle:_winapi.WaitForSingleObject(self.handle,300)
        reaped=False
        try:
            if self.active():self.k.TerminateJobObject(self.job,0xE007)
            import time
            deadline=time.monotonic()+2
            while time.monotonic()<deadline:
                if self.active()==0:reaped=True;break
                time.sleep(.02)
        finally:
            self.k.CloseHandle(self.job);self.job=None
            if self.handle:self.k.CloseHandle(self.handle);self.handle=None
            for file in self.files:
                if not file.closed:file.close()
        return {'closed':True,'children_reaped':reaped}


class Session:
    """单会话单请求，无自动重试；主动服务请求拒绝后关闭，不提供采样或本地执行。"""
    def __init__(self,config,credential=None,verify=True):
        self.config=config;self.changed=False;self.initialization={};self.server_info={};self.capabilities={}
        self._credential=credential;self._verify=verify;self._id=0;self._lock=asyncio.Lock();self._closed=False;self._failed=None
        self._process=None;self._client=None;self._reader=None;self._stderr=None;self._pending=None;self._session_id=None;self._notifications=0;self._close_result=None;self._close_task=None;self._spawn_task=None

    @property
    def closed(self):
        """EOF、协议失败或关闭均不能继续显示为ready。"""
        return self._closed or self._failed is not None

    async def start(self):
        if self.config['transport']=='stdio':
            # 原生CreateProcess不能靠取消Python线程终止。保存唯一spawn任务并shield，
            # 取消或超时必须等待该原生尝试终结，再关闭后到Job，不能丢掉其所有权。
            self._spawn_task=asyncio.create_task(asyncio.to_thread(_JobProcess,self.config))
            try:
                self._process=await asyncio.shield(self._spawn_task)
            except asyncio.CancelledError:
                await asyncio.shield(self.close())
                raise
            if self._closed:
                await self.close()
                raise McpError('MCP_CLOSED','启动期间会话已关闭，后到Job已回收')
            self._reader=asyncio.create_task(self._read_stdio());self._stderr=asyncio.create_task(self._drain_stderr())
        else:
            self._client=httpx.AsyncClient(verify=self._verify,trust_env=False,follow_redirects=False,timeout=REQUEST_SECONDS)
        result=await self.request('initialize',{'protocolVersion':VERSION,'capabilities':{},'clientInfo':{'name':'Orvia','version':'4.0.7'}})
        if not isinstance(result,dict) or result.get('protocolVersion')!=VERSION or type(result.get('capabilities')) is not dict or type(result.get('serverInfo')) is not dict:
            raise McpError('MCP_VERSION','服务器协议版本或能力协商结果不受支持')
        if set(result['serverInfo'])-{'name','version','title'} or any(not isinstance(result['serverInfo'].get(key),str) or not 1<=len(result['serverInfo'][key])<=200 for key in ('name','version')):
            raise McpError('MCP_PROTOCOL','服务器身份结构无效')
        tools=result['capabilities'].get('tools')
        if type(tools) is not dict or set(tools)-{'listChanged'} or ('listChanged' in tools and type(tools['listChanged']) is not bool):
            raise McpError('MCP_CAPABILITY','服务器没有受支持的tools能力')
        self.initialization=result;self.server_info=result['serverInfo'];self.capabilities=result['capabilities']
        await self.notify('notifications/initialized')
        return self

    async def request(self,method,params=None):
        """每次尝试有20秒总预算，通知或SSE进度不能延长期限。"""
        if type(method) is not str or method not in METHODS:raise McpError('MCP_METHOD','方法不在固定MCP工具允许清单')
        if params is not None and type(params) is not dict:raise McpError('MCP_PROTOCOL','请求params必须为结构对象')
        async with self._lock:
            if self._closed or self._failed:raise self._failed or McpError('MCP_CLOSED','服务会话已关闭')
            self._id+=1;rid=self._id;message={'jsonrpc':'2.0','id':rid,'method':method,'params':params or {}}
            encode(message);self._notifications=0
            try:
                return await asyncio.wait_for(self._request(message),REQUEST_SECONDS)
            except asyncio.TimeoutError:
                self._failed=McpError('MCP_TIMEOUT','MCP响应超时，结果未知，不自动重试');await self.close();raise self._failed from None
            except asyncio.CancelledError:
                self._failed=McpError('MCP_CANCELLED','MCP调用已取消，结果未知，不自动重试');await asyncio.shield(self.close());raise
            except McpError as exc:
                self._failed=exc;await self.close();raise
            except (OSError,httpx.HTTPError,ValueError) as exc:
                self._failed=McpError('MCP_DISCONNECTED','MCP连接失败或断开，结果未知，不自动重试');await self.close();raise self._failed from None

    async def notify(self,method,params=None):
        """客户端仅发送固定初始化/取消通知，不提供服务器请求或任意方法透传。"""
        if type(method) is not str or method not in NOTIFICATIONS:raise McpError('MCP_METHOD','通知不在固定允许清单')
        if params is not None and type(params) is not dict:raise McpError('MCP_PROTOCOL','通知params必须为结构对象')
        if self._closed:raise McpError('MCP_CLOSED','服务会话已关闭')
        message={'jsonrpc':'2.0','method':method,'params':params or {}}
        try:
            await asyncio.wait_for(self._send(message),REQUEST_SECONDS)
        except (asyncio.TimeoutError,OSError,httpx.HTTPError):
            await self.close();raise McpError('MCP_DISCONNECTED','通知未被接受，会话已关闭') from None
        except McpError as exc:
            self._failed=exc;await self.close();raise

    async def _send(self,message):
        data=encode(message)
        if self._process:
            await asyncio.to_thread(self._process.stdin.write,data+b'\n')
        else:
            async with self._client.stream('POST',self.config['url'],headers=self._headers(),content=data) as response:
                await self._status(response,notification=True)
                total=0
                async for block in response.aiter_raw():
                    total+=len(block)
                    if total:raise McpError('MCP_PROTOCOL','通知接受202响应必须为空')

    def _headers(self):
        headers={'Accept':'application/json, text/event-stream','Content-Type':'application/json','Accept-Encoding':'identity'}
        if self.initialization:headers['MCP-Protocol-Version']=VERSION
        if self._session_id:headers['Mcp-Session-Id']=self._session_id
        if self._credential:headers['Authorization']='Bearer '+self._credential
        return headers

    async def _status(self,response,notification=False):
        if response.status_code!=(202 if notification else 200):
            code='MCP_AUTH' if response.status_code==401 else 'MCP_SESSION_EXPIRED' if response.status_code==404 else 'MCP_HTTP'
            raise McpError(code,'MCP服务拒绝响应；不重定向、授权跳转或自动重连')
        if response.headers.get('content-encoding','identity').lower()!='identity':raise McpError('MCP_ENCODING','压缩响应不在当前支持子集中')
        sid=response.headers.get('mcp-session-id')
        if sid is not None:
            if not sid or len(sid)>256 or any(not 0x21<=ord(char)<=0x7e for char in sid):raise McpError('MCP_SESSION','服务器session身份无效')
            if self._session_id is not None and sid!=self._session_id:raise McpError('MCP_SESSION','服务器改变session身份')
            self._session_id=sid

    async def _request(self,message):
        if self._process:
            self._pending=asyncio.get_running_loop().create_future()
            await self._send(message)
            try:return await self._pending
            finally:self._pending=None
        result=None
        async with self._client.stream('POST',self.config['url'],headers=self._headers(),content=encode(message)) as response:
            await self._status(response)
            media=response.headers.get('content-type','').split(';',1)[0].strip().lower()
            if media not in {'application/json','text/event-stream'}:raise McpError('MCP_MEDIA','服务器返回不支持的内容类型')
            total=0;buffer=b''
            async for block in response.aiter_raw():
                total+=len(block)
                if total>WIRE_LIMIT:raise McpError('MCP_LIMIT','HTTP响应超过64KiB')
                buffer+=block
                if media=='text/event-stream':
                    buffer=buffer.replace(b'\r\n',b'\n')
                    while b'\n\n' in buffer:
                        event,buffer=buffer.split(b'\n\n',1)
                        values=[]
                        for line in event.split(b'\n'):
                            if line.startswith(b':') or not line:continue
                            field,separator,value=line.partition(b':')
                            if value.startswith(b' '):value=value[1:]
                            if field==b'data':values.append(value)
                            elif field==b'event':
                                if value not in {b'message',b''}:raise McpError('MCP_SSE','不支持SSE事件类别')
                            elif field==b'id':
                                if len(value)>256 or any(c<33 or c>126 for c in value):raise McpError('MCP_SSE','SSE事件身份无效')
                            else:raise McpError('MCP_SSE','不支持SSE字段或自动恢复提示')
                        if values:
                            value=await self._message(decode(b'\n'.join(values)),message['id'])
                            if value is not None:
                                if result is not None:raise McpError('MCP_PROTOCOL','服务器重复返回同一响应')
                                result=value
            if media=='application/json':result=await self._message(decode(buffer),message['id'])
            elif buffer.strip():raise McpError('MCP_SSE','SSE流在完整事件之前断开')
        if result is None:raise McpError('MCP_DISCONNECTED','服务器未返回当前请求结果')
        return result

    async def _message(self,value,rid=None):
        if value.get('jsonrpc')!='2.0':raise McpError('MCP_PROTOCOL','JSON-RPC版本不正确')
        if 'method' in value:
            if set(value)-{'jsonrpc','id','method','params'} or type(value['method']) is not str or type(value.get('params',{})) is not dict:raise McpError('MCP_PROTOCOL','服务器请求或通知结构无效')
            if 'id' in value:
                if type(value['id']) not in (int,str):raise McpError('MCP_PROTOCOL','服务器请求身份无效')
                # 客户端没有sampling/roots/elicitation/执行能力，明确-32601后关闭。
                await self._send({'jsonrpc':'2.0','id':value['id'],'error':{'code':-32601,'message':'Client capability unavailable'}})
                raise McpError('MCP_SERVER_REQUEST','拒绝服务器主动请求，会话已关闭')
            self._notifications+=1
            if self._notifications>32:raise McpError('MCP_LIMIT','单次响应通知超过32项')
            if value['method']=='notifications/tools/list_changed':self.changed=True
            elif value['method'] not in {'notifications/progress','notifications/message'}:raise McpError('MCP_NOTIFICATION','不支持的服务器通知')
            return None
        if set(value)-{'jsonrpc','id','result','error'} or type(value.get('id')) is not int or value['id']!=rid or ('result' in value)==('error' in value):raise McpError('MCP_PROTOCOL','响应身份未知、重复或结构无效')
        if 'error' in value:
            error=value['error']
            if type(error) is not dict or type(error.get('code')) is not int or type(error.get('message')) is not str:raise McpError('MCP_PROTOCOL','服务错误结构无效')
            raise McpError('MCP_REMOTE_ERROR','服务返回JSON-RPC错误；不会自动重试')
        if type(value['result']) is not dict:raise McpError('MCP_PROTOCOL','MCP工具响应必须为结构对象')
        return value['result']

    async def _read_stdio(self):
        try:
            while not self._closed:
                line=await asyncio.to_thread(self._process.stdout.readline,WIRE_LIMIT+2)
                if not line:raise McpError('MCP_DISCONNECTED','stdio服务器退出或断开')
                if len(line)>WIRE_LIMIT+1 or not line.endswith(b'\n'):raise McpError('MCP_LIMIT','stdio消息超过64KiB或缺少行结束')
                value=await self._message(decode(line[:-1].removesuffix(b'\r')),self._id if self._pending is not None else None)
                if value is not None:
                    if self._pending is None or self._pending.done():raise McpError('MCP_PROTOCOL','重复响应或无对应请求')
                    self._pending.set_result(value)
        except asyncio.CancelledError:raise
        except (McpError,OSError,ValueError) as exc:
            if self._closed:return
            self._failed=self._failed or (exc if isinstance(exc,McpError) else McpError('MCP_DISCONNECTED','stdio连接断开'))
            if self._pending is not None and not self._pending.done():self._pending.set_exception(self._failed)
            await self.close()

    async def _drain_stderr(self):
        """按4KiB块丢弃stderr，不保留日志/路径/正文；超过256KiB停止恶意服务。"""
        total=0
        try:
            while not self._closed:
                data=await asyncio.to_thread(self._process.stderr.read,4096)
                if not data:return
                total+=len(data)
                if total>256*1024:
                    self._failed=McpError('MCP_LIMIT','服务器stderr超过有限排空预算');await self.close();return
        except (OSError,ValueError):return

    async def close(self):
        """关闭会话及真实Job，结果明确区分客户端关闭与本地子进程核验。"""
        if self._close_result is not None:return self._close_result
        if self._close_task is None:self._close_task=asyncio.create_task(self._close())
        return await asyncio.shield(self._close_task)

    async def _close(self):
        self._closed=True;result={'closed':True,'children_reaped':True}
        if self._spawn_task is not None:
            try:
                self._process=await asyncio.shield(self._spawn_task)
            except (McpError,OSError,ValueError):
                # _JobProcess失败路径自身终止挂起进程并关闭Job，不产生可用会话。
                self._process=None
        if self._pending is not None and not self._pending.done():self._pending.set_exception(self._failed or McpError('MCP_CLOSED','MCP会话已关闭'))
        if self._process:
            result=await asyncio.to_thread(self._process.close)
        if self._client:
            if self._session_id:
                try:
                    async def delete():
                        async with self._client.stream('DELETE',self.config['url'],headers=self._headers()) as response:
                            return response.status_code
                    status=await asyncio.wait_for(delete(),3)
                    # 405表示服务不支持关闭会话，不能把本地client关闭当远端已接受终止。
                    if status not in {200,202,204}:result['closed']=False
                except (httpx.HTTPError,asyncio.TimeoutError):result['closed']=False
            await self._client.aclose()
        for task in (self._reader,self._stderr):
            if task and task is not asyncio.current_task():task.cancel()
        self._credential=None;self._close_result=result
        return result


async def connect(config,credential=None,*,verify=True):
    """调用者必须先原生批准准确配置；失败安全关闭，30秒连接总预算无重试。"""
    if type(config) is not dict or type(config.get('transport')) is not str or config.get('transport') not in {'stdio','https'}:raise McpError('MCP_CONFIG','传输配置无效')
    if verify is not True and not isinstance(verify,ssl.SSLContext):raise McpError('MCP_TLS','禁止关闭TLS核验；测试只能提供明确SSLContext')
    if config['transport']=='https':
        if set(config)-{'transport','url'}:raise McpError('MCP_CONFIG','HTTPS配置含未允许字段')
        endpoint(config.get('url'))
    else:
        if set(config)-{'transport','executable','args','cwd'}:raise McpError('MCP_CONFIG','stdio配置含未允许字段')
        executable=config.get('executable');args=config.get('args',[]);cwd=config.get('cwd')
        if not isinstance(executable,str) or not Path(executable).is_absolute() or not Path(executable).is_file() or Path(executable).suffix.lower()!='.exe' or len(executable)>1000:raise McpError('MCP_CONFIG','服务器可执行程序必须是明确绝对exe路径')
        if type(args) is not list or len(args)>16 or any(type(arg) is not str or len(arg)>2000 or '\x00' in arg for arg in args):raise McpError('MCP_CONFIG','服务器参数必须为最多16个有界字符串')
        if cwd is not None and (not isinstance(cwd,str) or not Path(cwd).is_absolute() or not Path(cwd).is_dir()):raise McpError('MCP_CONFIG','服务器工作目录必须是明确绝对目录')
        if credential is not None:raise McpError('MCP_CREDENTIAL','stdio不继承或注入云凭据')
    if credential is not None and (not isinstance(credential,str) or not 1<=len(credential)<=4096 or any(ord(char)<33 or ord(char)>126 for char in credential)):raise McpError('MCP_CREDENTIAL','服务凭据格式不受支持')
    session=Session(dict(config),credential,verify)
    try:
        return await asyncio.wait_for(session.start(),CONNECT_SECONDS)
    except asyncio.TimeoutError:
        await session.close();raise McpError('MCP_CONNECT_TIMEOUT','MCP初始化30秒总预算耗尽') from None
    except (OSError,ValueError):
        await session.close();raise McpError('MCP_START','服务器无法受控启动，能力关闭') from None
    except BaseException:
        await session.close();raise
