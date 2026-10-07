"""V4-002 实际应用、SQLite及只读网关；不调用模型或Redis。"""
import asyncio
import json
from uuid import uuid4

from test_chat import setup, call


def test_skills_protocol_gateway_binding_and_restart(tmp_path):
    async def scenario():
        app=await setup(tmp_path)
        root=tmp_path/'files';root.mkdir();(root/'synthetic.txt').write_text('fixture',encoding='utf-8')
        try:
            listed=(await call(app,'skills.list'))['result']['skills']
            assert len(listed)==5
            assert next(s for s in listed if s['id']=='file-organize')['available']
            mission=(await call(app,'missions.create',{'client_request_id':str(uuid4()),'title':'合成只读工作流'}))['result']['id']
            grant=(await call(app,'computer.grant',{'mission_id':mission,'root':str(root)}))['result']['grant_id']
            plan=(await call(app,'skills.plan',{'skill_id':'file-organize','inputs':{'path':'.'},'mission_id':mission,'grant_id':grant}))['result']
            params={k:plan[k] for k in ('plan_id','revision','mission_id','grant_id')}
            wrong=await call(app,'skills.execute',params|{'grant_id':str(uuid4())})
            assert not wrong['ok']
            assert (await call(app,'skills.execution',{'plan_id':plan['plan_id']}))['result']['status']=='failed'
            assert app.computer.status(mission)['calls_remaining']==200
            plan=(await call(app,'skills.plan',{'skill_id':'file-organize','inputs':{'path':'.'},'mission_id':mission,'grant_id':grant}))['result']
            params={k:plan[k] for k in ('plan_id','revision','mission_id','grant_id')}
            result=await call(app,'skills.execute',params)
            assert result['ok'],result
            execution=result['result'];assert execution['status']=='completed',execution
            assert len(execution['steps'])==2
            assert 'synthetic.txt' in json.dumps(execution,ensure_ascii=False)
            used=app.computer.status(mission)['calls_remaining'];assert used==198
            repeat=await call(app,'skills.execute',params)
            assert not repeat['ok'] or repeat['result']==execution
            assert app.computer.status(mission)['calls_remaining']==used
            for extra in ({'approved':True},{'model':'other'},{'root':str(root)}):
                assert not (await call(app,'skills.plan',{'skill_id':'file-organize','inputs':{'path':'.'},'mission_id':mission,'grant_id':grant}|extra))['ok']
            assert not (await call(app,'skills.list',{'password':'synthetic'}))['ok']
            await call(app,'computer.revoke',{'mission_id':mission})
            assert not (await call(app,'skills.execute',params))['ok']
            plan_id=plan['plan_id']
        finally:await app.close()
        app=await setup(tmp_path)
        try:
            assert (await call(app,'skills.execution',{'plan_id':plan_id}))['result']['status']=='completed'
            assert app.computer.status(mission)['grant_id'] is None
            assert not (await call(app,'skills.execute',params))['ok']
        finally:await app.close()
    asyncio.run(scenario())
