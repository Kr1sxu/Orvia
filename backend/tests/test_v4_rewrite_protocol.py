"""V4-006：固定协议、本地组合权限与实际来源生命周期；Main mock，零真实云调用。"""
import asyncio
import pytest
from test_chat import setup, create, call
from test_v4_rewrite import Model, document, memory


def test_rewrite_protocol_rejects_private_scope_and_injected_approval(tmp_path):
    async def run():
        app=await setup(tmp_path)
        try:
            cid=(await create(app))['id']
            cases=[('rewrite.preview',{'id':cid,'query':'费用','sources':[]}),('rewrite.preview',{'id':cid,'query':'费用','memory_ids':['0'*64]*4}),('rewrite.generate',{'id':cid,'revision':'0'*64,'approved':True}),('rewrite.search',{'id':cid,'query':'费用','sql':'select private'}),('rewrite.search',{'id':cid,'query':'费用','grant_id':'fake'}),('rewrite.history',{'id':cid,'model':'other'})]
            for method,params in cases:
                response=await call(app,method,params)
                assert not response['ok'] and response['error']['code']=='INVALID_PARAMS'
            result=await call(app,'rewrite.search',{'id':cid,'query':'费用'})
            assert result['ok'] and result['result']['queries']==['费用']
        finally:await app.close()
    asyncio.run(run())


@pytest.mark.parametrize('failure',['missing','timeout'])
def test_rewrite_protocol_model_failure_returns_original_no_replay(tmp_path,failure):
    async def run():
        app=await setup(tmp_path)
        try:
            cid=(await create(app))['id'];calls=[]
            if failure=='timeout':
                async def fail(*args,**kwargs):calls.append(True);raise TimeoutError()
                app.chat.client.complete=fail
            packet=(await call(app,'rewrite.preview',{'id':cid,'query':'费用'}))['result']
            params={'id':cid,'revision':packet['revision']}
            first=await call(app,'rewrite.generate',params)
            assert first['ok'] and first['result']['status']=='original'
            assert first['result']['reason']==('MISSING_CREDENTIAL' if failure=='missing' else 'MODEL_TIMEOUT')
            second=await call(app,'rewrite.generate',params)
            assert second['ok'] and second['result']['reason']=='ALREADY_ATTEMPTED'
            assert len(calls)==(1 if failure=='timeout' else 0)
        finally:await app.close()
    asyncio.run(run())


def test_rewrite_protocol_memory_withdrawal_scope_and_chat_purge(tmp_path):
    async def run():
        app=await setup(tmp_path)
        try:
            cid=(await create(app))['id'];mid=await memory(app,cid,'合成航线');await document(app,cid,'合成航线成本资料')
            model=Model();app.chat.client=model
            packet=(await call(app,'rewrite.preview',{'id':cid,'query':'它的费用','memory_ids':[mid]}))['result']
            result=await call(app,'rewrite.generate',{'id':cid,'revision':packet['revision']})
            assert result['ok'] and result['result']['status']=='rewritten'
            search=await call(app,'rewrite.search',{'id':cid,'query':'它的费用','revision':packet['revision']})
            assert search['ok'] and len(search['result']['queries'])>1
            await app.chat.memory.forget(cid,mid)
            search=await call(app,'rewrite.search',{'id':cid,'query':'它的费用','revision':packet['revision']})
            assert search['ok'] and search['result']['queries']==['它的费用'] and model.calls==1
            assert (await call(app,'chat.delete',{'id':cid}))['ok']
            async with app.store._lock:
                for table in ('rewrite_previews','rewrite_attempts','rewrite_records'):
                    async with app.store._db().execute(f'SELECT count(*) FROM {table} WHERE cid=?',(cid,)) as cursor:assert (await cursor.fetchone())[0]==0
            assert not (await call(app,'rewrite.history',{'id':cid}))['ok']
        finally:await app.close()
    asyncio.run(run())


