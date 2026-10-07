"""V4-010真实SQLite/Browser解析/FTS，HTTP与Main用合成fixture，不调用真实模型。"""
import asyncio
import json
from urllib.parse import urlsplit
from uuid import uuid4
import pytest

from orvia_backend.research import ResearchService,ResearchError
from orvia_backend.browser import BrowserService
from orvia_backend.configuration.client import Completion
from orvia_backend.computer.paths import ToolError
from orvia_backend.memory.service import size
from test_chat import setup,create

class Network:
    def __init__(self):self.calls=[];self.fail=set();self.alias={};self.entered=asyncio.Event();self.block=False;self.text=None;self.callback=None
    async def fetch(self,url,*,limit,**kwargs):
        self.calls.append(url);self.entered.set()
        if self.block:await asyncio.Event().wait()
        if self.callback:await self.callback()
        path=urlsplit(url).path
        if path in self.alias:return 302,{'location':self.alias[path]},b''
        if path in self.fail:return 503,{'content-type':'text/plain'},b'failure'
        if self.text is not None:return 200,{'content-type':'text/plain'},self.text.encode()
        paragraph=('合成航线方案比较。合成方案甲成本十元，合成方案乙成本十二元。仅限合成场景，缺少实测样本。'+path)*8
        html=('<html><head><title>合成页面'+path+'</title></head><body><article><h1>合成航线</h1>'+''.join('<p>'+paragraph+'</p>' for _ in range(3))+'</article></body></html>').encode()
        return 200,{'content-type':'text/html'},html

class Model:
    def __init__(self):self.calls=0;self.callback=None;self.bad=None;self.entered=asyncio.Event();self.block=False
    async def complete(self,profile,messages,**kwargs):
        self.calls+=1;self.entered.set();self.messages=messages
        assert profile.model=='deepseek-flash' and kwargs['max_tokens']==4096
        if self.block:await asyncio.Event().wait()
        if self.callback:await self.callback()
        data=json.loads(messages[-1]['content']);fragments=data['fragments']
        claim={'text':'合成方案甲成本十元','kind':'fact','citations':[fragments[0]['citation']]}
        if self.bad=='cite':claim['citations']=['browser:'+'0'*64+':0']
        if self.bad=='conflict':claim.update(kind='conflict',citations=[f['citation'] for f in fragments[:2]])
        answer='比较：合成方案甲与乙。冲突：当前未确认。缺口：无实测样本。覆盖：仅已发送原文片段。'
        if self.bad=='structure':answer='仅有概述'
        return Completion(json.dumps({'answer':answer,'claims':[claim]},ensure_ascii=False),() if self.bad!='tools' else ({'tool':'bad'},),'stop',{})

async def prepare(tmp_path):
    app=await setup(tmp_path);cid=(await create(app))['id']
    network=Network();app.chat.browser=BrowserService(network=network)
    model=Model();app.chat.client=model
    service=ResearchService(app.store,app.chat);await service.open()
    return app,service,cid,network,model

async def collected(s,cid,count=4):
    task=await s.create(cid,'合成航线方案比较',['https://example.org/'+str(i) for i in range(count)],[],[],[])
    return await s.collect(cid,task['operation_id'])

