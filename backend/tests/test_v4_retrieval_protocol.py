"""真实应用/SQLite/FTS与合成向量；权限、解除关联、发送引用和重启验证。"""
import asyncio
from uuid import uuid4

from test_chat import setup,create,call
from test_m15_synthesis import seed
from test_v4_retrieval import SyntheticEmbedder


def test_protocol_scope_remove_cascade_and_restart(tmp_path):
    async def run():
        app=await setup(tmp_path)
        try:
            cid=(await create(app))['id'];other=(await create(app))['id']
            selected=await seed(app,cid)
            assert (await call(app,'retrieval.status'))['result']['reason']=='MODEL_MISSING'
            fallback=(await call(app,'retrieval.search',{'id':cid,'query':'合成'}))['result']
            assert fallback['status']=='keyword_only' and fallback['reason']=='MODEL_MISSING'
            assert fallback['evidence']
            app.retrieval.embedder=SyntheticEmbedder()
            built=(await call(app,'retrieval.rebuild',{'id':cid}))['result']
            assert built['status']=='completed'
            found=(await call(app,'retrieval.search',{'id':cid,'query':'合成'}))['result']
            assert found['status']=='hybrid' and found['coverage']['indexed_chunks']>0
            assert not (await call(app,'retrieval.search',{'id':other,'query':'合成'}))['result']['evidence']
            assert not (await call(app,'retrieval.search',{'id':cid,'query':'合成','sources':['private']}))['ok']
            removed=selected[0]
            assert (await call(app,'chat.material.remove',{'id':cid,**removed}))['ok']
            after=(await call(app,'retrieval.search',{'id':cid,'query':'合成'}))['result']
            assert all(removed['evidence_id'] not in hit['source'] for hit in after['evidence'])
            rejected=await call(app,'chat.synthesis.preview',{'id':cid,'mode':'answer','question':'合成','sources':[removed]})
            assert not rejected['ok'] and rejected['error']['code']=='SOURCE_UNAVAILABLE'
            preview=await call(app,'chat.synthesis.preview',{'id':cid,'mode':'answer','question':'合成','sources':selected[1:]})
            assert preview['ok'] and preview['result']['fragments']
            assert (await call(app,'context.clear',{'mission_id':cid}))['ok']
            assert (await app.retrieval.status(cid))['indexed_chunks']==0
        finally:await app.close()
        app=await setup(tmp_path)
        try:
            assert (await call(app,'retrieval.status'))['result']['reason']=='MODEL_MISSING'
            assert (await app.retrieval.status(cid))['indexed_chunks']==0
            assert not (await call(app,'retrieval.prepare',{'path':'relative','approved':True}))['ok']
        finally:await app.close()
    asyncio.run(run())


def test_fifty_unit_document_keeps_keyword_answer_and_empty_scope(tmp_path):
    async def run():
        app=await setup(tmp_path)
        try:
            cid=(await create(app))['id']
            empty=(await call(app,'retrieval.search',{'id':cid,'query':'合成'}))['result']
            assert empty['evidence']==[] and empty['reason']=='SCOPE_EMPTY'
            value=await app.chat.documents.save(cid,'fifty-synthetic.docx',b'synthetic-fifty',
                {'format':'docx','units':[{'number':i,'locator':f'段落{i}','text':f'合成许可第{i}项，应保留来源。','method':'text','confidence':None,'error':None} for i in range(1,51)],
                 'total_units':50,'truncated':False,'missing_units':[],'error':None})
            await app.chat.natural.material_added(cid,'document',value['evidence_id'])
            query=(await call(app,'retrieval.search',{'id':cid,'query':'许可'}))['result']
            assert query['status']=='keyword_only' and query['coverage']['scope_sources']==50
            preview=await call(app,'chat.synthesis.preview',{'id':cid,'mode':'answer','question':'许可','sources':[{'kind':'document','evidence_id':value['evidence_id']}]})
            assert preview['ok'] and preview['result']['fragments']
            assert (await call(app,'chat.material.remove',{'id':cid,'kind':'document','evidence_id':value['evidence_id']}))['ok']
            final=(await call(app,'retrieval.search',{'id':cid,'query':'许可'}))['result']
            assert final['evidence']==[] and final['reason']=='SCOPE_EMPTY'
        finally:await app.close()
    asyncio.run(run())


def test_chat_delete_removes_vectors_and_epoch_leaves_only_tombstone(tmp_path):
    async def run():
        app=await setup(tmp_path)
        try:
            cid=(await create(app))['id'];await seed(app,cid)
            app.retrieval.embedder=SyntheticEmbedder()
            assert (await call(app,'retrieval.rebuild',{'id':cid}))['result']['status']=='completed'
            await app.retrieval.clear(cid)
            assert (await call(app,'retrieval.rebuild',{'id':cid}))['result']['status']=='completed'
            async with app.store._lock:
                async with app.store._db().execute('SELECT generation FROM retrieval_epochs WHERE mission_id=?',[cid]) as cursor:
                    assert (await cursor.fetchone())[0]>0
            assert (await call(app,'chat.delete',{'id':cid}))['result']['deleted']
            async with app.store._lock:
                for table in ('retrieval_vectors','retrieval_epochs','context_documents'):
                    async with app.store._db().execute(f'SELECT count(*) FROM {table} WHERE mission_id=?',[cid]) as cursor:
                        assert (await cursor.fetchone())[0]==0
                async with app.store._db().execute('SELECT id,state FROM chat_deletions WHERE id=?',[cid]) as cursor:
                    assert tuple(await cursor.fetchone())==(cid,'completed')
            assert not (await call(app,'retrieval.search',{'id':cid,'query':'合成'}))['ok']
        finally:await app.close()
    asyncio.run(run())
