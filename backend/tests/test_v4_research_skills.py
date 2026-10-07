"""V4-010真实SQLite/LangGraph/业务准备与简报预览；不采集网页、不调用模型或保存成品。"""
import asyncio
import copy
import json
from uuid import uuid4
import pytest
from orvia_backend.skills import SkillsService,SkillError
from orvia_backend.skills.service import _builtin,OPEN_OBJECT,_size,_research_ready
from orvia_backend.research import ResearchService
from orvia_backend.chat.contracts import PublicationPreview
from orvia_backend.computer.contracts import GrantRequest,ToolRequest
from test_chat import setup,create


async def prepare(tmp_path):
    app=await setup(tmp_path);cid=(await create(app))['id']
    research=ResearchService(app.store,app.chat);await research.open()
    return app,app.skills,research,cid


async def forbidden(*args,**kwargs):raise AssertionError('Skill不得偷偷采集、调用模型或保存文件')


def block_external(app,research,monkeypatch):
    monkeypatch.setattr(app.chat.client,'complete',forbidden)
    monkeypatch.setattr(app.chat.publication if hasattr(app.chat,'publication') else app.chat,'publication_save' if not hasattr(app.chat,'publication') else 'save',forbidden,raising=False)
    monkeypatch.setattr(research,'collect',forbidden)


async def dispatch(app,research,cid,tool,args,grant=None):
    if tool=='research_create':
        task=await research.create(cid,args['query'],urls=[line.strip() for line in args['urls'].splitlines() if line.strip()])
        return {'complete':False,'truncated':False,'errors':[],'status':'pending_approval','data':task}
    if tool=='research_status':
        task=await research.status(cid,args['task_id'])
        return {'complete':False,'truncated':False,'errors':[],'status':'pending_approval','data':task}
    if tool=='report_build_preview':
        message=await app.chat.repository.message(cid,args['message_id']);data=message['data']
        packet=await app.chat.publication_preview(PublicationPreview(id=cid,**args,answer=data['answer'],claim_texts=[claim['text'] for claim in data['claims']]))
        return {'complete':False,'truncated':False,'errors':[],'status':'pending_save','data':packet}
    if tool=='query_rewrite':
        packet=await app.chat.rewrite.search(cid,args['query'],[],args.get('revision'))
        return {'complete':True,'truncated':False,'errors':[],'data':packet}
    return app.computer.execute('computer',ToolRequest.model_validate({'mission_id':cid,'grant_id':grant,'call':{'tool':tool,'arguments':args}}))


async def execute(skills,plan,callback):
    return await skills.execute(plan['plan_id'],plan['revision'],plan['mission_id'],plan['grant_id'],callback)


async def register(skills,tmp_path,manifest):
    root=tmp_path/manifest['id'];root.mkdir()
    (root/'SKILL.md').write_text('合成声明式组合。权限由外部可信审批提供。',encoding='utf-8')
    (root/'workflow.json').write_text(json.dumps(manifest,ensure_ascii=False),encoding='utf-8')
    preview=await skills.preview_import(str(root));await skills.register(preview['review_id'],preview['revision'])


def custom(sid,steps,dependencies=None):
    manifest=copy.deepcopy(next(_builtin())[0])
    return {**manifest,'id':sid,'name':'合成组合','dependencies':dependencies or [],'input_schema':{'type':'object','properties':{},'required':[]},'steps':steps,'output_schema':OPEN_OBJECT,'output':{'observation':{'from_step':steps[-1]['id']}}}


def toolstep(identifier,tool,args):return {'id':identifier,'tool':tool,'arguments':args,'output_schema':OPEN_OBJECT}


def ready_stage(task,mid):
    """一致的合成采集/综合阶段fixture；不能当作真实网页访问或模型生成证据。"""
    task.update(state='ready',final={'state':'saved','message_id':mid,'revision':'b'*64})
    task['pages']=[{'url':'https://example.com/','final_url':'https://example.com/','state':'ready','evidence_id':'c'*64,'error':None}]
    task['coverage'].update(attempted_pages=1,ready_pages=1,distinct_final_pages=1)
    return task


