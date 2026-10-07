"""V4-011真实SQLite与合成目录/原文；Main只用mock，禁止把局部事实提升为任务完成。"""
import asyncio
import json
from uuid import uuid4

import pytest

from test_chat import setup,create,call
from orvia_backend.chat.routing import Route,Step
from orvia_backend.chat.verification import digest
from orvia_backend.computer.paths import ToolError
from orvia_backend.browser.service import evidence


async def seed(app,cid,steps):
    rid=str(uuid4());await app.chat.repository.claim(cid,rid,'synthetic closure')
    async with app.store._lock:
        await app.store._db().execute("INSERT INTO m20_workflows(conversation_id,request_id,text,plan_json,position,state) VALUES(?,?,?,'[]',0,'running')",(cid,rid,'synthetic closure'))
    plan=Route(steps=steps);await app.chat.natural.progress.install(cid,rid,plan)
    await app.chat.streams.start(cid,rid)
    return rid,plan


async def bound_answer(app,cid,rid,plan,index=0):
    await app.chat.natural.progress.set(cid,rid,index,'running')
    return await app.chat.natural._append_step(cid,rid,index,plan.steps[index],'合成真实已保存的普通回答','natural_answer',{})


def test_real_multistep_scans_and_summary_seal_precise_results_restart_no_replay(tmp_path):
    async def run():
        app=await setup(tmp_path);cid=(await create(app))['id'];root=tmp_path/'synthetic';root.mkdir();(root/'a.txt').write_text('synthetic')
        try:
            await call(app,'chat.grant',{'id':cid,'root':str(root)})
            rid,plan=await seed(app,cid,[Step(kind='list'),Step(kind='space'),Step(kind='task_summary')])
            await app.chat.natural.drive(cid,rid,{'cancelled':False,'model':None,'request_id':rid})
            row=await app.chat.natural.row(cid);states=json.loads(row['step_states'])
            assert row['state']=='completed' and all(s['result_id'] and s['verification'] for s in states)
            assert len({s['result_id'] for s in states})==len(states)
            before=json.dumps(states);await app.close();app=await setup(tmp_path)
            assert json.dumps(json.loads((await app.chat.natural.row(cid))['step_states']))==before
            assert (root/'a.txt').read_text()=='synthetic'
        finally:await app.close()
    asyncio.run(run())


@pytest.mark.parametrize('fault',['none','wrong_kind','other_cid','wrong_step','wrong_request'])
def test_status_completed_without_exact_goal_evidence_rejected(tmp_path,fault):
    async def run():
        app=await setup(tmp_path);cid=(await create(app))['id']
        try:
            rid,plan=await seed(app,cid,[Step(kind='answer',query='合成概念')]);ref=None
            if fault!='none':
                other=(await create(app))['id'] if fault=='other_cid' else cid
                data={'request_id':str(uuid4()) if fault=='wrong_request' else rid,'task_step_index':1 if fault=='wrong_step' else 0,'task_step_revision':digest(plan.steps[0].model_dump())}
                message=app.chat.repository._message('assistant','自述任务已完成','result' if fault=='wrong_kind' else 'natural_answer',data)
                async with app.store._lock:await app.store._db().execute('INSERT INTO chat_messages(conversation_id,message_json) VALUES(?,?)',(other,json.dumps(message)))
                ref=message['id']
            with pytest.raises(ToolError,match='STEP_NOT_VERIFIED'):await app.chat.natural.progress.set(cid,rid,0,'completed',result_id=ref)
            assert json.loads((await app.chat.natural.row(cid,rid))['step_states'])[0]['status']=='not_started'
        finally:await app.close()
    asyncio.run(run())


