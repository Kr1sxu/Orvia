"""V4-011实际Application/SQLite/HTTP TCP；合成服务，不调用云模型或用户资料。"""
import asyncio
import json
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4

from test_chat import setup, create, call
from orvia_backend.browser.network import SafeHTTP
from orvia_backend.context import ContextService
from v4_research_fixture import LocalSocketTransport, dns


async def result(app, method, params):
    reply = await call(app, method, params)
    assert reply['ok'], reply
    return reply['result']


def test_real_tcp_three_attempts_fact_history_restart_purge_and_research(tmp_path):
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            attempt = requests.count(self.path)
            body = '合成安全读取：事实42。'.encode()
            self.send_response(503 if attempt <= 2 else 200)
            self.send_header('Content-Type','text/plain; charset=utf-8')
            self.send_header('Content-Length',str(len(body)))
            self.end_headers();self.wfile.write(body)
        def log_message(self,*_args):
            pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    async def run():
        app=await setup(tmp_path)
        try:
            cid=(await create(app))['id'];other=(await create(app))['id']
            app.browser.network=SafeHTTP(transport=LocalSocketTransport(server.server_port),resolver=dns)
            snapshot=await result(app,'chat.browser.read',{'id':cid,'request_id':str(uuid4()),'url':'http://research.example/read','mode':'http'})
            assert requests==['/read']*3
            source=snapshot['sources'][0]
            original=await app.chat.evidence.get(cid,source['evidence_id'])
            assert '事实42' in original['content']
            history=await result(app,'retry.history',{'id':cid})
            records=[r for r in history['runs'] if r['tool']=='browser.static_read']
            assert len(records)==1 and records[0]['state']=='succeeded'
            assert [a['sequence'] for a in records[0]['attempts']]==[1,2,3]
            assert [a['reason'] for a in records[0]['attempts']]==['http_503','http_503','success']
            assert 'research.example' not in json.dumps(history) and '事实42' not in json.dumps(history)
            assert not (await result(app,'retry.history',{'id':other}))['runs']
            for extra in ({'approved':True},{'tool':'shell.execute'},{'max_attempts':9}):
                assert not (await call(app,'retry.history',{'id':cid,**extra}))['ok']
            task=await result(app,'research.create',{'id':cid,'question':'合成事实','urls':['http://research.example/research']})
            collected=await result(app,'research.collect',{'id':cid,'operation_id':task['operation_id']})
            assert collected['coverage']['attempted_pages']==1 and requests[-3:]==['/research']*3
            current=await result(app,'retry.history',{'id':cid})
            assert len([r for r in current['runs'] if r['tool']=='browser.static_read'])==2
            await app.close();app=await setup(tmp_path)
            restored=await result(app,'retry.history',{'id':cid})
            assert restored==current and len(requests)==6
            await result(app,'chat.delete',{'id':cid})
            assert not (await call(app,'retry.history',{'id':cid}))['ok']
            async with app.store._lock:
                for table in ('retry_runs','retry_attempts'):
                    async with app.store._db().execute(f'SELECT count(*) FROM {table} WHERE cid=?',(cid,)) as cursor:
                        assert (await cursor.fetchone())[0]==0
        finally:
            await app.close()
    try:
        asyncio.run(run())
    finally:
        server.shutdown();server.server_close()


def test_context_adapter_retries_only_pure_select_and_records_real_sqlite(tmp_path):
    async def run():
        app=await setup(tmp_path)
        try:
            cid=(await create(app))['id']
            await ContextService(app.store).index_text(cid,'合成.txt','合成数据库事实42')
            original=app.store.search_context;calls=[]
            async def transient(*args):
                calls.append(args)
                if len(calls)<3:
                    error=sqlite3.OperationalError('synthetic transient')
                    error.sqlite_errorcode=sqlite3.SQLITE_BUSY
                    raise error
                return await original(*args)
            app.store.search_context=transient
            found=await result(app,'context.search',{'mission_id':cid,'query':'数据库'})
            assert len(calls)==3 and len(found['evidence'])==1
            history=await result(app,'retry.history',{'id':cid})
            record=history['runs'][0]
            assert record['tool']=='context.sqlite_read' and record['state']=='succeeded'
            assert [a['reason'] for a in record['attempts']]==['sqlite_busy','sqlite_busy','success']
            before=len(history['runs'])
            await result(app,'context.index',{'mission_id':cid,'source':'新.txt','text':'合成内容'})
            assert len((await result(app,'retry.history',{'id':cid}))['runs'])==before
            assert not (await call(app,'context.search',{'mission_id':cid,'query':'bad*'}))['ok']
            assert len(calls)==3
        finally:
            await app.close()
    asyncio.run(run())


def test_independent_mission_read_keeps_original_capability(tmp_path):
    """不是聊天会话的既有Mission仍可安全读取，不因新history表排除原能力。"""
    from test_browser import service,response
    async def run():
        app=await setup(tmp_path)
        try:
            mission=await result(app,'missions.create',{'client_request_id':str(uuid4()),'title':'合成独立任务'})
            app.browser.network=service(lambda request:response('合成独立任务')).network
            page=await result(app,'browser.read',{'mission_id':mission['id'],'url':'https://example.com/synthetic','mode':'http'})
            assert page['error'] is None and page['content']=='合成独立任务'
        finally:
            await app.close()
    asyncio.run(run())


def test_local_select_timeout_is_not_reported_as_model_failure(tmp_path):
    async def run():
        app=await setup(tmp_path)
        try:
            cid=(await create(app))['id']
            async def slow(*_args):
                await asyncio.sleep(10)
                return []
            app.store.search_context=slow
            reply=await call(app,'context.search',{'mission_id':cid,'query':'合成'})
            assert reply['error']['code']=='SEARCH_TIMEOUT'
            record=(await result(app,'retry.history',{'id':cid}))['runs'][0]
            assert record['state']=='timed_out' and len(record['attempts'])==1
        finally:
            await app.close()
    asyncio.run(run())


def test_natural_cancel_during_real_http_backoff_stops_next_attempt(tmp_path):
    requests=[]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            self.send_response(503);self.send_header('Content-Length','0');self.end_headers()
        def log_message(self,*_args):
            pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    async def run():
        app=await setup(tmp_path)
        try:
            cid=(await create(app))['id'];rid=str(uuid4())
            app.browser.network=SafeHTTP(transport=LocalSocketTransport(server.server_port),resolver=dns)
            pending=asyncio.create_task(call(app,'chat.natural',{'id':cid,'request_id':rid,'text':'读取 http://research.example/cancel'}))
            for _ in range(200):
                history=await result(app,'retry.history',{'id':cid})
                if history['runs'] and history['runs'][0]['attempts'] and history['runs'][0]['attempts'][0]['reason']=='http_503':
                    break
                await asyncio.sleep(.005)
            else:
                raise AssertionError('没有实际进入可取消的退避阶段')
            assert (await result(app,'chat.cancel',{'id':cid,'request_id':rid}))['cancelled']
            ended=await pending;assert ended['ok'] and ended['result']['task_progress']['state']=='cancelled'
            assert requests==['/cancel']
            history=await result(app,'retry.history',{'id':cid})
            assert history['runs'][0]['state']=='cancelled' and len(history['runs'][0]['attempts'])==1
            assert not ended['result']['sources']
        finally:
            await app.close()
    try:
        asyncio.run(run())
    finally:
        server.shutdown();server.server_close()
