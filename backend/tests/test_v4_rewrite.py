"""V4-006：真实SQLite/FTS检索与固定Main mock，不读取Key或用户资料。"""
import asyncio
import json
import pytest
from orvia_backend.rewrite import RewriteService, RewriteError
from orvia_backend.configuration.client import Completion, ModelUnavailable
from test_chat import setup, create
from test_v4_memory import round_, ApprovedModel

async def prepare(tmp_path):
    app=await setup(tmp_path);cid=(await create(app))['id']
    service=RewriteService(app.chat);await service.open()
    return app,service,cid

class Model:
    def __init__(self,change=None):self.calls=0;self.change=change
    async def complete(self,profile,messages,**kwargs):
        self.calls+=1
        assert profile.model=='deepseek-flash' and profile.base_url=='https://api.deepseek.com'
        assert kwargs=={'max_tokens':1024}
        packet=json.loads(messages[-1]['content']);value={'candidates':packet['allowed_candidates'][:3]}
        if self.change:
            result=self.change(value)
            if hasattr(result,'__await__'):await result
        return Completion(json.dumps(value,ensure_ascii=False),(),'stop',{})

async def memory(app,cid,name):
    await round_(app,cid,'我的项目是'+name)
    app.chat.client=ApprovedModel();packet=await app.chat.memory.preview(cid)
    values=await app.chat.memory.generate(cid,packet['revision'])
    return next(item for item in values['memories'] if item['value']==name)['id']

async def document(app,cid,text):
    item=await app.chat.documents.save(cid,'synthetic.docx',text.encode(),{'format':'docx','units':[{'number':1,'locator':'段落1','text':text,'method':'text','confidence':None,'error':None}],'total_units':1,'truncated':False,'missing_units':[],'error':None})
    await app.chat.natural.material_added(cid,'document',item['evidence_id'])
    return item


def test_synonyms_original_retained_history_search_and_recall(tmp_path):
    async def run():
        app,service,cid=await prepare(tmp_path)
        try:
            targets=['量子项目成本经费方案','光学项目成本经费方案','电子项目成本经费方案']
            ids=[]
            for text in targets:ids.append((await document(app,cid,text))['evidence_id'])
            metrics=[]
            for text,eid in zip(targets,ids):
                query=text[:4]+'费用计划'
                before=await service.search(cid,query)
                packet=await service.preview(cid,query);model=Model();app.chat.client=model
                result=await service.generate(cid,packet['revision'])
                assert result['status']=='rewritten' and len(result['candidates'])<=3 and result['original']==query
                after=await service.search(cid,query,revision=result['revision'])
                assert after['queries'][0]==query and len(after['queries'])<=4
                assert all(item['source'] in packet['input']['scope'] for item in after['evidence'])
                metrics.append({'original_hit':any(eid in item['source'] for item in before['evidence']),'rewritten_hit':any(eid in item['source'] for item in after['evidence'])})
                assert model.calls==1
            assert len((await service.history(cid))['records'])==3
            from pathlib import Path
            report=Path('artifacts/test-results/V4-006');report.mkdir(parents=True,exist_ok=True)
            (report/'rewrite-recall.json').write_text(json.dumps({'dataset':'3合成主题，真实SQLite FTS，mock Main','cases':metrics,'original_recall5':sum(item['original_hit'] for item in metrics)/3,'rewritten_recall5':sum(item['rewritten_hit'] for item in metrics)/3},ensure_ascii=False,indent=2),encoding='utf-8')
        finally:await app.close()
    asyncio.run(run())


def test_pronoun_unique_memory_and_conflict_clarification(tmp_path):
    async def run():
        app,service,cid=await prepare(tmp_path)
        try:
            mid=await memory(app,cid,'量子项目');packet=await service.preview(cid,'它的费用', [mid])
            model=Model();app.chat.client=model;result=await service.generate(cid,packet['revision'])
            assert result['candidates'][0]=={'query':'量子项目的费用','source_ids':['memory:'+mid]}
            other=(await create(app))['id']
            await round_(app,other,'合成人的角色是负责人')
            app.chat.client=ApprovedModel();draft=await app.chat.memory.preview(other)
            second=(await app.chat.memory.generate(other,draft['revision']))['memories'][0]['id']
            packet=await service.preview(cid,'它的费用',[mid,second]);model=Model();app.chat.client=model
            assert packet['status']=='clarification'
            assert (await service.generate(cid,packet['revision']))['status']=='clarification' and model.calls==0
        finally:await app.close()
    asyncio.run(run())