def test_real_browser_parser_sqlite_fts_precise_batch_then_original_final_not_summary(tmp_path):
    async def run():
        app,s,cid,n,m=await prepare(tmp_path)
        try:
            task=await collected(s,cid)
            assert task['state']=='collected' and task['coverage']['ready_pages']==4 and len(n.calls)==4 and m.calls==0
            async with app.store._lock:
                assert (await s._rows(app.store._db(),'SELECT count(*) FROM context_fts WHERE mission_id=?',(cid,)))[0][0]>0
            batch=await s.preview(cid,task['operation_id'],'batch')
            assert len(batch['source_ids'])==3 and size(batch)<=49152 and m.calls==0
            task=await s.generate(cid,task['operation_id'],'batch',batch['revision'])
            assert task['batches'][0]['state']=='saved'
            second=await s.preview(cid,task['operation_id'],'batch')
            assert len(second['source_ids'])==1
            final=await s.preview(cid,task['operation_id'],'final')
            assert len(final['source_ids'])==4 and len(final['fragments'])==4 and '成本十元' in final['input']
            assert '调研批次摘要' not in final['input'] and all(f['kind']=='browser' for f in final['fragments'])
            task=await s.generate(cid,task['operation_id'],'final',final['revision'])
            message=await app.chat.repository.message(cid,task['final']['message_id'])
            assert task['state']=='ready' and message['kind']=='synthesis' and len(message['data']['coverage'])==4
            assert m.messages==[{'role':'system','content':final['system']},{'role':'user','content':final['input']}]
            with pytest.raises(ResearchError,match='RESEARCH_ALREADY_ATTEMPTED'):await s.generate(cid,task['operation_id'],'final',final['revision'])
            with pytest.raises(ResearchError,match='RESEARCH_COLLECT'):await s.collect(cid,task['operation_id'])
            assert m.calls==2
        finally:await s.close();await app.close()
    asyncio.run(run())

def test_ten_attempts_two_failed_rounds_missing_tavily_and_final_redirect_dedup(tmp_path):
    async def run():
        app,s,cid,n,m=await prepare(tmp_path)
        try:
            n.fail={'/'+str(i) for i in range(10)}
            task=await s.create(cid,'合成问题',['https://example.org/'+str(i) for i in range(10)],['合成检索一','合成检索二'],[],[])
            task=await s.collect(cid,task['operation_id'])
            assert task['state']=='limited' and task['coverage']['attempted_pages']==10 and task['coverage']['search_rounds']==2
            assert all(search['state']=='unavailable' for search in task['searches']) and len(n.calls)==10
            n.fail.clear();n.alias={'/a':'/same','/b':'/same'}
            task=await s.create(cid,'合成问题',['https://example.org/a','https://example.org/b','https://example.org/same','https://example.org/a'])
            assert len(task['urls'])==3
            task=await s.collect(cid,task['operation_id'])
            assert task['coverage']['attempted_pages']==2 and task['coverage']['distinct_final_pages']==1 and task['pages'][1]['state']=='duplicate'
        finally:await s.close();await app.close()
    asyncio.run(run())

@pytest.mark.parametrize('changes',[{'question':''},{'question':'x'*501},{'urls':['http://127.0.0.1/']},{'urls':['https://example.org/'+str(i) for i in range(11)]},{'queries':['a','b','c']},{'queries':['sk-syntheticcredential']},{'sites':['other.example'],'urls':['https://example.org/a']},{'sites':['https://example.org']},{'sources':[{'kind':'browser','evidence_id':'bad'}]}])
def test_invalid_scope_and_budget_plan_zero_requests(tmp_path,changes):
    async def run():
        app,s,cid,n,m=await prepare(tmp_path)
        try:
            args={'cid':cid,'question':'合成','urls':[]};args.update(changes)
            with pytest.raises(ToolError):await s.create(**args)
            assert n.calls==[] and m.calls==0
        finally:await s.close();await app.close()
    asyncio.run(run())

@pytest.mark.parametrize('bad',['cite','conflict','structure','tools'])
def test_invalid_citation_same_origin_conflict_structure_tool_calls_not_saved(tmp_path,bad):
    async def run():
        app,s,cid,n,m=await prepare(tmp_path)
        try:
            task=await collected(s,cid,1)
            stage='batch' if bad=='conflict' else 'final'
            p=await s.preview(cid,task['operation_id'],stage)
            m.bad=bad
            task=await s.generate(cid,task['operation_id'],stage,p['revision'])
            assert task['final']['message_id'] is None and task['error'] and m.calls==1
            assert not any(message['kind']=='synthesis' for message in await app.chat.repository.since(cid,0))
        finally:await s.close();await app.close()
    asyncio.run(run())

