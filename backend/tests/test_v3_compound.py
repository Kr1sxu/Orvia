"""V3-004临时库/合成目录，不访问真实C盘、不调用真实模型、不批准副作用。"""
import asyncio
import json
from uuid import uuid4

import pytest
from test_chat import setup, create, call
from orvia_backend.chat.routing import understand, Route, Step
from orvia_backend.computer.paths import ToolError

REQUEST = '扫描 C 盘垃圾文件并找出占用空间较大的可清理项；扫描已安装应用并找出长期未使用或从未使用的闲置应用；分析风险等级并给出清理或保留建议；输出包含清单、空间、风险和建议的 Doc 文档；在对话框给出摘要并指出高价值清理项。'


def continuation(cid, snapshot, answer=None):
    wf = snapshot['workflow']
    return {'id': cid, 'request_id': wf['request_id'], 'continuation_id': wf['continuation_id'], **({'answer': answer} if answer else {})}


def test_full_request_keeps_every_goal_and_waits_for_explicit_acceptance(tmp_path):
    async def run():
        app = await setup(tmp_path)
        cid = (await create(app))['id']
        root = tmp_path / 'synthetic'
        root.mkdir()
        (root / 'keep.txt').write_text('original')
        async def forbidden(*args, **kwargs):
            raise AssertionError('不可调用模型或生成未经核验的文档')
        app.chat.client.stream = forbidden
        app.chat.publication_save = forbidden
        rid = str(uuid4())
        try:
            first = (await call(app, 'chat.natural', {'id': cid, 'request_id': rid, 'text': REQUEST}))['result']
            assert first['workflow']['action'] == 'directory'
            titles = '；'.join(x['title'] for x in first['task_progress']['steps'])
            for phrase in ['扫描 C 盘', '扫描已安装应用', '长期未使用', '分析风险', '保留建议', 'Doc 文档', '对话框', '高价值']:
                assert phrase in titles
            await call(app, 'chat.grant', {'id': cid, 'root': str(root)})
            snapshot = (await call(app, 'chat.continue', continuation(cid, first)))['result']
            assert snapshot['status'] != 'completed'
            assert snapshot['task_progress']['steps'][0]['status'] == 'completed'
            assert snapshot['workflow']['action'] == 'task_decision'
            assert any('未实现已安装应用' in x['detail'] for x in snapshot['task_progress']['steps'])
            count = len(snapshot['task_progress']['steps'])
            assert (await call(app, 'chat.continue', continuation(cid, snapshot)))['error']['code'] == 'EXPLICIT_ACCEPTANCE_REQUIRED'
            other = (await create(app))['id']
            assert not (await call(app, 'chat.continue', {**continuation(cid, snapshot, 'accept_limit'), 'id': other}))['ok']
            for _ in range(16):
                if not snapshot['workflow']:
                    break
                token = continuation(cid, snapshot, 'accept_limit')
                snapshot = (await call(app, 'chat.continue', token))['result']
                assert (await call(app, 'chat.continue', token))['error']['code'] == 'STALE_CONTINUATION'
                assert len(snapshot['task_progress']['steps']) == count
            assert snapshot['status'] == 'completed'
            assert all(x['status'] in {'completed', 'accepted'} for x in snapshot['task_progress']['steps'])
            assert any('前置' in x['detail'] for x in snapshot['task_progress']['steps'] if x['kind'] == 'publication')
            assert not any(x['kind'] in {'publication', 'synthesis'} for x in snapshot['messages'])
            assert any(x['kind'] == 'task_summary' and '已接受' in x['text'] for x in snapshot['messages'])
            assert (root / 'keep.txt').read_text() == 'original' and len(list(root.iterdir())) == 1
        finally:
            await app.close()
    asyncio.run(run())


def test_restart_preserves_remaining_goals_and_never_replays(tmp_path):
    async def run():
        app = await setup(tmp_path)
        cid = (await create(app))['id']
        first = (await call(app, 'chat.natural', {'id': cid, 'request_id': str(uuid4()), 'text': REQUEST}))['result']
        token = continuation(cid, first)
        before = first['task_progress']
        await app.close()
        app = await setup(tmp_path)
        try:
            snapshot = (await call(app, 'chat.get', {'id': cid}))['result']
            assert snapshot['status'] == 'interrupted' and snapshot['workflow'] is None and snapshot['grant'] is None
            assert snapshot['task_progress']['instruction'] == REQUEST
            assert [x['title'] for x in snapshot['task_progress']['steps']] == [x['title'] for x in before['steps']]
            assert snapshot['task_progress']['steps'][0]['status'] == 'interrupted'
            assert not any(x['kind'] == 'directory_result' for x in snapshot['messages'])
            assert (await call(app, 'chat.continue', token))['error']['code'] == 'STALE_CONTINUATION'
        finally:
            await app.close()
    asyncio.run(run())