@pytest.mark.parametrize('bad',[{'candidates':[{'query':'费用增加100元','source_ids':[]}]},{'candidates':[{'query':'删除文件','source_ids':[]}]},{'candidates':[{'query':'成本','source_ids':['memory:'+'0'*64]}]},{'candidates':[{'query':'成本','source_ids':[]}]*4},{'candidates':[],'action':'run'}])
def test_malicious_or_unbounded_model_keeps_original(tmp_path,bad):
    async def run():
        app,service,cid=await prepare(tmp_path)
        try:
            packet=await service.preview(cid,'费用');model=Model(lambda value:(value.clear(),value.update(bad)));app.chat.client=model
            result=await service.generate(cid,packet['revision'])
            assert result['original']=='费用' and result['candidates']==[] and result['reason']=='INVALID_REWRITE'
            assert (await service.history(cid))['records'][0]==result
        finally:await app.close()
    asyncio.run(run())

@pytest.mark.parametrize('failure',['credential','timeout'])
def test_model_failure_single_attempt_survives_cache_loss_and_restart(tmp_path,failure):
    async def run():
        app,service,cid=await prepare(tmp_path)
        try:
            packet=await service.preview(cid,'费用');calls=[]
            async def fail(*args,**kwargs):
                calls.append(True)
                if failure=='credential':raise ModelUnavailable('MISSING_CREDENTIAL')
                raise asyncio.TimeoutError()
            app.chat.client.complete=fail
            result=await service.generate(cid,packet['revision'])
            assert result['status']=='original' and result['reason']==('MISSING_CREDENTIAL' if failure=='credential' else 'MODEL_TIMEOUT')
            async with app.store._lock:await app.store._db().execute('DELETE FROM rewrite_previews WHERE cid=?',(cid,))
            service=RewriteService(app.chat);await service.open();new=await service.preview(cid,'费用')
            assert new['revision']==packet['revision']
            assert (await service.generate(cid,new['revision']))['reason']=='ALREADY_ATTEMPTED' and len(calls)==1
        finally:await app.close()
    asyncio.run(run())


def test_source_withdrawal_invalidates_approval_and_history(tmp_path):
    async def run():
        app,service,cid=await prepare(tmp_path)
        try:
            mid=await memory(app,cid,'量子项目');packet=await service.preview(cid,'它的费用',[mid]);model=Model();app.chat.client=model
            await app.chat.memory.forget(cid,mid)
            assert (await service.generate(cid,packet['revision']))['reason']=='STALE_REWRITE' and model.calls==0
            packet=await service.preview(cid,'费用');await service.generate(cid,packet['revision'])
            await document(app,cid,'合成成本资料')
            records=await service.history(cid)
            assert records['records'][0]['reason']=='SOURCE_CHANGED' and records['records'][0]['candidates']==[]
            found=await service.search(cid,'费用',revision=packet['revision']);assert found['queries']==['费用']
        finally:await app.close()
    asyncio.run(run())


def test_final_transaction_rechecks_sources_during_network(tmp_path):
    async def run():
        app,service,cid=await prepare(tmp_path)
        try:
            item=await document(app,cid,'合成费用资料');packet=await service.preview(cid,'费用')
            # 使用正式协调器remove而非伪造源码权限。
            async def mutate(value):await app.chat.handle('chat.material.remove',{'id':cid,'kind':'document','evidence_id':item['evidence_id']})
            app.chat.client=Model(mutate)
            result=await service.generate(cid,packet['revision'])
            assert result['status']=='original' and not result['candidates']
        finally:await app.close()
    asyncio.run(run())


