"""V3-003：临时库和合成资料，永久删除、跨会话隔离、失败恢复，不调用模型。"""
import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from test_chat import setup, create, call
from orvia_backend.chat.management import deletion_blockers, remove_private_script
from orvia_backend.computer.paths import ToolError
from orvia_backend.context import ContextService
from langgraph.checkpoint.base import empty_checkpoint


def test_management_persistence_validation_and_migration(tmp_path):
    async def scenario():
        app = await setup(tmp_path)
        try:
            a, b = (await create(app))['id'], (await create(app))['id']
            db = app.store._db()
            models = (await (await db.execute('SELECT models_json FROM missions WHERE id=?', (a,))).fetchone())[0]
            # 模拟V3-002旧表，重开时追加元数据，消息和固定模型快照不能重建。
            await db.execute('ALTER TABLE chat_conversations DROP COLUMN pinned')
            await db.execute('ALTER TABLE chat_conversations DROP COLUMN updated_at')
            await app.chat.repository.open()
            assert (await call(app, 'chat.pin', {'id': a, 'pinned': True}))['ok']
            assert (await call(app, 'chat.rename', {'id': a, 'title': '  新名称  '}))['result']['title'] == '新名称'
            for title in ('  ', 'x\ntext', 'x' * 101):
                assert not (await call(app, 'chat.rename', {'id': a, 'title': title}))['ok']
            assert not (await call(app, 'chat.pin', {'id': a, 'pinned': 1}))['ok']
            assert not (await call(app, 'chat.delete', {'id': a, 'force': True}))['ok']
            assert (await (await db.execute('SELECT models_json FROM missions WHERE id=?', (a,))).fetchone())[0] == models
        finally:
            await app.close()
        app = await setup(tmp_path)
        try:
            rows = (await call(app, 'chat.list'))['result']['conversations']
            assert rows[0]['id'] == a and rows[0]['pinned'] and rows[0]['title'] == '新名称'
            assert (await call(app, 'chat.pin', {'id': a, 'pinned': False}))['ok']
            await app.chat.repository.append(b, 'user', '最新活动')
            assert (await call(app, 'chat.list'))['result']['conversations'][0]['id'] == b
        finally:
            await app.close()
        app = await setup(tmp_path)
        try:
            rows = (await call(app, 'chat.list'))['result']['conversations']
            assert rows[0]['id'] == b and not any(row['pinned'] for row in rows)
        finally:
            await app.close()
    asyncio.run(scenario())


def test_delete_all_local_evidence_and_private_copies_only(tmp_path):
    async def scenario():
        app = await setup(tmp_path)
        original = tmp_path / 'user.txt'
        original.write_text('用户原件与导出成品', encoding='utf8')
        try:
            a, b = (await create(app))['id'], (await create(app))['id']
            db = app.store._db()
            for cid in (a, b):
                await app.chat.repository.append(cid, 'user', '机密合成文字')
                await ContextService(app.store).index_text(cid, 'synthetic', '合成检索证据内容')
                for table in ('browser_evidence', 'document_evidence'):
                    await db.execute(f'INSERT INTO {table} VALUES (?,?,?)', (str(uuid4()), cid, json.dumps({'content': '合成原文'})))
            # 证据用最小存储夹具；授权直接走程序网关，避免夹具被完整快照格式校验。
            from orvia_backend.computer.contracts import GrantRequest
            app.chat.gateway.grant(GrantRequest(mission_id=a, root=str(tmp_path)))
            tid = str(uuid4())
            await db.execute('INSERT INTO operation_tasks VALUES (?,?,?,?,?,?,?,?)', (tid, a, str(tmp_path), 'completed', '{}', None, 'now', 'now'))
            await db.execute('INSERT INTO operation_entries VALUES (?,?,?,?,?,?,?,?,?)', (tid, 1, 'mkdir', None, str(original), 'completed', None, '{}', None))
            oid = await app.chat.automation.repository.create(a, 'script', 'rev', {})
            await app.chat.automation.repository.transition(a, oid, ['awaiting_approval'], 'completed')
            private = app.chat.automation.scripts.root / oid
            private.mkdir(parents=True)
            (private / 'script.py').write_text('print("synthetic")')
            # 历史图线程和仅落初始输入的线程均须清除，保留另一会话的checkpoint。
            for cid in (a, a, b):
                await app.graph._graph.aupdate_state({'configurable': {'thread_id': str(uuid4())}}, {'mission_id': cid, 'goal': '合成'}, as_node='route')
            checkpoint = empty_checkpoint()
            checkpoint['channel_values'] = {'__start__': {'mission_id': a, 'goal': '初始合成输入'}}
            await app.graph._checkpointer.aput({'configurable': {'thread_id': str(uuid4()), 'checkpoint_ns': ''}}, checkpoint, {'source': 'input', 'step': -1, 'parents': {}}, {})
            app.chat.automation.plans[oid] = {'cid': a, 'plan': {'source': 'sensitive'}}
            assert (await call(app, 'chat.delete', {'id': a}))['result']['deleted']
            assert not private.exists() and original.read_text(encoding='utf8') == '用户原件与导出成品'
            assert oid not in app.chat.automation.plans
            with pytest.raises(ToolError):
                app.chat.gateway.authorized_root(a)
            with pytest.raises(ToolError):
                await app.chat.repository.append(a, 'system', '晚到的消息')
            assert not await (await db.execute('SELECT 1 FROM operation_entries WHERE task_id=?', (tid,))).fetchone()
            for table, column in [('chat_messages', 'conversation_id'), ('m18_operations', 'conversation_id'), ('context_fts', 'mission_id'), ('context_chunks', 'mission_id'), ('context_documents', 'mission_id'), ('browser_evidence', 'mission_id'), ('document_evidence', 'mission_id'), ('missions', 'id')]:
                assert (await (await db.execute(f'SELECT COUNT(*) FROM {table} WHERE {column}=?', (a,))).fetchone())[0] == 0
            entries = [entry async for entry in app.graph._checkpointer.alist(None)]
            assert entries and all(entry.checkpoint['channel_values'].get('mission_id') == b for entry in entries)
            assert (await app.chat.repository.messages(b))[1] >= 1
            for method in ('chat.get', 'chat.delete_check', 'chat.delete'):
                assert (await call(app, method, {'id': a}))['error']['code'] == 'NOT_FOUND'
        finally:
            await app.close()
        app = await setup(tmp_path)
        try:
            assert [x['id'] for x in (await call(app, 'chat.list'))['result']['conversations']] == [b]
        finally:
            await app.close()
    asyncio.run(scenario())


