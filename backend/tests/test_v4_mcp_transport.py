"""V4-007真实Windows Job/子进程和本机TLS；不调用模型、不读取真实凭据。"""
import asyncio
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import psutil
import pytest
from orvia_backend.mcp import transport
from orvia_backend.mcp.protocol import McpError,VERSION,decode
from orvia_backend.mcp.schema import validate_schema,validate
from v4_mcp_https_fixture import Fixture


def stdio(mode='normal'):
    return {'transport':'stdio','executable':str(Path(sys.executable).resolve()),'args':[str(Path(__file__).with_name('v4_mcp_stdio_fixture.py').resolve()),mode]}


def test_real_tls_server_refuses_delete_cannot_claim_remote_session_closed(tls_files):
    async def run():
        cert,key,verify=tls_files;fixture=Fixture(cert,key,'close_refused')
        try:
            session=await transport.connect({'transport':'https','url':fixture.url},verify=verify)
            report=await session.close()
            assert report=={'closed':False,'children_reaped':True}
            assert session.closed and session._client.is_closed
            assert await session.close()==report
        finally:fixture.close()
    asyncio.run(run())

@pytest.fixture(scope='module')
def tls_files():
    root=Path('artifacts/test-results/V4-007/tls-fixture').resolve();root.mkdir(parents=True,exist_ok=True)
    cert=root/'cert.pem';key=root/'key.pem'
    config=root/'openssl.cnf';config.write_text('[req]\ndistinguished_name=dn\n[dn]\n',encoding='utf-8')
    tool=Path('C:/Users/18532/anaconda3/Library/bin/openssl.exe')
    subprocess.run([str(tool),'req','-config',str(config),'-x509','-newkey','rsa:2048','-nodes','-keyout',str(key),'-out',str(cert),'-days','1','-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost'],check=True,capture_output=True,timeout=10)
    return cert,key,ssl.create_default_context(cafile=str(cert))


def test_stdio_real_initialization_pages_call_and_clean_environment(tmp_path):
    async def run():
        original=os.environ.get('SYNTHETIC_API_KEY');os.environ['SYNTHETIC_API_KEY']='synthetic-not-real'
        session=None
        try:
            session=await transport.connect(stdio('children'))
            assert session.initialization['protocolVersion']==VERSION
            result=await session.request('tools/list',{})
            assert not result['environment_has_secret']
            child=psutil.Process(result['child_pid']);assert child.is_running()
            assert (await session.request('tools/call',{'name':'read_echo','arguments':{'query':'合成'}}))['content'][0]['text']=='合成'
            closed=await session.close();assert closed=={'closed':True,'children_reaped':True}
            child.wait(3)
            assert not psutil.pid_exists(child.pid)
        finally:
            if session:await session.close()
            if original is None:os.environ.pop('SYNTHETIC_API_KEY',None)
            else:os.environ['SYNTHETIC_API_KEY']=original
    asyncio.run(run())


def test_stdio_pages_and_live_list_changed():
    async def run():
        session=await transport.connect(stdio('notification'))
        try:
            first=await session.request('tools/list',{})
            second=await session.request('tools/list',{'cursor':first['nextCursor']})
            assert 'nextCursor' not in second and session.changed
        finally:assert (await session.close())['children_reaped']
    asyncio.run(run())

@pytest.mark.parametrize('mode,code',[('version','MCP_VERSION'),('disconnect','MCP_DISCONNECTED'),('request','MCP_SERVER_REQUEST'),('oversize','MCP_LIMIT'),('notifications','MCP_LIMIT')])
def test_stdio_malicious_or_disconnected_closes_tree(mode,code):
    async def run():
        session=None
        try:
            if mode=='version':
                with pytest.raises(McpError) as error:await transport.connect(stdio(mode))
            else:
                session=await transport.connect(stdio(mode))
                with pytest.raises(McpError) as error:await session.request('tools/list',{})
            assert error.value.code==code
            if session:assert (await session.close())['children_reaped']
        finally:
            if session:await session.close()
    asyncio.run(run())


def test_stdio_timeout_no_retry_and_job_closed(monkeypatch):
    async def run():
        session=await transport.connect(stdio('timeout'));pid=session._process.pid
        monkeypatch.setattr(transport,'REQUEST_SECONDS',.15)
        with pytest.raises(McpError) as error:await session.request('tools/list',{})
        assert error.value.code=='MCP_TIMEOUT'
        assert (await session.close())['children_reaped'] and not psutil.pid_exists(pid)
        with pytest.raises(McpError):await session.request('tools/list',{})
    asyncio.run(run())