async def saved_synthesis(app,cid):
    source=await app.chat.documents.save(cid,'合成资料.docx',b'synthetic',{'format':'docx','units':[{'number':1,'locator':'段落1','text':'合成资料成本为20。','method':'text','confidence':None,'error':None}],'total_units':1,'truncated':False,'missing_units':[],'error':None})
    eid=source['evidence_id']
    await app.chat.repository.append(cid,'assistant','合成已保存综合','synthesis',{'answer':'合成资料说明成本。','claims':[{'text':'合成成本为20。','kind':'fact','citations':['C1']}],'citations':[{'citation':'C1','kind':'document','evidence_id':eid,'locator':'段落1'}],'coverage':[{'kind':'document','evidence_id':eid,'title':'合成资料.docx'}],'revision':'a'*64,'model':'deepseek-flash','usage':{}})
    return (await app.chat.repository.messages(cid))[0][-1]['id']


def test_real_web_research_builtin_creates_fact_pending_no_fetch_cloud(tmp_path,monkeypatch):
    async def run():
        app,skills,research,cid=await prepare(tmp_path);block_external(app,research,monkeypatch)
        try:
            items=(await skills.list())['skills']
            assert all(item['available'] for item in items)
            assert next(item for item in items if item['id']=='web-research')['version']=='1.1.0'
            plan=await skills.plan('web-research',{'query':'比较合成资料','urls':'https://example.com/a\nhttps://example.org/b'},cid,None)
            result=await execute(skills,plan,lambda tool,args:dispatch(app,research,cid,tool,args))
            assert result['status']=='limited' and len(result['steps'])==1
            value=result['steps'][0]['result'];task=value['data']
            assert value['status']=='pending_approval' and task['state']=='planned' and task['pages']==[] and task['searches']==[]
            assert await research.status(cid,task['operation_id'])==task
            assert await skills.get_execution(plan['plan_id'])==result and _size(result)<=32768
        finally:await app.close()
    asyncio.run(run())


@pytest.mark.parametrize('format',['docx','pptx','pdf'])
def test_real_report_preview_with_saved_citations_is_pending_save(tmp_path,monkeypatch,format):
    async def run():
        app,skills,research,cid=await prepare(tmp_path);block_external(app,research,monkeypatch)
        try:
            mid=await saved_synthesis(app,cid)
            plan=await skills.plan('report-build',{'message_id':mid,'format':format,'title':'合成简报'},cid,None)
            result=await execute(skills,plan,lambda tool,args:dispatch(app,research,cid,tool,args))
            assert result['status']=='limited' and result['steps'][0]['result']['status']=='pending_save'
            packet=result['steps'][0]['result']['data']
            assert packet['format']==format and packet['references'][0]['citation']=='C1' and packet['source_revision']
            assert not list(tmp_path.glob('*.docx')) and not list(tmp_path.glob('*.pptx')) and not list(tmp_path.glob('*.pdf'))
        finally:await app.close()
    asyncio.run(run())