@pytest.mark.parametrize('fault',['missing_seal','changed_message','changed_step'])
def test_terminal_reloads_sealed_original_facts_and_rejects_stale_status(tmp_path,fault):
    async def run():
        app=await setup(tmp_path);cid=(await create(app))['id']
        try:
            rid,plan=await seed(app,cid,[Step(kind='answer',query='合成')]);ref=await bound_answer(app,cid,rid,plan)
            await app.chat.natural.progress.set(cid,rid,0,'completed',result_id=ref);await app.chat.natural._update(cid,rid,position=1)
            old=await app.chat.natural.row(cid,rid)
            async with app.store._lock:
                db=app.store._db()
                if fault=='missing_seal':
                    states=json.loads(old['step_states']);states[0].pop('verification');await db.execute('UPDATE m20_workflows SET step_states=? WHERE request_id=?',(json.dumps(states),rid))
                elif fault=='changed_message':await db.execute("UPDATE chat_messages SET message_json=json_set(message_json,'$.text','伪改原文') WHERE json_extract(message_json,'$.id')=?",(ref,))
                else:
                    plan.steps[0].query='另一个目标';await db.execute('UPDATE m20_workflows SET plan_json=? WHERE request_id=?',(plan.model_dump_json(),rid))
            with pytest.raises(ToolError,match='STEP_NOT_VERIFIED'):await app.chat.natural.progress.terminal(old,'completed')
            with pytest.raises(ToolError,match='STEP_NOT_VERIFIED'):await app.chat.natural._terminal(cid,rid,'completed')
            assert (await app.chat.natural.row(cid,rid))['state']=='running'
        finally:await app.close()
    asyncio.run(run())


@pytest.mark.parametrize('terminal',['cancelled','failed','completed'])
def test_late_result_repeat_notify_and_old_update_never_overwrite_terminal(tmp_path,terminal):
    async def run():
        app=await setup(tmp_path);cid=(await create(app))['id']
        try:
            rid,plan=await seed(app,cid,[Step(kind='answer')]);ref=await bound_answer(app,cid,rid,plan)
            if terminal=='completed':await app.chat.natural.progress.set(cid,rid,0,'completed',result_id=ref);await app.chat.natural._update(cid,rid,position=1)
            await app.chat.natural._terminal(cid,rid,terminal)
            before=await app.chat.natural.row(cid,rid);seq=await app.chat.repository.sequence(cid)
            assert await app.chat.natural.progress.set(cid,rid,0,'completed',result_id=ref) is False
            await app.chat.natural._update(cid,rid,state='running',position=0)
            await app.chat.natural.pause(cid,rid,'directory','迟到等待')
            await app.chat.natural._terminal(cid,rid,'completed')
            await app.chat.natural._terminal(cid,rid,'cancelled')
            assert await app.chat.natural.row(cid,rid)==before and await app.chat.repository.sequence(cid)==seq
            assert await app.chat.repository.latest_request_status(cid)==terminal
            async with app.store._lock:
                async with app.store._db().execute('SELECT state FROM m20_streams WHERE conversation_id=? AND request_id=?',(cid,rid)) as cursor:assert (await cursor.fetchone())[0]==terminal
        finally:await app.close()
    asyncio.run(run())


def test_explicit_acceptance_consumes_exact_token_step_and_not_a_success_result(tmp_path):
    async def run():
        app=await setup(tmp_path);cid=(await create(app))['id']
        try:
            rid,plan=await seed(app,cid,[Step(kind='unsupported',query='未实现的合成目标')])
            await app.chat.natural.progress.set(cid,rid,0,'unsupported','未执行');await app.chat.natural.pause(cid,rid,'task_decision','接受或取消')
            row=await app.chat.natural.row(cid,rid);token=row['continuation_id']
            with pytest.raises(ToolError):await app.chat.natural.progress.set(cid,rid,0,'accepted')
            with pytest.raises(ToolError,match='STALE_CONTINUATION'):await app.chat.natural.progress.accept(cid,rid,0,str(uuid4()))
            await app.chat.natural.progress.accept(cid,rid,0,token)
            current=await app.chat.natural.row(cid,rid);states=json.loads(current['step_states']);assert current['continuation_id'] is None and current['position']==1
            receipt=await app.chat.repository.message(cid,states[0]['result_id']);assert receipt['kind']=='task_acceptance' and receipt['data']['continuation_id']==token
            with pytest.raises(ToolError,match='STALE_CONTINUATION'):await app.chat.natural.progress.accept(cid,rid,0,token)
            await app.chat.natural._terminal(cid,rid,'completed')
            assert (await app.chat.natural.row(cid,rid))['state']=='completed' and states[0]['status']=='accepted'
        finally:await app.close()
    asyncio.run(run())