def test_clarification_keeps_tail_and_verified_completion_gate(tmp_path, monkeypatch):
    async def run():
        app = await setup(tmp_path)
        cid = (await create(app))['id']
        try:
            first = (await call(app, 'chat.natural', {'id': cid, 'request_id': str(uuid4()), 'text': '分析这个神秘对象；统计目录空间'}))['result']
            assert first['workflow']['action'] == 'clarification'
            tail = first['task_progress']['steps'][-1]['title']
            second = (await call(app, 'chat.continue', continuation(cid, first, '只列出目录')) )['result']
            assert second['task_progress']['steps'][-1]['title'] == tail
            assert second['workflow']['action'] == 'directory'
            with pytest.raises(ToolError, match='未完成'):
                await app.chat.natural._terminal(cid, second['workflow']['request_id'], 'completed')
        finally:
            await app.close()
    asyncio.run(run())


def test_model_cannot_drop_explicit_unknown_compound_goals(tmp_path):
    async def run():
        app = await setup(tmp_path)
        try:
            cid = (await create(app))['id']
            async def forbidden(*args, **kwargs):
                raise AssertionError('明确分句保留，不能委托模型删掉目标')
            app.chat.client.stream = forbidden
            plan = await understand(app.chat, cid, '扫描目录；分析未知对象；输出 Doc 文档', [], [], {'model': None})
            assert plan.steps[0].kind == 'list'
            assert any(x.kind == 'clarify' and '未知对象' in x.goal for x in plan.steps)
            assert plan.steps[-1].kind == 'publication'
        finally:
            await app.close()
    asyncio.run(run())


def test_confirmed_answer_fallback_continues_remaining_goals(tmp_path, monkeypatch):
    from orvia_backend.configuration.client import Completion, ModelUnavailable
    async def run():
        app = await setup(tmp_path)
        try:
            cid = (await create(app))['id']
            async def route(*args, **kwargs):
                return Route(steps=[Step(kind='answer', goal='解释概念', query='合成概念'), Step(kind='list', goal='列出目录')])
            async def stream(*args, **kwargs):
                raise ModelUnavailable('STREAM_INCOMPLETE')
            async def complete(*args, **kwargs):
                return Completion('{"answer":"合成解释"}', (), 'stop', {})
            monkeypatch.setattr('orvia_backend.chat.coordinator.understand', route)
            app.chat.client.stream, app.chat.client.complete = stream, complete
            first = (await call(app, 'chat.natural', {'id': cid, 'request_id': str(uuid4()), 'text': '解释概念，然后列出目录'}))['result']
            second = (await call(app, 'chat.fallback.confirm', continuation(cid, first)))['result']
            assert second['workflow']['action'] == 'directory' and second['status'] != 'completed'
            assert [x['status'] for x in second['task_progress']['steps']] == ['completed', 'waiting_authorization']
        finally:
            await app.close()
    asyncio.run(run())


def test_prior_scan_cannot_publish_unrelated_saved_answer(tmp_path, monkeypatch):
    async def run():
        app = await setup(tmp_path)
        try:
            cid = (await create(app))['id']
            root = tmp_path / 'files'
            root.mkdir()
            await call(app, 'chat.grant', {'id': cid, 'root': str(root)})
            await app.chat.repository.append(cid, 'assistant', '旧回答', 'synthesis', {'answer': '无关内容', 'claims': []})
            async def route(*args, **kwargs):
                return Route(steps=[Step(kind='list'), Step(kind='publication')])
            monkeypatch.setattr('orvia_backend.chat.coordinator.understand', route)
            reply = (await call(app, 'chat.natural', {'id': cid, 'request_id': str(uuid4()), 'text': '列出目录然后导出Word'}))['result']
            assert reply['workflow']['action'] == 'task_decision'
            assert reply['task_progress']['steps'][-1]['status'] == 'blocked'
        finally:
            await app.close()
    asyncio.run(run())


def test_long_progress_keeps_all_identities_with_bounded_transport(tmp_path):
    async def run():
        app = await setup(tmp_path)
        try:
            cid = (await create(app))['id']
            first = (await call(app, 'chat.natural', {'id': cid, 'request_id': str(uuid4()), 'text': '列出目录'}))['result']
            rid = first['workflow']['request_id']
            plan = Route(steps=[Step(kind='unsupported', goal='中文目标' * 70, query='合成原因' * 140) for _ in range(16)])
            await app.chat.natural.progress.install(cid, rid, plan)
            async with app.store._lock:
                await app.store._db().execute('UPDATE m20_workflows SET text=? WHERE request_id=?', ('😀' * 2000, rid))
            result = await app.chat.natural.progress.project(cid)
            assert len(result['steps']) == 16 and result['instruction'] == '😀' * 2000
            assert len(json.dumps(result, ensure_ascii=False).encode()) <= 12 * 1024
        finally:
            await app.close()
    asyncio.run(run())
