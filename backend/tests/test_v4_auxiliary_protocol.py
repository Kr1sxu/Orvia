"""V4-001 私有协议与初始化失败清理；无真实 Redis 或模型调用。"""
import asyncio
import json
import sqlite3

from test_chat import setup, call
from orvia_backend.application import Application
from orvia_backend.auxiliary import AuxiliaryService


def test_protocol_rejects_endpoint_command_and_secret_echo(tmp_path):
    async def scenario():
        app=await setup(tmp_path)
        try:
            assert (await call(app,'auxiliary.status'))['result']['state']=='disabled'
            for patch in ({'host':'example.com'},{'port':True},{'db':16},{'password':'synthetic-private'},{'command':'FLUSHALL'}):
                reply=await call(app,'auxiliary.configure',dict(enabled=True,host='127.0.0.1',port=6379,db=0)|patch)
                assert not reply['ok'] and 'synthetic-private' not in json.dumps(reply)
            assert (await call(app,'auxiliary.probe',{'enabled':True}))['error']['code']=='INVALID_PARAMS'
            assert (await call(app,'credentials.replace',{'credentials':{'redis':'synthetic-redis'}}))['ok']
            public=await call(app,'auxiliary.status')
            assert public['result']['password_configured'] and 'synthetic-redis' not in json.dumps(public)
            assert (await call(app,'configuration.status'))['result']['profiles'][0]['model']=='deepseek-flash'
        finally:await app.close()
    asyncio.run(scenario())


def test_partial_auxiliary_initialization_releases_and_can_retry(tmp_path,monkeypatch):
    async def scenario():
        app=Application()
        await call(app,'hello')
        original=AuxiliaryService.open
        captured=[]
        async def failure(self):
            captured.append(self)
            await original(self)
            raise sqlite3.OperationalError('synthetic-storage-failure')
        try:
            with monkeypatch.context() as patch:
                patch.setattr(AuxiliaryService,'open',failure)
                result=await call(app,'initialize',{'data_directory':str(tmp_path),'credentials':{}})
                assert not result['ok'] and result['error']['code']=='STORAGE_UNAVAILABLE'
                assert app.store is None and captured[0]._task is None
            assert (await call(app,'initialize',{'data_directory':str(tmp_path),'credentials':{}}))['ok']
            assert (await call(app,'auxiliary.status'))['result']['state']=='disabled'
        finally:await app.close()
    asyncio.run(scenario())