def test_actual_file_organize_text_retrieval_then_pending_research_stops_report(tmp_path,monkeypatch):
    async def run():
        app,skills,research,cid=await prepare(tmp_path);block_external(app,research,monkeypatch)
        try:
            root=tmp_path/'synthetic-files';root.mkdir();(root/'合成.txt').write_text('合成成本为20。',encoding='utf-8')
            grant=app.computer.grant(GrantRequest(mission_id=cid,root=str(root),allow_text=True))['grant_id']
            manifest=custom('mixed-research',[
                {'id':'files','skill':'file-organize','arguments':{'path':'.'},'output_schema':OPEN_OBJECT},
                toolstep('text','read_text_file',{'path':'合成.txt'}),
                toolstep('retrieve','query_rewrite',{'query':'合成成本','revision':''}),
                toolstep('research','research_create',{'query':'合成成本','urls':'https://example.com/'}),
                toolstep('report','report_build_preview',{'message_id':str(uuid4()),'format':'docx','title':'不会执行'})],['file-organize'])
            await register(skills,tmp_path,manifest)
            with pytest.raises(SkillError):await skills.plan('mixed-research',{},cid,None)
            plan=await skills.plan('mixed-research',{},cid,grant);calls=[]
            async def callback(tool,args):calls.append(tool);return await dispatch(app,research,cid,tool,args,grant)
            result=await execute(skills,plan,callback)
            assert result['status']=='limited' and [s['status'] for s in result['steps']]==['completed']*4+['limited']
            assert calls==['list_directory','analyze_directory_space','read_text_file','query_rewrite','research_create']
            assert 'report_build_preview' not in calls
        finally:await app.close()
    asyncio.run(run())


def test_pending_envelope_cannot_claim_completed_even_complete_true(tmp_path):
    async def run():
        app,skills,research,cid=await prepare(tmp_path)
        try:
            manifest=custom('pending-chain',[toolstep('status','research_status',{'task_id':str(uuid4())}),toolstep('later','memory_context',{'query':'不得执行'})])
            await register(skills,tmp_path,manifest);plan=await skills.plan('pending-chain',{},cid,None);calls=[]
            async def callback(tool,args):calls.append(tool);return {'complete':True,'truncated':False,'errors':[],'status':'pending_approval','data':{'state':'planned'}}
            result=await execute(skills,plan,callback)
            assert result['status']=='limited' and calls==['research_status']
        finally:await app.close()
    asyncio.run(run())


@pytest.mark.parametrize('sid,inputs',[('web-research',{'query':'合成','urls':'https://example.com/'}),('report-build',{'message_id':str(uuid4()),'format':'docx','title':'合成'})])
def test_preparation_tool_never_complete_from_dispatcher_success(tmp_path,sid,inputs):
    async def run():
        app,skills,research,cid=await prepare(tmp_path)
        try:
            plan=await skills.plan(sid,inputs,cid,None)
            async def callback(*args):return {'complete':True,'truncated':False,'errors':[],'data':{'synthetic':'prepared'}}
            result=await execute(skills,plan,callback)
            assert result['status']=='limited' and not result['steps'][0]['result']['complete']
        finally:await app.close()
    asyncio.run(run())


def test_actual_status_and_report_are_same_conversation(tmp_path):
    async def run():
        app,skills,research,cid=await prepare(tmp_path)
        try:
            other=(await create(app))['id'];task=await research.create(cid,'合成问题',urls=['https://example.com/'])
            mid=await saved_synthesis(app,cid)
            for tool,args in [('research_status',{'task_id':task['operation_id']}),('report_build_preview',{'message_id':mid,'format':'docx','title':'合成'})]:
                manifest=custom('cross-'+tool.replace('_','-'),[toolstep('read',tool,args)]);await register(skills,tmp_path,manifest)
                plan=await skills.plan(manifest['id'],{},other,None)
                result=await execute(skills,plan,lambda tool,args:dispatch(app,research,other,tool,args))
                assert result['status']=='failed'
        finally:await app.close()
    asyncio.run(run())


def test_migration_preserves_disabled_and_invalidates_prior_generation(tmp_path):
    async def run():
        app,skills,research,cid=await prepare(tmp_path)
        try:
            await skills.set_enabled('web-research',False)
            async with app.store._lock:await app.store._db().execute("UPDATE skills_registry SET version='1.0.0',revision='old',reason='旧占位' WHERE id='web-research'")
            await skills.open();row=next(x for x in (await skills.list())['skills'] if x['id']=='web-research')
            assert row['version']=='1.1.0' and not row['enabled']
            await skills.set_enabled('web-research',True)
            plan=await skills.plan('web-research',{'query':'合成','urls':'https://example.com/'},cid,None)
            await skills.set_enabled('web-research',False);await skills.set_enabled('web-research',True)
            with pytest.raises(SkillError):await execute(skills,plan,forbidden)
        finally:await app.close()
    asyncio.run(run())