@pytest.mark.parametrize('mutation',['version','removed'])
def test_source_full_version_or_withdrawal_invalidates_prior_step_before_whole_completion(tmp_path,mutation):
    async def run():
        app=await setup(tmp_path);cid=(await create(app))['id']
        try:
            value=await app.chat.evidence.save(cid,evidence('https://example.org/a',mode='http',content='合成原文资料。'))
            await app.chat.natural.material_added(cid,'browser',value['evidence_id'])
            rid,plan=await seed(app,cid,[Step(kind='material_quote',query='合成')]);await app.chat.natural.progress.set(cid,rid,0,'running')
            ref=await app.chat.natural._append_step(cid,rid,0,plan.steps[0],'原文引用','source',{'operation':'ask','error':None,'items':[{'evidence_id':value['evidence_id'],'content':'合成原文资料。'}]})
            await app.chat.natural.progress.set(cid,rid,0,'completed',result_id=ref);await app.chat.natural._update(cid,rid,position=1)
            async with app.store._lock:
                if mutation=='version':await app.store._db().execute("UPDATE browser_evidence SET evidence_json=json_set(evidence_json,'$.content','改变的尾部完整原文') WHERE id=?",(value['evidence_id'],))
                else:await app.store._db().execute('INSERT INTO m20_removed_sources VALUES(?,?,?)',(cid,'browser',value['evidence_id']))
            with pytest.raises(ToolError,match='STEP_NOT_VERIFIED'):await app.chat.natural._terminal(cid,rid,'completed')
        finally:await app.close()
    asyncio.run(run())


@pytest.mark.parametrize('kind',['script','development'])
def test_exit_zero_or_generated_draft_only_limited_and_explicit_accept_closes(tmp_path,kind):
    async def run():
        app=await setup(tmp_path);cid=(await create(app))['id']
        try:
            rid,plan=await seed(app,cid,[Step(kind=kind,query='合成业务目标')]);await app.chat.natural.progress.set(cid,rid,0,'running')
            await app.chat.natural.pause(cid,rid,kind,'真实批准等待',input={'requirement':'合成业务目标'},approval=True)
            wf=await app.chat.natural.workflow(cid)
            if kind=='script':
                oid=await app.chat.automation.repository.create(cid,'script','1'*64,{'evidence':{'exit_code':0,'token_verified':True,'processes_reaped':True}})
                await app.chat.automation.repository.transition(cid,oid,['awaiting_approval'],'completed',{'exit_code':0,'token_verified':True,'processes_reaped':True})
                await app.chat.repository.append(cid,'system','隔离运行退出0','automation',{'operation_id':oid})
            else:await app.chat.repository.append(cid,'assistant','生成了待审批草稿','development',{'draft_id':str(uuid4()),'revision':'2'*64})
            request={'id':cid,'request_id':rid,'continuation_id':wf['continuation_id']}
            result=await call(app,'chat.continue',request);assert result['ok']
            current=await app.chat.natural.row(cid,rid);assert current['state']=='waiting_input' and json.loads(current['step_states'])[0]['status']=='limited'
            assert (await call(app,'chat.continue',request))['error']['code']=='STALE_CONTINUATION'
            done=await call(app,'chat.continue',{'id':cid,'request_id':rid,'continuation_id':current['continuation_id'],'answer':'accept_limit'})
            assert done['ok'] and (await app.chat.natural.row(cid,rid))['state']=='completed'
        finally:await app.close()
    asyncio.run(run())