@pytest.mark.parametrize('mode',['json','sse'])
def test_real_tls_json_sse_version_headers_pages_and_delete(tls_files,mode):
    cert,key,verify=tls_files;fixture=Fixture(str(cert),str(key),mode)
    async def run():
        session=await transport.connect({'transport':'https','url':fixture.url},'synthetic-token',verify=verify)
        try:
            first=await session.request('tools/list',{});second=await session.request('tools/list',{'cursor':first['nextCursor']})
            assert second=={'tools':[]}
            assert (await session.request('tools/call',{'name':'read','arguments':{'query':'合成'}}))['content'][0]['text']=='合成TLS结果'
            if mode=='sse':assert session.changed
            assert all(headers.get('Authorization')=='Bearer synthetic-token' for headers in fixture.headers)
            assert all(headers.get('Mcp-Session-Id')=='fixture-session' and headers.get('MCP-Protocol-Version')==VERSION for headers in fixture.headers[1:])
            assert (await session.close())['closed']
        finally:await session.close()
    try:asyncio.run(run())
    finally:fixture.close()

@pytest.mark.parametrize('mode,code',[('redirect','MCP_HTTP'),('auth','MCP_AUTH'),('expired','MCP_SESSION_EXPIRED'),('unknown','MCP_PROTOCOL'),('oversize','MCP_LIMIT'),('media','MCP_MEDIA'),('gzip','MCP_ENCODING'),('session-invalid','MCP_SESSION'),('sse-invalid','MCP_SSE'),('duplicate','MCP_PROTOCOL'),('request','MCP_SERVER_REQUEST'),('notifications','MCP_LIMIT')])
def test_real_tls_invalid_response_rejected_without_redirect_or_retry(tls_files,mode,code):
    cert,key,verify=tls_files;fixture=Fixture(str(cert),str(key),mode)
    async def run():
        session=None
        try:
            with pytest.raises(McpError) as error:
                session=await transport.connect({'transport':'https','url':fixture.url},verify=verify)
                await session.request('tools/list',{})
            assert error.value.code==code
            if mode in {'redirect','auth','expired'}:assert len(fixture.messages)==1
        finally:
            if session:await session.close()
    try:asyncio.run(run())
    finally:fixture.close()

@pytest.mark.parametrize('payload',[b'{"jsonrpc":"2.0","id":1,"id":2}',b'{"n":NaN}',b'[]',b'{"n":"'+b'x'*65536+b'"}'],ids=['duplicate','nan','array','size'])
def test_strict_wire_json(payload):
    with pytest.raises(McpError):decode(payload)

@pytest.mark.parametrize('schema',[{'type':'object','properties':{'x':{'$ref':'https://example.invalid/private'}}},{'type':'string','pattern':'.*'},{'type':'array','items':{'type':'string'},'maxItems':65},{'type':'object','oneOf':[]}])
def test_unsupported_schema_is_explicitly_rejected(schema):
    with pytest.raises(McpError):validate_schema(schema)


def test_schema_supported_types_and_boundary_values():
    schema={'type':'object','properties':{'name':{'type':'string','minLength':1,'maxLength':10},'count':{'type':'integer','minimum':0,'maximum':3},'score':{'type':'number','exclusiveMinimum':0,'maximum':1},'flag':{'type':'boolean'},'tags':{'type':'array','items':{'type':'string'},'maxItems':2,'uniqueItems':True},'empty':{'type':'null'}},'required':['name'],'additionalProperties':False}
    validate(schema,{'name':'合成','count':2,'score':.5,'flag':True,'tags':['one'],'empty':None})
    for value in ({'name':'a','count':True},{'name':'a','score':float('nan')},{'name':'a','tags':['a','a']},{'name':'a','extra':1},{'name':'a','tags':['a','b','c']}):
        with pytest.raises(McpError):validate(schema,value)

@pytest.mark.parametrize('url',['http://localhost/mcp','https://user:pass@localhost/mcp','https://localhost/mcp?q=1','https://localhost/mcp#x','https://localhost/mcp\n','https://localhost:0/mcp'])
def test_endpoint_rejects_unapproved_identity_parts(url):
    with pytest.raises(McpError):transport.endpoint(url)

@pytest.mark.parametrize('payload',[b'{"n":1e309}',b'{"n":9007199254740992}',b'{"x":"\\ud800"}',b'{"\\ud800":1}'],ids=['exponent','safeint','surrogate-value','surrogate-key'])
def test_json_scalar_safety(payload):
    with pytest.raises(McpError):decode(payload)

@pytest.mark.parametrize('schema',[{'type':[]},{'type':'object','required':[{}]},{'type':'integer','minimum':10**500},{'type':'number','maximum':float('inf')},{'type':'array','items':[]},{'type':'string','enum':[{}]}],ids=['type-shape','required-shape','huge-int','infinite','items-shape','enum-shape'])
def test_malformed_schema_always_stable_error(schema):
    with pytest.raises(McpError):validate_schema(schema)