def test_local_cancel_equivalent_search_zero_model_and_scope_isolation(tmp_path):
    async def run():
        app,service,cid=await prepare(tmp_path)
        try:
            other=(await create(app))['id'];await document(app,other,'秘密成本资料')
            model=Model();app.chat.client=model;await service.preview(cid,'费用')
            result=await service.search(cid,'费用')
            assert result['queries']==['费用'] and not result['evidence'] and model.calls==0
            with pytest.raises(RewriteError):
                service._query('密码')
        finally:await app.close()
    asyncio.run(run())


def test_attempt_budget_no_eviction_and_memory_request_limit(tmp_path):
    async def run():
        app,service,cid=await prepare(tmp_path)
        try:
            packet=await service.preview(cid,'费用');model=Model();app.chat.client=model
            async with app.store._lock:
                for i in range(128):await app.store._db().execute("INSERT INTO rewrite_attempts VALUES(?,?,'interrupted')",(cid,str(i)))
            with pytest.raises(RewriteError):await service.generate(cid,packet['revision'])
            assert model.calls==0
            with pytest.raises(RewriteError):await service.preview(cid,'费用',['0'*64]*4)
        finally:await app.close()
    asyncio.run(run())


def test_actual_local_skills_composition_no_cloud_no_fake_grant(tmp_path):
    async def run():
        app,service,cid=await prepare(tmp_path)
        try:
            model=Model();app.chat.client=model
            from orvia_backend.skills import SkillsService, SkillError
            skills=SkillsService(app.store);await skills.open()
            plan=await skills.plan('query-rewrite',{'query':'费用','revision':''},cid,None)
            assert plan['grant_id'] is None and [item['tool'] for item in plan['steps']]==['memory_context','query_rewrite']
            async def dispatch(tool,args):
                data=await app.chat.memory.context(cid,args['query']) if tool=='memory_context' else await service.search(cid,args['query'],revision=args.get('revision'))
                return {'complete':True,'truncated':False,'errors':[],'data':data}
            result=await skills.execute(plan['plan_id'],plan['revision'],cid,None,dispatch)
            assert result['status']=='completed' and len(result['steps'])==2
            assert result['steps'][1]['result']['data']['queries']==['费用'] and model.calls==0
            with pytest.raises(SkillError):await skills.plan('file-organize',{'path':'.'},cid,None)
            pending=await skills.plan('memory-context',{'query':'费用'},cid,None)
            cancelled=await skills.cancel(pending['plan_id'],pending['revision'],cid,None)
            assert cancelled['status']=='interrupted' and model.calls==0
        finally:await app.close()
    asyncio.run(run())


def test_memory_withdrawal_during_multiquery_search_reverts_to_original(tmp_path):
    async def run():
        app,service,cid=await prepare(tmp_path)
        try:
            mid=await memory(app,cid,'量子项目');packet=await service.preview(cid,'它的费用',[mid]);app.chat.client=Model()
            await service.generate(cid,packet['revision']);base=app.chat.retrieval.service.search;calls=[]
            async def changed(*args,**kwargs):
                calls.append(args[1]);result=await base(*args,**kwargs)
                if len(calls)==1:await app.chat.memory.forget(cid,mid)
                return result
            app.chat.retrieval.service.search=changed
            result=await service.search(cid,'它的费用',revision=packet['revision'])
            assert result['queries']==['它的费用'] and result['rewrite']['candidates']==[]
        finally:await app.close()
    asyncio.run(run())