@pytest.mark.parametrize('phase',['before','after'])
def test_source_withdraw_before_cloud_or_during_cloud_invalidates_and_no_late_answer(tmp_path,phase):
    async def run():
        app,s,cid,n,m=await prepare(tmp_path)
        try:
            task=await collected(s,cid,1);p=await s.preview(cid,task['operation_id'],'final')
            async def remove():
                async with app.store._lock:
                    await app.store._db().execute('INSERT INTO m20_removed_sources VALUES(?,?,?)',(cid,'browser',task['pages'][0]['evidence_id']))
            if phase=='before':
                await remove()
                with pytest.raises(ToolError):await s.generate(cid,task['operation_id'],'final',p['revision'])
                assert m.calls==0
            else:
                m.callback=remove
                task=await s.generate(cid,task['operation_id'],'final',p['revision'])
                assert task['final']['state']=='failed' and task['final']['message_id'] is None
        finally:await s.close();await app.close()
    asyncio.run(run())

def test_search_offsite_results_not_read_and_failure_counts_round(tmp_path):
    async def run():
        app,s,cid,n,m=await prepare(tmp_path)
        async def search(query,**kwargs):return {'available':True,'error':None,'results':[{'source_url':'https://other.example/a','title':'offsite'},{'source_url':'https://example.org/a','title':'in scope'}]}
        app.chat.browser.web_search=search
        try:
            task=await s.create(cid,'合成',[],['合成'],['example.org'],[])
            task=await s.collect(cid,task['operation_id'])
            assert n.calls==['https://example.org/a'] and task['coverage']['search_rounds']==1 and task['state']=='limited'
        finally:await s.close();await app.close()
    asyncio.run(run())

def test_cancel_waits_for_read_or_model_and_restart_never_replays(tmp_path):
    async def run():
        app,s,cid,n,m=await prepare(tmp_path)
        try:
            task=await s.create(cid,'合成',['https://example.org/a'])
            n.block=True;running=asyncio.create_task(s.collect(cid,task['operation_id']))
            await n.entered.wait();assert await s.has_unresolved(cid)
            result=await s.cancel(cid,task['operation_id'])
            assert running.done() and result['state']=='cancelled' and not await s.has_unresolved(cid)
            n.block=False;task=await collected(s,cid,1);p=await s.preview(cid,task['operation_id'],'final')
            m.block=True;running=asyncio.create_task(s.generate(cid,task['operation_id'],'final',p['revision']))
            await m.entered.wait();result=await s.cancel(cid,task['operation_id'])
            assert running.done() and result['final']['state']=='cancelled' and result['final']['message_id'] is None
            await s.open();assert m.calls==1 and len(n.calls)==2
        finally:await s.close();await app.close()
    asyncio.run(run())

def test_publication_receipt_requires_actual_event_and_same_synthesis_version(tmp_path):
    async def run():
        from orvia_backend.publication.service import _digest
        app,s,cid,n,m=await prepare(tmp_path)
        try:
            task=await collected(s,cid,1);p=await s.preview(cid,task['operation_id'],'final');task=await s.generate(cid,task['operation_id'],'final',p['revision'])
            message=await app.chat.repository.message(cid,task['final']['message_id'])
            data={'filename':'synthetic.docx','format':'docx','revision':'1'*64,'message_id':message['id'],'source_revision':_digest(message['data']),'pages':1}
            with pytest.raises(ToolError,match='RESEARCH_PUBLICATION'):await s.record_publication(cid,message['id'],data)
            await app.chat.repository.append(cid,'system','合成成品已保存','publication',data)
            await s.record_publication(cid,message['id'],data)
            assert (await s.status(cid,task['operation_id']))['publications'][0]['verified']
            with pytest.raises(ToolError,match='RESEARCH_PUBLICATION'):await s.record_publication(cid,message['id'],{**data,'source_revision':'0'*64})
        finally:await s.close();await app.close()
    asyncio.run(run())