def test_stdio_job_breakaway_is_denied():
    async def run():
        session=await transport.connect(stdio('escape'))
        child=None
        try:
            value=await session.request('tools/list',{})
            if not value['escape_denied']:child=psutil.Process(value['child_pid'])
        finally:
            assert (await session.close())['children_reaped']
        if child:
            escaped=child.is_running()
            if escaped:
                # 只清理本用例明确创建并保留creation_time的合成子进程，绝不按模糊PID操作。
                child.kill();child.wait(3)
            assert not escaped, 'breakaway child escaped owned Job'
    asyncio.run(run())


def test_stdio_stderr_budget_closes_and_reaps():
    async def run():
        session=await transport.connect(stdio('stderr'))
        with pytest.raises(McpError) as error:await session.request('tools/list',{})
        assert error.value.code=='MCP_LIMIT'
        assert (await session.close())['children_reaped']
    asyncio.run(run())


@pytest.mark.parametrize('url',['https://localhost/mcp?','https://localhost/mcp#','https://LOCALHOST/mcp','https://localhost/a/../mcp'])
def test_endpoint_exact_identity_no_normalization(url):
    with pytest.raises(McpError):transport.endpoint(url)

@pytest.mark.parametrize('value',[{'hidden':['x']*65},{'hidden':{'x'+str(i):0 for i in range(33)}},{'hidden':'x'*8001},{'hidden':'\ud800'}],ids=['array','object','string','unicode'])
def test_open_object_does_not_bypass_global_value_limits(value):
    with pytest.raises(McpError):validate({'type':'object','additionalProperties':True},value)


def test_tls_verification_cannot_be_disabled(tls_files):
    cert,key,verify=tls_files;fixture=Fixture(str(cert),str(key))
    async def run():
        with pytest.raises(McpError) as error:await transport.connect({'transport':'https','url':fixture.url},verify=False)
        assert error.value.code=='MCP_TLS' and fixture.messages==[]
        with pytest.raises(McpError) as error:await transport.connect({'transport':'https','url':fixture.url})
        assert error.value.code=='MCP_DISCONNECTED' and fixture.messages==[]
    try:asyncio.run(run())
    finally:fixture.close()


def test_stdio_isolated_python_mode_state_and_utf8(tmp_path):
    import shutil
    copy=tmp_path/'synthetic.py';shutil.copyfile(Path(__file__).with_name('v4_mcp_stdio_fixture.py'),copy)
    async def run():
        session=await transport.connect({'transport':'stdio','executable':str(Path(sys.executable).resolve()),'args':['-I','-u',str(copy),'state']})
        try:
            assert (await session.request('tools/list',{}))['tools'][0]['name']=='read_echo'
            result=await session.request('tools/call',{'name':'read_echo','arguments':{'query':'合成证据'}})
            assert result['structuredContent']=={'query':'合成证据'}
            state=json.loads(copy.with_suffix('.state.json').read_text(encoding='utf-8'))
            assert state['calls']==1
        finally:assert (await session.close())['children_reaped']
        assert not psutil.pid_exists(state['parent_pid']) and not psutil.pid_exists(state['child_pid'])
    asyncio.run(run())

@pytest.mark.parametrize('cancel_kind',['cancel','timeout'])
def test_cancelled_native_spawn_retains_and_reaps_real_late_job(monkeypatch,cancel_kind):
    """在挂起/入Job尝试之后模拟原生返回延迟，取消也须等待真实owned进程回收。"""
    import threading
    import time
    entered=threading.Event();release=threading.Event();owned=[];base=transport._JobProcess
    def delayed(config):
        process=base(config);owned.append(process);entered.set()
        release.wait(2)
        return process
    monkeypatch.setattr(transport,'_JobProcess',delayed)
    async def run():
        if cancel_kind=='timeout':monkeypatch.setattr(transport,'CONNECT_SECONDS',.05)
        task=asyncio.create_task(transport.connect(stdio()))
        assert await asyncio.to_thread(entered.wait,2)
        pid=owned[0].pid
        if cancel_kind=='cancel':task.cancel()
        else:await asyncio.sleep(.08)
        assert not task.done(), 'startup must retain ownership until native return'
        release.set()
        if cancel_kind=='cancel':
            with pytest.raises(asyncio.CancelledError):await task
        else:
            with pytest.raises(McpError) as error:await task
            assert error.value.code=='MCP_CONNECT_TIMEOUT'
        assert owned[0].job is None and not psutil.pid_exists(pid)
    try:asyncio.run(run())
    finally:release.set()