def test_local_skills_actual_application_no_file_grant_or_cloud(tmp_path):
    async def run():
        app=await setup(tmp_path)
        try:
            cid=(await create(app))['id'];await document(app,cid,'合成成本方案')
            def forbidden(*args,**kwargs):raise AssertionError('本地组合不得调用文件网关')
            async def no_cloud(*args,**kwargs):raise AssertionError('本地组合不得调用模型')
            app.computer.execute=forbidden;app.computer.check_scan=forbidden;app.chat.client.complete=no_cloud
            for skill,inputs,count in [('memory-context',{'query':'合成'},1),('query-rewrite',{'query':'合成','revision':''},2)]:
                planned=await call(app,'skills.plan',{'skill_id':skill,'inputs':inputs,'mission_id':cid,'grant_id':None})
                assert planned['ok'],planned
                plan=planned['result'];assert plan['grant_id'] is None
                approval={key:plan[key] for key in ('plan_id','revision','mission_id','grant_id')}
                completed=await call(app,'skills.execute',approval)
                assert completed['ok'] and completed['result']['status']=='completed',completed
                assert len(completed['result']['steps'])==count
            rejected=await call(app,'skills.plan',{'skill_id':'file-organize','inputs':{'path':'.'},'mission_id':cid,'grant_id':None})
            assert not rejected['ok']
            plan=(await call(app,'skills.plan',{'skill_id':'memory-context','inputs':{'query':'合成'},'mission_id':cid}))['result']
            approval={key:plan[key] for key in ('plan_id','revision','mission_id','grant_id')}
            assert (await call(app,'skills.cancel',approval))['ok']
            assert not (await call(app,'skills.execute',approval))['ok']
        finally:await app.close()
    asyncio.run(run())


def test_local_skills_bounded_context_stops_retrieval_and_purges_chat(tmp_path):
    async def run():
        app=await setup(tmp_path)
        try:
            from test_v4_memory import round_
            cid=(await create(app))['id']
            for _ in range(5):await round_(app,cid,'合成内容'*200,assistant='合成回答'*200)
            retrieval=[]
            async def forbidden(*args,**kwargs):retrieval.append(True);raise AssertionError('上下文受限不得继续检索')
            app.chat.rewrite.search=forbidden
            plan=(await call(app,'skills.plan',{'skill_id':'query-rewrite','inputs':{'query':'合成','revision':''},'mission_id':cid}))['result']
            approval={key:plan[key] for key in ('plan_id','revision','mission_id','grant_id')}
            result=await call(app,'skills.execute',approval)
            assert result['ok'] and result['result']['status']=='limited',result
            assert len(result['result']['steps'])==1 and result['result']['steps'][0]['result']['truncated'] and not retrieval
            assert (await call(app,'chat.delete',{'id':cid}))['ok']
            assert not (await call(app,'skills.execution',{'plan_id':plan['plan_id']}))['ok']
            assert (await call(app,'skills.history'))['result']['executions']==[]
        finally:await app.close()
    asyncio.run(run())


def test_rewrite_cross_session_memory_pending_deletion_blocks_send(tmp_path):
    async def run():
        app=await setup(tmp_path)
        try:
            source=(await create(app))['id'];mid=await memory(app,source,'合成航线');target=(await create(app))['id']
            packet=(await call(app,'rewrite.preview',{'id':target,'query':'它的费用','memory_ids':[mid]}))['result']
            model=Model();app.chat.client=model
            async with app.store._lock:
                await app.store._db().execute("INSERT INTO chat_deletions VALUES(?, 'pending')",(source,))
            preview=await call(app,'rewrite.preview',{'id':target,'query':'它的费用','memory_ids':[mid]})
            assert not preview['ok']
            result=await call(app,'rewrite.generate',{'id':target,'revision':packet['revision']})
            assert result['ok'] and result['result']['status']=='original' and result['result']['reason']=='STALE_REWRITE'
            assert model.calls==0
        finally:await app.close()
    asyncio.run(run())


def test_local_skills_real_directory_grant_does_not_bypass_pending_chat_delete(tmp_path):
    async def run():
        app=await setup(tmp_path)
        try:
            from orvia_backend.skills import SkillError
            cid=(await create(app))['id'];root=tmp_path/'synthetic';root.mkdir()
            grant=(await call(app,'computer.grant',{'mission_id':cid,'root':str(root)}))['result']['grant_id']
            response=await call(app,'skills.plan',{'skill_id':'memory-context','inputs':{'query':'合成'},'mission_id':cid,'grant_id':grant})
            assert response['ok'];plan=response['result']
            async with app.store._lock:
                await app.store._db().execute("DELETE FROM skills_executions WHERE plan_id=?",(plan['plan_id'],))
                await app.store._db().execute("INSERT INTO chat_deletions VALUES(?, 'pending')",(cid,))
            with pytest.raises(SkillError):await app.skills._save(plan,app.skills._execution(plan),insert=True)
            async with app.store._lock:
                async with app.store._db().execute('SELECT count(*) FROM skills_executions WHERE mission_id=?',(cid,)) as cursor:assert (await cursor.fetchone())[0]==0
        finally:await app.close()
    asyncio.run(run())