def test_real_fts_prefers_middle_original_fragment_and_excludes_unselected_global_source(tmp_path):
    async def run():
        from orvia_backend.context import ContextService
        app,s,cid,n,m=await prepare(tmp_path)
        n.text='背景资料说明。'*450+'\n目标实测航线结果是合成七十七。\n'+'后续补充资料。'*450
        try:
            task=await s.create(cid,'目标实测',['https://example.org/a'])
            task=await s.collect(cid,task['operation_id'])
            await ContextService(app.store).index_text(cid,'browser:'+'f'*64,'目标实测未选择的全局资料。'*100)
            p=await s.preview(cid,task['operation_id'],'final')
            assert '目标实测航线结果是合成七十七' in p['fragments'][0]['text'] and p['fragments'][0]['chunk']>0
            assert all(f['evidence_id']==task['pages'][0]['evidence_id'] for f in p['fragments'])
            assert '未选择的全局资料' not in p['input']
            assert len(await app.chat.natural.materials(cid))<=3,'研究scope不扩大M20全局有效资料'
        finally:await s.close();await app.close()
    asyncio.run(run())


def test_original_full_version_change_after_preview_stops_cloud(tmp_path):
    async def run():
        app,s,cid,n,m=await prepare(tmp_path)
        try:
            task=await collected(s,cid,1);p=await s.preview(cid,task['operation_id'],'final')
            eid=task['pages'][0]['evidence_id']
            async with app.store._lock:
                await app.store._db().execute("UPDATE browser_evidence SET evidence_json=json_set(evidence_json,'$.content',json_extract(evidence_json,'$.content')||'changed suffix') WHERE id=?",(eid,))
            with pytest.raises(ToolError,match='RESEARCH_STALE'):await s.generate(cid,task['operation_id'],'final',p['revision'])
            assert m.calls==0
        finally:await s.close();await app.close()
    asyncio.run(run())


@pytest.mark.parametrize('stage',['collect','final'])
def test_delete_tombstone_and_purge_during_request_never_restore_body(tmp_path,stage):
    async def run():
        app,s,cid,n,m=await prepare(tmp_path)
        async def delete():
            async with app.store._lock:
                db=app.store._db();await db.execute("INSERT INTO chat_deletions VALUES(?,'pending')",(cid,))
                for table in ('research_tasks','research_attempts','research_sources'):await db.execute(f'DELETE FROM {table} WHERE cid=?',(cid,))
                await db.execute('DELETE FROM browser_evidence WHERE mission_id=?',(cid,))
        try:
            if stage=='collect':
                task=await s.create(cid,'合成',['https://example.org/a']);n.callback=delete
                with pytest.raises(ToolError,match='RESEARCH_CONVERSATION'):await s.collect(cid,task['operation_id'])
            else:
                task=await collected(s,cid,1);p=await s.preview(cid,task['operation_id'],'final');m.callback=delete
                with pytest.raises(ToolError,match='RESEARCH_CONVERSATION'):await s.generate(cid,task['operation_id'],'final',p['revision'])
            async with app.store._lock:
                assert not await s._rows(app.store._db(),'SELECT 1 FROM research_tasks WHERE cid=?',(cid,))
                assert not await s._rows(app.store._db(),'SELECT 1 FROM browser_evidence WHERE mission_id=?',(cid,))
                assert not await s._rows(app.store._db(),"SELECT 1 FROM chat_messages WHERE conversation_id=? AND json_extract(message_json,'$.kind')='synthesis'",(cid,))
        finally:await s.close();await app.close()
    asyncio.run(run())


def test_startup_interrupts_only_read_lifecycle_without_replay_or_permanent_delete_block(tmp_path):
    async def run():
        app,s,cid,n,m=await prepare(tmp_path)
        try:
            task=await s.create(cid,'合成',['https://example.org/a']);task['state']='collecting'
            async with app.store._lock:
                db=app.store._db();await db.execute('UPDATE research_tasks SET data_json=? WHERE cid=? AND operation_id=?',(json.dumps(task),cid,task['operation_id']))
                await db.execute('INSERT INTO research_attempts VALUES(?,?,?,?,?,?)',(cid,task['operation_id'],'collect',task['revision'],'running','[]'))
            rebuilt=ResearchService(app.store,app.chat);await rebuilt.open()
            assert (await rebuilt.status(cid,task['operation_id']))['state']=='interrupted' and not await rebuilt.has_unresolved(cid)
            with pytest.raises(ToolError,match='RESEARCH_COLLECT'):await rebuilt.collect(cid,task['operation_id'])
            assert not n.calls and m.calls==0
        finally:await s.close();await app.close()
    asyncio.run(run())


