"""V4-007固定Application接口和真实会话生命周期；合成数据、零模型调用。"""
import asyncio
import json
import sys
import pytest
from pathlib import Path
from uuid import uuid4

from test_chat import setup, create, call
from test_v4_mcp import Session, configure, ready


@pytest.mark.parametrize('secret',['', 'synthetic\nline', 'x'*4097, '合成令牌'],ids=['empty','newline','oversize','non_ascii'])
def test_private_initialization_rejects_invalid_mcp_secret_without_echo(tmp_path,secret):
    async def run():
        from orvia_backend.application import Application
        app=Application()
        try:
            await result(app,'hello')
            response=await call(app,'initialize',{'data_directory':str(tmp_path/'db'),'credentials':{},'mcp_credentials':{str(uuid4()):secret}})
            assert not response['ok'] and response['error']['code']=='INVALID_PARAMS'
            if secret:assert secret not in json.dumps(response,ensure_ascii=False)
            assert app.mcp is None
        finally:await app.close()
    asyncio.run(run())


async def result(app, method, params=None):
    response = await call(app, method, params)
    assert response['ok'], response
    return response['result']


def test_fixed_protocol_rejects_injected_authority(tmp_path):
    async def run():
        app = await setup(tmp_path)
        try:
            cid = (await create(app))['id']; sid = str(uuid4())
            for method, params in [
                ('mcp.list', {'url': 'https://a.invalid/mcp'}),
                ('mcp.connect', {'server_id': sid, 'revision': '0'*64, 'approved': True}),
                ('mcp.call', {'id': cid, 'server_id': sid, 'revision': '0'*64, 'executable': sys.executable}),
                ('mcp.call_preview', {'id': cid, 'server_id': sid, 'tool': 'read_echo', 'arguments': {}, 'model': 'other'}),
                ('mcp.history', {'id': cid, 'sql': 'SELECT private'}),
                ('mcp.credential_replace', {'server_id': sid, 'credential': 'synthetic', 'env': {}}),
            ]:
                denied = await call(app, method, params)
                assert not denied['ok'] and denied['error']['code'] == 'INVALID_PARAMS'
            assert (await result(app, 'mcp.list'))['servers'] == []
        finally: await app.close()
    asyncio.run(run())


def test_actual_stdio_protocol_fact_and_chat_purge(tmp_path):
    async def run():
        app = await setup(tmp_path)
        try:
            cid = (await create(app))['id']
            fixture = tmp_path/'synthetic-server.py'
            fixture.write_bytes(Path(__file__).with_name('v4_mcp_stdio_fixture.py').read_bytes())
            config = tmp_path/'mcp.json'
            config.write_text(json.dumps({'name':'合成只读服务','transport':'stdio','executable':sys.executable,'args':['-I','-u',str(fixture),'state'],'allowed_tools':['read_echo','write_delete']}),encoding='utf-8')
            packet = await result(app,'mcp.preview_config',{'path':str(config)})
            server = await result(app,'mcp.configure',{k:packet[k] for k in ('review_id','revision')});sid=server['id']
            connection = await result(app,'mcp.connect_preview',{'server_id':sid})
            tools = await result(app,'mcp.connect',{'server_id':sid,'revision':connection['revision']})
            assert len(tools['tools'])==2 and not tools['tools'][1]['allowed']
            await result(app,'mcp.approve_tools',{'server_id':sid,'revision':tools['revision']})
            params={'id':cid,'server_id':sid,'tool':'read_echo','arguments':{'query':'合成协议证据'}}
            preview=await result(app,'mcp.call_preview',params)
            execution=await result(app,'mcp.call',{'id':cid,'server_id':sid,'revision':preview['revision']})
            assert execution['status']=='completed' and execution['result']['structuredContent']==params['arguments']
            state=json.loads(fixture.with_suffix('.state.json').read_text());assert state['calls']==1
            assert not (await call(app,'mcp.call',{'id':cid,'server_id':sid,'revision':preview['revision']}))['ok']
            assert (await result(app,'mcp.history',{'id':cid}))['executions']==[execution]
            await result(app,'chat.delete',{'id':cid})
            async with app.store._lock:
                db=app.store._db()
                for table in ('mcp_attempts','mcp_executions'):
                    async with db.execute(f'SELECT count(*) FROM {table} WHERE cid=?',(cid,)) as cursor:assert (await cursor.fetchone())[0]==0
                async with db.execute('SELECT count(*) FROM mcp_servers') as cursor:assert (await cursor.fetchone())[0]==1
            assert not (await call(app,'mcp.history',{'id':cid}))['ok']
            closed=await result(app,'mcp.disconnect',{'server_id':sid});assert closed['closed'] and closed['children_reaped']
        finally: await app.close()
    asyncio.run(run())


def test_pending_call_deleted_chat_cannot_restore_body(tmp_path):
    async def run():
        app=await setup(tmp_path); started=asyncio.Event(); release=asyncio.Event()
        async def pending():started.set();await release.wait()
        session=Session(callback=pending)
        async def connector(*args):return session
        app.mcp.connector=connector
        try:
            cid=(await create(app))['id'];sid,_=await ready(app.mcp,tmp_path)
            preview=await app.mcp.call_preview(cid,sid,'get_record',{'query':'合成迟到正文'})
            task=asyncio.create_task(call(app,'mcp.call',{'id':cid,'server_id':sid,'revision':preview['revision']}))
            await started.wait();await result(app,'chat.delete',{'id':cid});release.set()
            response=await task;assert not response['ok'] and session.calls==1
            async with app.store._lock:
                for table in ('mcp_attempts','mcp_executions'):
                    async with app.store._db().execute(f'SELECT count(*) FROM {table} WHERE cid=?',(cid,)) as cursor:assert (await cursor.fetchone())[0]==0
            assert not any(review['value'].get('id')==cid for review in app.mcp._reviews.values())
        finally:release.set();await app.close()
    asyncio.run(run())


def test_private_mcp_credential_restart_never_persists_or_connects(tmp_path):
    async def run():
        app=await setup(tmp_path);secret='synthetic-mcp-private-token-007'
        try:
            sid,_=await configure(app.mcp,tmp_path)
            summary=await result(app,'mcp.credential_replace',{'server_id':sid,'credential':secret})
            assert summary['credential_configured'] and not app.mcp._sessions
            assert secret not in json.dumps(summary)
            async with app.store._lock:
                for table in ('mcp_servers','mcp_tool_reviews','mcp_attempts','mcp_executions'):
                    async with app.store._db().execute(f'SELECT * FROM {table}') as cursor:assert secret not in str(await cursor.fetchall())
        finally:await app.close()
        from orvia_backend.application import Application
        app=Application()
        try:
            await result(app,'hello')
            await result(app,'initialize',{'data_directory':str(tmp_path/'db'),'credentials':{},'mcp_credentials':{sid:secret}})
            listing=await result(app,'mcp.list');assert listing['servers'][0]['credential_configured']
            assert listing['servers'][0]['status']=='disconnected' and not app.mcp._sessions
            await result(app,'mcp.credential_replace',{'server_id':sid,'credential':None})
            assert not (await result(app,'mcp.list'))['servers'][0]['credential_configured']
        finally:await app.close()
    asyncio.run(run())