@pytest.mark.parametrize('urls',['','https://127.0.0.1/','https://u:p@example.com/','https://example.com/#fragment','\n'.join('https://example.com/'+str(i) for i in range(11)),'\n'.join('https://host'+str(i)+'.example.com/' for i in range(6))])
def test_research_urls_budget_and_browser_boundary_refuse_before_dispatch(tmp_path,urls):
    async def run():
        app,skills,research,cid=await prepare(tmp_path)
        try:
            with pytest.raises(SkillError):await skills.plan('web-research',{'query':'合成问题','urls':urls},cid,None)
        finally:await app.close()
    asyncio.run(run())


def test_cancel_prepared_skill_calls_no_tool_and_cid_injection_refused(tmp_path):
    async def run():
        app,skills,research,cid=await prepare(tmp_path)
        try:
            inputs={'query':'合成','urls':'https://example.com/'}
            with pytest.raises(SkillError):await skills.plan('web-research',{**inputs,'cid':str(uuid4())},cid,None)
            plan=await skills.plan('web-research',inputs,cid,None)
            result=await skills.cancel(plan['plan_id'],plan['revision'],cid,None)
            assert result['status']=='interrupted' and result['steps']==[]
            with pytest.raises(SkillError):await execute(skills,plan,forbidden)
        finally:await app.close()
    asyncio.run(run())


@pytest.mark.parametrize('state',['planned','collecting','collected','limited','unknown','ready'])
def test_status_without_saved_synthesis_cannot_advance_even_complete_true(tmp_path,state):
    async def run():
        app,skills,research,cid=await prepare(tmp_path)
        try:
            manifest=custom('status-chain',[toolstep('status','research_status',{'task_id':str(uuid4())}),toolstep('later','memory_context',{'query':'不能推进'})]);await register(skills,tmp_path,manifest)
            plan=await skills.plan('status-chain',{},cid,None);calls=[]
            async def callback(tool,args):calls.append(tool);return {'complete':True,'truncated':False,'errors':[],'data':{'state':state,'final':{'state':'not_requested','message_id':None}}}
            result=await execute(skills,plan,callback)
            assert result['status']=='limited' and calls==['research_status']
        finally:await app.close()
    asyncio.run(run())


def test_real_status_saved_synthesis_then_report_reference_binding(tmp_path):
    async def run():
        app,skills,research,cid=await prepare(tmp_path)
        try:
            task=await research.create(cid,'合成问题',urls=['https://example.com/']);mid=await saved_synthesis(app,cid)
            # 合成已保存阶段fixture；模型/网页阶段由ResearchService目标另测，不宣称真实模型。
            ready_stage(task,mid)
            async with app.store._lock:await app.store._db().execute('UPDATE research_tasks SET data_json=? WHERE cid=? AND operation_id=?',(json.dumps(task,ensure_ascii=False),cid,task['operation_id']))
            manifest=custom('saved-report-chain',[toolstep('status','research_status',{'task_id':task['operation_id']}),toolstep('report','report_build_preview',{'message_id':{'from_step':'status','path':['data','final','message_id']},'format':'pdf','title':'合成研究简报'})]);await register(skills,tmp_path,manifest)
            plan=await skills.plan('saved-report-chain',{},cid,None);calls=[]
            async def callback(tool,args):
                calls.append(tool)
                if tool=='research_status':return {'complete':True,'truncated':False,'errors':[],'data':await research.status(cid,args['task_id'])}
                return await dispatch(app,research,cid,tool,args)
            result=await execute(skills,plan,callback)
            assert result['status']=='limited' and calls==['research_status','report_build_preview']
            assert [s['status'] for s in result['steps']]==['completed','limited']
            assert result['steps'][-1]['result']['data']['references'][0]['citation']=='C1'
        finally:await app.close()
    asyncio.run(run())