@pytest.mark.parametrize('mutation',['plan','workflow','source_body'])
def test_native_continuation_exact_review_bound_not_swappable(tmp_path,mutation):
    async def run():
        app=await setup(tmp_path);cid=(await create(app))['id']
        try:
            rid,plan=await seed(app,cid,[Step(kind='answer',query='合成目标')]);await app.chat.natural.progress.set(cid,rid,0,'running')
            await app.chat.natural.pause(cid,rid,'synthesis','精确待批准',input={'mode':'answer','question':'合成问题','sources':[]},approval=True)
            row=await app.chat.natural.row(cid,rid);context=json.loads(row['workflow_json'])
            if mutation=='plan':
                plan.steps[0].query='调换目标';await app.chat.natural._update(cid,rid,plan_json=plan.model_dump_json())
            elif mutation=='workflow':
                changed={**context,'question':'被调换的批准说明'};await app.chat.natural._update(cid,rid,workflow_json=json.dumps(changed))
            else:context['input']['question']='未经批准的新发送正文'
            with pytest.raises(ToolError,match='STEP_NOT_VERIFIED'):
                await app.chat.natural.progress.complete_continuation(cid,rid,0,row['continuation_id'],str(uuid4()),context)
            assert (await app.chat.natural.row(cid,rid))['position']==0
        finally:await app.close()
    asyncio.run(run())


def test_zero_entry_complete_scan_valid_but_partial_scan_never_sealed(tmp_path,monkeypatch):
    async def run():
        import orvia_backend.chat.scans as scans
        app=await setup(tmp_path);cid=(await create(app))['id'];root=tmp_path/'empty';root.mkdir()
        try:
            await call(app,'chat.grant',{'id':cid,'root':str(root)})
            full=await call(app,'chat.natural',{'id':cid,'request_id':str(uuid4()),'text':'列出目录'})
            assert full['result']['status']=='completed'
            (root/'a.txt').write_text('a');(root/'b.txt').write_text('b');monkeypatch.setattr(scans,'MAX_VISITED',1)
            partial=await call(app,'chat.natural',{'id':cid,'request_id':str(uuid4()),'text':'列出目录'})
            wf=partial['result']['workflow'];row=await app.chat.natural.row(cid,wf['request_id'])
            assert wf['action']=='task_decision' and json.loads(row['step_states'])[0]['status']=='limited'
            message=next(item for item in reversed(partial['result']['messages']) if item['kind']=='directory_result')
            with pytest.raises(ToolError,match='STEP_NOT_VERIFIED'):await app.chat.natural.progress.set(cid,wf['request_id'],0,'completed',result_id=message['id'])
        finally:await app.close()
    asyncio.run(run())


def test_truncated_web_read_limited_and_direct_sealing_cannot_bypass(tmp_path):
    async def run():
        app=await setup(tmp_path);cid=(await create(app))['id'];url='https://example.org/partial'
        async def read(*args,**kwargs):return evidence(url,mode='http',content='合成部分正文。',truncated=True)
        app.chat.browser.read=read
        try:
            partial=await call(app,'chat.natural',{'id':cid,'request_id':str(uuid4()),'text':'读取 '+url})
            wf=partial['result']['workflow'];assert wf['action']=='task_decision'
            message=next(item for item in reversed(partial['result']['messages']) if item['kind']=='source')
            with pytest.raises(ToolError,match='STEP_NOT_VERIFIED'):await app.chat.natural.progress.set(cid,wf['request_id'],0,'completed',result_id=message['id'])
            accepted=await call(app,'chat.continue',{'id':cid,'request_id':wf['request_id'],'continuation_id':wf['continuation_id'],'answer':'accept_limit'})
            assert accepted['result']['status']=='completed' and accepted['result']['task_progress']['steps'][0]['status']=='accepted'
        finally:await app.close()
    asyncio.run(run())