@pytest.mark.parametrize('status', ['awaiting_approval', 'running', 'interrupted', 'uncertain', 'future_unknown'])
def test_delete_blocks_all_history_not_only_recent_twenty(tmp_path, status):
    async def scenario():
        app = await setup(tmp_path)
        try:
            cid = (await create(app))['id']
            repo = app.chat.automation.repository
            for index in range(23):
                oid = await repo.create(cid, 'script', 'revision', {})
                await repo.transition(cid, oid, ['awaiting_approval'], status if index == 0 else 'completed')
            assert (await call(app, 'chat.delete_check', {'id': cid}))['result']['blocked']
            assert (await call(app, 'chat.delete', {'id': cid}))['error']['code'] == 'DELETE_BLOCKED'
            assert (await call(app, 'chat.get', {'id': cid}))['ok']
        finally:
            await app.close()
    asyncio.run(scenario())


def test_confirmed_delete_failure_resumes_on_restart(tmp_path, monkeypatch):
    async def scenario():
        app = await setup(tmp_path)
        cid = (await create(app))['id']
        async def failed(_):
            raise OSError('synthetic interruption')
        monkeypatch.setattr(app.graph, 'delete_conversation', failed)
        try:
            assert (await call(app, 'chat.delete', {'id': cid}))['error']['code'] == 'DELETE_UNAVAILABLE'
            assert (await call(app, 'chat.get', {'id': cid}))['error']['code'] == 'NOT_FOUND'
        finally:
            await app.close()
        app = await setup(tmp_path)
        try:
            assert (await call(app, 'chat.list'))['result']['conversations'] == []
            row = await (await app.store._db().execute('SELECT state FROM chat_deletions WHERE id=?', (cid,))).fetchone()
            assert row[0] == 'completed'
        finally:
            await app.close()
    asyncio.run(scenario())


def test_private_copy_rejects_non_uuid(tmp_path):
    with pytest.raises(ValueError):
        remove_private_script(tmp_path, '../user-files')


def test_private_copy_rejects_reparse_before_removing_files(tmp_path, monkeypatch):
    from pathlib import Path
    import stat
    root = tmp_path / 'scripts'
    oid = str(uuid4())
    target = root / oid
    target.mkdir(parents=True)
    original = target / 'synthetic.txt'
    original.write_text('preserve')
    lstat = Path.lstat
    def reparse(path, *args, **kwargs):
        if path == root:
            return SimpleNamespace(st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT)
        return lstat(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'lstat', reparse)
    with pytest.raises(ToolError, match='私有任务目录异常'):
        remove_private_script(root, oid)
    assert original.read_text() == 'preserve'


@pytest.mark.parametrize('kind', ['cleanup', 'draft'])
def test_quarantined_file_or_pending_draft_blocks_delete(tmp_path, kind):
    async def scenario():
        app = await setup(tmp_path)
        try:
            cid = (await create(app))['id']
            db = app.store._db()
            if kind == 'cleanup':
                await db.execute('INSERT INTO m17_cleanup VALUES (?,?,?,?,?,?)',
                                 (str(uuid4()), cid, 'completed', json.dumps({'entries': [{'status': 'moved'}]}), 'now', 'now'))
            else:
                await db.execute('INSERT INTO m17_drafts VALUES (?,?,?,?,?,?,?,?)',
                                 (str(uuid4()), cid, str(tmp_path), '1', '1', 'code', json.dumps({'files': [{'status': 'pending'}]}), 'now'))
            assert (await call(app, 'chat.delete', {'id': cid}))['error']['code'] == 'DELETE_BLOCKED'
        finally:
            await app.close()
    asyncio.run(scenario())


def test_finishing_worker_and_open_browser_block(tmp_path):
    async def scenario():
        app = await setup(tmp_path)
        cid = (await create(app))['id']
        task = asyncio.create_task(asyncio.Event().wait())
        try:
            app.chat.automation.active['test'] = {'cid': cid, 'task': task}
            assert await deletion_blockers(app.chat, cid)
            app.chat.automation.active.clear()
            app.chat.automation.browser = SimpleNamespace(_sessions={'test': SimpleNamespace(cid=cid, closed=False)})
            assert await deletion_blockers(app.chat, cid)
        finally:
            app.chat.automation.browser = None
            app.chat.automation.active.clear()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await app.close()
    asyncio.run(scenario())