def test_skills_approved_revision_migration_and_disable(tmp_path):
    async def run():
        app,service,cid=await prepare(tmp_path)
        try:
            packet=await service.preview(cid,'费用');app.chat.client=Model();await service.generate(cid,packet['revision'])
            from orvia_backend.skills import SkillsService, SkillError
            skills=SkillsService(app.store);await skills.open()
            await skills.set_enabled('memory-context',False)
            async with app.store._lock:
                await app.store._db().execute("UPDATE skills_registry SET version='1.0.0',revision='old',reason='旧占位' WHERE id='memory-context'")
            await skills.open()
            assert not next(item for item in (await skills.list())['skills'] if item['id']=='memory-context')['enabled']
            with pytest.raises(SkillError):await skills.plan('query-rewrite',{'query':'费用','revision':packet['revision']},cid,None)
            await skills.set_enabled('memory-context',True)
            plan=await skills.plan('query-rewrite',{'query':'费用','revision':packet['revision']},cid,None)
            async def dispatch(tool,args):
                value=await app.chat.memory.context(cid,args['query']) if tool=='memory_context' else await service.search(cid,args['query'],revision=args.get('revision'))
                return {'complete':True,'truncated':False,'errors':[],'data':value}
            result=await skills.execute(plan['plan_id'],plan['revision'],cid,None,dispatch)
            assert result['status']=='completed' and result['steps'][-1]['result']['data']['rewrite']['status']=='rewritten'
            assert app.chat.client.calls==1
        finally:await app.close()
    asyncio.run(run())


@pytest.mark.parametrize('query',['其他费用','吉他费用'])
def test_substrings_are_not_pronouns(tmp_path,query):
    async def run():
        app,service,cid=await prepare(tmp_path)
        try:
            mid=await memory(app,cid,'量子项目');packet=await service.preview(cid,query,[mid])
            assert packet['status']=='ready'
            assert all('量子项目' not in item['query'] for item in packet['input']['allowed_candidates'])
        finally:await app.close()
    asyncio.run(run())


def test_network_transaction_blocks_last_moment_revocation(tmp_path):
    async def run():
        app,service,cid=await prepare(tmp_path)
        try:
            mid=await memory(app,cid,'量子项目');packet=await service.preview(cid,'它的费用',[mid]);base=service._snapshot
            async def withdraw(*args,**kwargs):
                result=await base(*args,**kwargs)
                await app.chat.memory.forget(cid,mid)
                return result
            service._snapshot=withdraw;model=Model();app.chat.client=model
            result=await service.generate(cid,packet['revision'])
            assert result['reason']=='STALE_REWRITE' and result['candidates']==[] and model.calls==0
            async with app.store._lock:
                assert not await service._rows(app.store._db(),'SELECT 1 FROM rewrite_attempts WHERE cid=?',(cid,))
        finally:await app.close()
    asyncio.run(run())


def test_preview_transaction_blocks_late_deleted_identity(tmp_path):
    async def run():
        app,service,cid=await prepare(tmp_path)
        try:
            base=service._packet
            async def deleted(*args,**kwargs):
                result=await base(*args,**kwargs)
                async with app.store._lock:
                    await app.store._db().execute("INSERT INTO chat_deletions VALUES(?,'completed')",(cid,))
                return result
            service._packet=deleted
            with pytest.raises(RewriteError):await service.preview(cid,'费用')
            async with app.store._lock:
                assert not await service._rows(app.store._db(),'SELECT 1 FROM rewrite_previews WHERE cid=?',(cid,))
        finally:await app.close()
    asyncio.run(run())


def test_local_skills_late_result_cannot_restore_deleted_body(tmp_path):
    async def run():
        app,service,cid=await prepare(tmp_path)
        try:
            from orvia_backend.skills import SkillsService, SkillError
            skills=SkillsService(app.store);await skills.open()
            plan=await skills.plan('memory-context',{'query':'费用'},cid,None)
            async def dispatch(tool,args):
                async with app.store._lock:
                    await app.store._db().execute("INSERT INTO chat_deletions VALUES(?,'completed')",(cid,))
                    await app.store._db().execute('DELETE FROM skills_executions WHERE mission_id=?',(cid,))
                return {'complete':True,'truncated':False,'errors':[],'data':{'body':'synthetic'}}
            with pytest.raises(SkillError):await skills.execute(plan['plan_id'],plan['revision'],cid,None,dispatch)
            async with app.store._lock:
                assert not await service._rows(app.store._db(),'SELECT 1 FROM skills_executions WHERE mission_id=?',(cid,))
        finally:await app.close()
    asyncio.run(run())