def test_goal_summary_cannot_complete_remaining_action_and_duplicate_result_not_reused(tmp_path):
    async def run():
        app=await setup(tmp_path);cid=(await create(app))['id']
        try:
            rid,plan=await seed(app,cid,[Step(kind='answer'),Step(kind='files')]);ref=await bound_answer(app,cid,rid,plan)
            await app.chat.natural.progress.set(cid,rid,0,'completed',result_id=ref);await app.chat.natural._update(cid,rid,position=1)
            with pytest.raises(ToolError,match='STEP_NOT_VERIFIED'):await app.chat.natural.progress.set(cid,rid,1,'completed',result_id=ref)
            with pytest.raises(ToolError,match='TASK_NOT_COMPLETE'):await app.chat.natural._terminal(cid,rid,'completed')
            before=await app.chat.natural.row(cid,rid)
            await app.chat.natural.progress.install(cid,rid,Route(steps=[Step(kind='answer')]))
            assert await app.chat.natural.row(cid,rid)==before
        finally:await app.close()
    asyncio.run(run())


def test_real_file_change_requires_exact_operation_and_each_verified_entry(tmp_path):
    async def run():
        from test_chat import FakeModel
        app=await setup(tmp_path);cid=(await create(app))['id'];root=tmp_path/'files';root.mkdir();(root/'a.txt').write_text('synthetic')
        try:
            await call(app,'chat.grant',{'id':cid,'root':str(root)})
            rid,plan=await seed(app,cid,[Step(kind='files',query='将a.txt改名b.txt')])
            app.chat.client=FakeModel([{'kind':'inspect','tool':'list_directory','arguments':{}},{'kind':'plan','actions':[{'kind':'rename','source':'a.txt','destination':'b.txt'}]}])
            app.chat._active[cid]={'request_id':rid,'cancelled':False,'model':None}
            await app.chat.natural.drive(cid,rid,app.chat._active[cid]);wf=await app.chat.natural.workflow(cid)
            assert wf['action']=='files' and (root/'a.txt').exists()
            with pytest.raises(ToolError):await app.chat.natural.progress.set(cid,rid,0,'completed',result_id=str(uuid4()))
            approved=await call(app,'chat.approve',{'id':cid,'operation_id':wf['input']['operation_id'],'revision':wf['input']['revision']});assert approved['ok']
            result=await call(app,'chat.continue',{'id':cid,'request_id':rid,'continuation_id':wf['continuation_id']})
            assert result['ok'] and result['result']['status']=='completed' and (root/'b.txt').read_text()=='synthetic' and not (root/'a.txt').exists()
            item=json.loads((await app.chat.natural.row(cid,rid))['step_states'])[0];assert 'operation' in item['verification']['facts']
        finally:app.chat._active.clear();await app.close()
    asyncio.run(run())


@pytest.mark.parametrize('subset',[True,False])
def test_real_cleanup_subset_not_full_goal_and_all_entries_evidenced(tmp_path,subset):
    async def run():
        import os,time
        app=await setup(tmp_path);cid=(await create(app))['id'];base=tmp_path/'local';temp=base/'Temp';temp.mkdir(parents=True)
        for name in ['a.tmp','b.log']:
            path=temp/name;path.write_text('synthetic');os.utime(path,(time.time()-32*86400,)*2)
        app.chat.cleanup.local_base=base
        try:
            rid,plan=await seed(app,cid,[Step(kind='cleanup',query='合成Temp隔离')]);await app.chat.natural.drive(cid,rid,{'request_id':rid,'cancelled':False,'model':None})
            wf=await app.chat.natural.workflow(cid);assert wf['action']=='cleanup'
            moved=await call(app,'chat.cleanup.execute',{'id':cid,**wf['input'],'indices':[0] if subset else [0,1]});assert moved['ok']
            result=await call(app,'chat.continue',{'id':cid,'request_id':rid,'continuation_id':wf['continuation_id']});assert result['ok']
            current=await app.chat.natural.row(cid,rid)
            if subset:
                assert current['state']=='waiting_input' and json.loads(current['step_states'])[0]['status']=='limited' and len(list(temp.iterdir()))==1
                accepted=await call(app,'chat.continue',{'id':cid,'request_id':rid,'continuation_id':current['continuation_id'],'answer':'accept_limit'})
                assert accepted['result']['task_progress']['steps'][0]['status']=='accepted'
            else:assert current['state']=='completed' and not list(temp.iterdir())
        finally:await app.close()
    asyncio.run(run())