@pytest.mark.parametrize('gap',[
    'limitations','search_unavailable','page_failed','not_all_read_zero',
    'missing_url','search_failed','missing_query','ready_count_mismatch',
    'missing_coverage','task_error',
])
def test_ready_saved_status_retains_collection_limits_and_stops(tmp_path,gap,monkeypatch):
    async def run():
        app,skills,research,cid=await prepare(tmp_path);block_external(app,research,monkeypatch)
        try:
            task=ready_stage(await research.create(cid,'合成问题',urls=['https://example.com/']),await saved_synthesis(app,cid))
            if gap=='limitations':task['coverage']['limitations']=['合成页面预算已耗尽']
            elif gap=='search_unavailable':
                task['queries']=['合成检索'];task['searches']=[{'query':'合成检索','state':'unavailable','error':None,'results':[]}]
                task['coverage'].update(search_rounds=1,search_unavailable=True)
            elif gap=='page_failed':
                task['pages'][0].update(state='failed',error={'code':'READ_FAILED','message':'合成读取失败'})
                task['coverage'].update(ready_pages=0,distinct_final_pages=0)
            elif gap=='not_all_read_zero':
                task['pages']=[];task['coverage'].update(attempted_pages=0,ready_pages=0,distinct_final_pages=0)
            elif gap=='missing_url':task['urls'].append('https://example.com/unread')
            elif gap=='search_failed':
                task['queries']=['合成检索'];task['searches']=[{'query':'合成检索','state':'failed','error':{'code':'SEARCH_FAILED'},'results':[]}]
                task['coverage']['search_rounds']=1
            elif gap=='missing_query':task['queries']=['未执行的合成检索']
            elif gap=='ready_count_mismatch':task['coverage']['ready_pages']=0
            elif gap=='missing_coverage':del task['coverage']['search_unavailable']
            elif gap=='task_error':task['error']={'code':'RESEARCH_LIMIT','message':'合成限制'}
            async with app.store._lock:
                await app.store._db().execute('UPDATE research_tasks SET data_json=? WHERE cid=? AND operation_id=?',(json.dumps(task,ensure_ascii=False),cid,task['operation_id']))
            manifest=custom('limited-ready-chain',[toolstep('status','research_status',{'task_id':task['operation_id']}),toolstep('later','memory_context',{'query':'不得越过采集缺口'})])
            await register(skills,tmp_path,manifest);plan=await skills.plan('limited-ready-chain',{},cid,None);calls=[]
            async def callback(tool,args):
                calls.append(tool)
                return {'complete':True,'truncated':False,'errors':[],'data':await research.status(cid,args['task_id'])}
            result=await execute(skills,plan,callback)
            assert result['status']=='limited' and calls==['research_status']
            assert result['steps'][0]['result']['status']=='limited'
            assert result['steps'][0]['result']['data']['coverage']==task['coverage']
        finally:await app.close()
    asyncio.run(run())


def test_ready_source_only_zero_pages_is_scoped_not_empty_completion():
    task={'state':'ready','error':None,'final':{'state':'saved','message_id':str(uuid4())},
          'urls':[],'queries':[],'pages':[],'searches':[],
          'sources':[{'kind':'document','evidence_id':'d'*64}],
          'coverage':{'attempted_pages':0,'ready_pages':0,'search_rounds':0,'distinct_final_pages':0,'search_unavailable':False,'limitations':[]}}
    assert _research_ready(task)
    task['sources']=[]
    assert not _research_ready(task),'没有任何已选范围的0==0不能是完成事实'
