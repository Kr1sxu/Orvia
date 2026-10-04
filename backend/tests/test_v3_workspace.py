"""V3-001：真实SQLite与会话服务；合成目录，禁止模型/执行作为显示的副作用。"""
import asyncio
from uuid import uuid4

import pytest

from test_chat import call, create, setup
from orvia_backend.chat.routing import local_small_talk


@pytest.mark.parametrize('text', ['你好', '谢谢！', '好的', '继续'])
def test_small_talk_has_no_capability_or_model_calls(tmp_path, text):
    async def run():
        app = await setup(tmp_path)
        async def forbidden(*args, **kwargs):
            raise AssertionError('普通寒暄不得调用模型或能力')
        app.chat.client.complete = app.chat.client.stream = forbidden
        app.chat.automation.handle = forbidden
        try:
            cid = (await create(app))['id']
            response = await call(app, 'chat.natural', {'id': cid, 'request_id': str(uuid4()), 'text': text})
            assert response['ok'], response
            state = response['result']
            assert state['workflow'] is None and state['operation'] is None and state['grant'] is None
            assert state['workspace_history'] == {'development': None, 'cleanup': None, 'automation': []}
            assert state['messages'][-1]['data']['origin'] == 'local'
            assert not any(m['kind'] in {'automation','development','cleanup','workflow'} for m in state['messages'])
        finally:
            await app.close()
    asyncio.run(run())


def test_small_talk_does_not_swallow_tasks_or_approve_waiting_work(tmp_path):
    for text in ['你好，请生成 React 页面', '好的，运行脚本', '继续填写表单', '谢谢，清理 Temp']:
        assert local_small_talk(text) is None
    async def run():
        app = await setup(tmp_path)
        try:
            cid = (await create(app))['id']
            first = await call(app, 'chat.natural', {'id': cid, 'request_id': str(uuid4()), 'text': '聚焦桌面应用'})
            workflow = first['result']['workflow']
            assert workflow['action'] == 'desktop'
            denied = await call(app, 'chat.natural', {'id': cid, 'request_id': str(uuid4()), 'text': '好的'})
            assert denied['error']['code'] == 'REQUEST_PENDING'
            assert (await call(app, 'chat.get', {'id':cid}))['result']['workflow'] == workflow
        finally:
            await app.close()
    asyncio.run(run())


def test_history_survives_message_clipping_restart_and_all_operation_states(tmp_path):
    async def run():
        app = await setup(tmp_path)
        try:
            cid, other = (await create(app))['id'], (await create(app))['id']
            root = tmp_path / 'synthetic-project'
            root.mkdir()
            await call(app, 'chat.grant', {'id':cid, 'root':str(root)})
            draft = await app.chat.development.create(cid, 'code', {'files':[{'path':'App.tsx','content':'export const App = () => null;'}]})
            local = tmp_path / 'Local'
            (local / 'Temp').mkdir(parents=True)
            app.chat.cleanup.local_base = local
            plan = (await call(app, 'chat.cleanup.scan', {'id':cid}))['result']
            for index, status in enumerate(['awaiting_approval','running','failed','completed','interrupted','uncertain']):
                kind = ['script','desktop','browser'][index % 3]
                oid = await app.chat.automation.repository.create(cid, kind, 'a'*64, {})
                if status != 'awaiting_approval':
                    await app.chat.automation.repository.transition(cid, oid, ['awaiting_approval'], status)
            for _ in range(35):
                await app.chat.repository.append(cid, 'user', '合成普通消息')
            expected = {'development':{'draft_id':draft['draft_id'],'kind':'code'},'cleanup':{'plan_id':plan['plan_id']},'automation':['browser','desktop','script']}
            before = (await call(app, 'chat.get', {'id':cid}))['result']
            assert before['messages_truncated'] and before['workspace_history'] == expected
            assert not (root / 'App.tsx').exists()
            await app.close()
            app = await setup(tmp_path)
            restored = (await call(app, 'chat.get', {'id':cid}))['result']
            assert restored['workspace_history'] == expected and restored['grant'] is None
            assert (await call(app, 'chat.get', {'id':other}))['result']['workspace_history'] == {'development':None,'cleanup':None,'automation':[]}
            denied = await call(app, 'chat.development.apply', {'id':cid,'draft_id':draft['draft_id'],'revision':draft['revision'],'index':0})
            assert denied['error']['code'] == 'PERMISSION_DENIED'
            assert not (root / 'App.tsx').exists()
        finally:
            await app.close()
    asyncio.run(run())