def test_final_explicit_subset_records_real_coverage_omission_and_batch_processed_fact(tmp_path):
    async def run():
        app,s,cid,n,m=await prepare(tmp_path)
        try:
            task=await collected(s,cid,4)
            selected=[{'kind':'browser','evidence_id':task['pages'][0]['evidence_id']}]
            p=await s.preview(cid,task['operation_id'],'final',selected)
            scope=json.loads(p['input'])['scope']
            assert scope['omitted_sources']==3 and any('排除3个来源' in text for text in scope['limitations'])
            task=await s.generate(cid,task['operation_id'],'final',p['revision'])
            assert any('1/4' in text for text in task['coverage']['limitations'])
            message=await app.chat.repository.message(cid,task['final']['message_id'])
            assert len(message['data']['coverage'])==1
        finally:await s.close();await app.close()
    asyncio.run(run())


def test_empty_scope_rejected_and_source_only_scope_valid(tmp_path):
    async def run():
        from orvia_backend.browser.service import evidence
        app,s,cid,n,m=await prepare(tmp_path)
        try:
            with pytest.raises(ToolError,match='RESEARCH_SCOPE'):await s.create(cid,'合成')
            value=await app.chat.evidence.save(cid,evidence('https://example.org/original',mode='http',content='合成明确原文资料。'))
            await app.chat.natural.material_added(cid,'browser',value['evidence_id'])
            task=await s.create(cid,'合成',sources=[{'kind':'browser','evidence_id':value['evidence_id']}])
            task=await s.collect(cid,task['operation_id'])
            assert task['state']=='collected' and not task['pages'] and not n.calls
            assert len((await s.preview(cid,task['operation_id'],'final'))['source_ids'])==1
        finally:await s.close();await app.close()
    asyncio.run(run())


def test_cancelled_search_has_terminal_step_and_missing_main_does_not_retry(tmp_path):
    async def run():
        from orvia_backend.configuration.client import ModelUnavailable
        app,s,cid,n,m=await prepare(tmp_path)
        entered=asyncio.Event()
        async def search(query,**kwargs):entered.set();await asyncio.Event().wait()
        async def missing(*args,**kwargs):m.calls+=1;raise ModelUnavailable('MISSING_CREDENTIAL')
        try:
            app.chat.browser.web_search=search
            task=await s.create(cid,'合成',queries=['合成'])
            running=asyncio.create_task(s.collect(cid,task['operation_id']));await entered.wait()
            task=await s.cancel(cid,task['operation_id'])
            assert running.done() and task['searches'][0]['state']=='failed' and not await s.has_unresolved(cid)
            task=await collected(s,cid,1);p=await s.preview(cid,task['operation_id'],'final')
            app.chat.client.complete=missing
            task=await s.generate(cid,task['operation_id'],'final',p['revision'])
            assert task['error']['code']=='MISSING_CREDENTIAL' and task['final']['message_id'] is None
            with pytest.raises(ToolError,match='RESEARCH_ALREADY_ATTEMPTED'):await s.generate(cid,task['operation_id'],'final',p['revision'])
            assert m.calls==1
        finally:await s.close();await app.close()
    asyncio.run(run())


