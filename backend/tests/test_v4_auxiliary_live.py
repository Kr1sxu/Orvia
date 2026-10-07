"""显式 opt-in 的真实 Redis 验收；仅合成会话，无真实模型或用户资料。"""
import asyncio
import json
import os
import subprocess
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from test_chat import setup, create, call

pytestmark = pytest.mark.skipif(not os.getenv('ORVIA_REDIS_TEST_PORT'), reason='需显式提供独立 Redis 测试端口')


def config():
    return dict(enabled=True, host='127.0.0.1', port=int(os.environ['ORVIA_REDIS_TEST_PORT']), db=0)


async def seed(app):
    cid=(await create(app))['id']
    rid=str(uuid4())
    await app.chat.repository.claim(cid,rid,'仅合成任务正文，不应进入 Redis')
    async with app.store._lock:
        row=await (await app.store._db().execute('SELECT * FROM auxiliary_tasks WHERE conversation_id=? AND request_id=?',(cid,rid))).fetchone()
    return cid,rid,dict(row)


def test_live_cache_queue_facts_and_deletion(tmp_path):
    async def scenario():
        app=await setup(tmp_path)
        redis=Redis(host='127.0.0.1',port=config()['port'],decode_responses=True)
        try:
            assert (await call(app,'auxiliary.status'))['result']['state']=='disabled'
            reply=await call(app,'auxiliary.configure',config())
            assert reply['ok'] and reply['result']['state']=='connected'
            cid,rid,row=await seed(app)
            aux=app.auxiliary
            await aux.tick_once()
            state=await aux.status()
            assert state['cache_hits']>=1 and state['notifications_processed']>=1
            key=aux._cache_key(row['task_id'])
            assert 0<await redis.ttl(key)<=30
            value=await redis.get(key)
            assert set(json.loads(value))=={'task_id','version','status'}
            assert '正文' not in value and cid not in value and rid not in value
            # 人为写入“完成”缓存和旧版本通知，业务事实必须仍为pending。
            await redis.set(key,json.dumps(dict(task_id=row['task_id'],version=row['revision'],status='completed')),ex=30)
            message=json.dumps(dict(task_id=row['task_id'],version=row['revision']))
            await redis.rpush(aux._queue_key,message,message,'bad',json.dumps(dict(task_id=str(uuid4()),version=1)))
            await aux.tick_once()
            assert (await aux.status())['cache_misses']>=2
            async with app.store._lock:
                assert (await (await app.store._db().execute('SELECT status FROM chat_requests WHERE conversation_id=? AND request_id=?',(cid,rid))).fetchone())[0]=='pending'
            await app.chat.repository.finish(cid,rid,'completed')
            await aux.tick_once()
            await redis.rpush(aux._queue_key,message)
            await aux.tick_once()
            assert (await aux.status())['notifications_discarded']>=3
            # 已终结合成会话经真实删除路径清除派生元数据，晚到通知不复活。
            assert (await call(app,'chat.delete',{'id':cid}))['ok']
            await redis.rpush(aux._queue_key,message)
            await aux.tick_once()
            assert (await aux.status())['metadata_count']==0
            assert (await call(app,'chat.get',{'id':cid}))['ok'] is False
            await aux.configure({**config(),'enabled':False})
            assert (await aux.probe())['state']=='disabled'
        finally:
            await app.close();await redis.aclose()
    asyncio.run(scenario())


def test_live_disconnect_recovery_and_authentication(tmp_path):
    container=os.environ.get('ORVIA_REDIS_TEST_CONTAINER')
    if container!='orvia-v4-001-test':pytest.skip('断服务仅允许专用测试容器')
    async def scenario():
        app=await setup(tmp_path)
        secret='synthetic-v4-redis-only'
        plain=Redis(host='127.0.0.1',port=config()['port'],decode_responses=True)
        authenticated=Redis(host='127.0.0.1',port=config()['port'],password=secret,decode_responses=True)
        try:
            assert (await app.auxiliary.configure(config()))['state']=='connected'
            cid,rid,row=await seed(app)
            await app.auxiliary.tick_once()
            await asyncio.to_thread(subprocess.run,['docker','stop',container],check=True,capture_output=True)
            await app.auxiliary.tick_once()
            assert (await app.auxiliary.status())['state']=='degraded'
            await app.chat.repository.finish(cid,rid,'completed')
            await app.auxiliary.tick_once()
            assert (await call(app,'health'))['ok']
            await asyncio.to_thread(subprocess.run,['docker','start',container],check=True,capture_output=True)
            await asyncio.sleep(.5)
            assert (await app.auxiliary.probe())['state']=='connected'
            await app.auxiliary.tick_once()
            assert json.loads(await plain.get(app.auxiliary._cache_key(row['task_id'])))['status']=='completed'
            await plain.config_set('requirepass',secret)
            assert (await app.auxiliary.probe())['reason']=='authentication_required'
            reply=await call(app,'credentials.replace',{'credentials':{'redis':secret}})
            assert reply['ok']
            assert (await call(app,'auxiliary.configure',config()))['result']['state']=='connected'
            public=await call(app,'auxiliary.status')
            assert secret not in json.dumps(public)
            async with app.store._lock:
                row=await (await app.store._db().execute('SELECT config_json FROM auxiliary_config')).fetchone()
                assert secret not in row[0]
            await call(app,'credentials.replace',{'credentials':{}})
            assert (await app.auxiliary.status())['state']=='degraded'
        finally:
            await authenticated.config_set('requirepass','')
            await app.close();await plain.aclose();await authenticated.aclose()
    asyncio.run(scenario())


def test_live_ttl_expires_without_reconstruction(tmp_path):
    async def scenario():
        app=await setup(tmp_path)
        redis=Redis(host='127.0.0.1',port=config()['port'],decode_responses=True)
        try:
            await app.auxiliary.configure(config())
            _,_,row=await seed(app)
            await app.auxiliary.tick_once()
            key=app.auxiliary._cache_key(row['task_id'])
            assert 0<await redis.ttl(key)<=30
            # 停止应用轮询且不续期，实际等待完整30秒TTL，不能把mock时钟当服务验收。
            await app.close()
            await asyncio.sleep(31)
            assert await redis.get(key) is None
        finally:
            await app.close();await redis.aclose()
    asyncio.run(scenario())