def test_real_publication_saved_bytes_exact_preview_and_source_versions_close_goal(tmp_path):
    async def run():
        from orvia_backend.chat.synthesis import prepare as synthesis_prepare
        app=await setup(tmp_path);cid=(await create(app))['id']
        try:
            value=await app.chat.evidence.save(cid,evidence('https://example.org/a',mode='http',content='合成原文。'))
            await app.chat.natural.material_added(cid,'browser',value['evidence_id'])
            packet=await synthesis_prepare(app.chat,cid,'summary','合成',[{'kind':'browser','evidence_id':value['evidence_id']}])
            data={'answer':'合成回答。','claims':[{'text':'合成原文。','kind':'fact','citations':[packet['fragments'][0]['citation']]}],'citations':[{k:v for k,v in packet['fragments'][0].items() if k!='text'}],'coverage':packet['coverage'],'revision':packet['revision']}
            await app.chat.repository.append(cid,'assistant','保存回答','synthesis',data)
            rid,plan=await seed(app,cid,[Step(kind='publication',format='docx',query='合成简报')]);await app.chat.natural.drive(cid,rid,{'request_id':rid,'cancelled':False,'model':None})
            wf=await app.chat.natural.workflow(cid);args={'id':cid,**wf['input']}
            preview=(await call(app,'chat.publication.preview',args))['result'];path=tmp_path/'synthetic.docx'
            saved=await call(app,'chat.publication.save',{**args,'request_id':str(uuid4()),'revision':preview['revision'],'path':str(path)})
            assert saved['ok'] and path.read_bytes().startswith(b'PK')
            result=await call(app,'chat.continue',{'id':cid,'request_id':rid,'continuation_id':wf['continuation_id']})
            assert result['ok'] and result['result']['status']=='completed'
        finally:await app.close()
    asyncio.run(run())


@pytest.mark.parametrize('kind',['context','retry'])
def test_local_read_errors_close_failed_without_model_fallback_or_late_completion(tmp_path,kind):
    async def run():
        from orvia_backend.context import ContextError
        from orvia_backend.retry import RetryError
        app=await setup(tmp_path);cid=(await create(app))['id']
        async def failing(*args,**kwargs):raise (ContextError('SEARCH_TIMEOUT','本机只读检索3秒预算已耗尽') if kind=='context' else RetryError('READ_RETRY_EXHAUSTED','只读尝试额度已耗尽'))
        app.chat.documents.search=failing
        try:
            result=await call(app,'chat.natural',{'id':cid,'request_id':str(uuid4()),'text':'检索原文引用'})
            assert result['ok'];row=await app.chat.natural.row(cid)
            assert row['state']=='failed' and json.loads(row['step_states'])[0]['status']=='failed'
            assert result['result']['workflow'] is None and result['result']['messages'][-1]['data']['code']==('SEARCH_TIMEOUT' if kind=='context' else 'READ_RETRY_EXHAUSTED')
        finally:await app.close()
    asyncio.run(run())


def test_cancel_immediately_after_review_commit_never_overwrites_request_status(tmp_path):
    async def run():
        app=await setup(tmp_path);cid=(await create(app))['id']
        try:
            rid,plan=await seed(app,cid,[Step(kind='files')]);original=app.chat.natural.progress.bind_review
            async def after_commit(*args,**kwargs):
                result=await original(*args,**kwargs)
                await app.chat.natural._terminal(cid,rid,'cancelled')
                return result
            app.chat.natural.progress.bind_review=after_commit
            await app.chat.natural.pause(cid,rid,'files','准确待批准',input={'operation_id':str(uuid4()),'revision':'a'*64},approval=True)
            row=await app.chat.natural.row(cid,rid)
            assert row['state']=='cancelled' and row['continuation_id'] is None
            assert await app.chat.repository.latest_request_status(cid)=='cancelled'
            assert (await app.chat.streams.get(cid,rid))['state']=='cancelled'
            assert not any(message['kind']=='workflow' for message in await app.chat.repository.since(cid,0))
        finally:await app.close()
    asyncio.run(run())