def test_thirteen_original_sources_default_final_sends_ten_and_approves_exact_omission(tmp_path):
    async def run():
        from orvia_backend.browser.service import evidence
        app,s,cid,n,m=await prepare(tmp_path)
        try:
            sources=[]
            for index in range(3):
                value=await app.chat.evidence.save(cid,evidence('https://example.org/material'+str(index),mode='http',content='合成明确原文资料。'))
                await app.chat.natural.material_added(cid,'browser',value['evidence_id'])
                sources.append({'kind':'browser','evidence_id':value['evidence_id']})
            task=await s.create(cid,'合成',['https://example.org/'+str(i) for i in range(10)],sources=sources)
            task=await s.collect(cid,task['operation_id'])
            p=await s.preview(cid,task['operation_id'],'final');scope=json.loads(p['input'])['scope']
            assert len(p['source_ids'])==10 and scope['available_sources']==13 and scope['omitted_sources']==3
            assert any('10/13' in text and '排除3个来源' in text for text in scope['limitations']) and size(p)<=49152
            assert len(await app.chat.natural.materials(cid))==3 and m.calls==0
        finally:await s.close();await app.close()
    asyncio.run(run())


def test_task_and_independent_attempt_caps_reject_before_requests(tmp_path):
    async def run():
        app,s,cid,n,m=await prepare(tmp_path)
        try:
            tasks=[await s.create(cid,'合成',['https://example.org/a']) for _ in range(20)]
            with pytest.raises(ToolError,match='RESEARCH_LIMIT'):await s.create(cid,'合成',['https://example.org/a'])
            async with app.store._lock:
                for index in range(128):await app.store._db().execute('INSERT INTO research_attempts VALUES(?,?,?,?,?,?)',(cid,str(uuid4()),'collect',str(index),'failed','[]'))
            with pytest.raises(ToolError,match='RESEARCH_LIMIT'):await s.collect(cid,tasks[0]['operation_id'])
            assert not n.calls and m.calls==0 and (await s.status(cid,tasks[0]['operation_id']))['state']=='planned'
        finally:await s.close();await app.close()
    asyncio.run(run())


def test_full_preview_budget_includes_duplicate_fragments_and_url_metadata(tmp_path):
    async def run():
        app,s,cid,n,m=await prepare(tmp_path)
        n.text='合成原文资料。'*200
        try:
            urls=['https://example.org/'+str(i)+'x'*700 for i in range(10)]
            task=await s.create(cid,'合成',urls);task=await s.collect(cid,task['operation_id'])
            assert task['coverage']['ready_pages']==10
            with pytest.raises(ToolError,match='RESEARCH_SEND_LIMIT'):await s.preview(cid,task['operation_id'],'final')
            assert m.calls==0
            p=await s.preview(cid,task['operation_id'],'final',[{'kind':'browser','evidence_id':task['pages'][0]['evidence_id']}])
            assert size(p)<=49152 and p['bytes']<=43008
        finally:await s.close();await app.close()
    asyncio.run(run())


@pytest.mark.parametrize('change',['removed','full_version','not_ready'])
def test_collect_rechecks_explicit_source_scope_before_any_web_request(tmp_path,change):
    async def run():
        from orvia_backend.browser.service import evidence
        app,s,cid,n,m=await prepare(tmp_path)
        try:
            value=await app.chat.evidence.save(cid,evidence('https://example.org/original',mode='http',content='合成已关联原资料。'))
            eid=value['evidence_id'];await app.chat.natural.material_added(cid,'browser',eid)
            task=await s.create(cid,'合成',['https://example.org/a'],sources=[{'kind':'browser','evidence_id':eid}])
            async with app.store._lock:
                db=app.store._db()
                if change=='removed':await db.execute('INSERT INTO m20_removed_sources VALUES(?,?,?)',(cid,'browser',eid))
                if change=='full_version':await db.execute("UPDATE browser_evidence SET evidence_json=json_set(evidence_json,'$.content','合成已更改完整正文') WHERE id=?",(eid,))
                if change=='not_ready':await db.execute("UPDATE m20_materials SET status='failed' WHERE conversation_id=? AND evidence_id=?",(cid,eid))
            with pytest.raises(ToolError):await s.collect(cid,task['operation_id'])
            assert n.calls==[] and m.calls==0 and (await s.status(cid,task['operation_id']))['state']=='planned'
        finally:await s.close();await app.close()
    asyncio.run(run())
