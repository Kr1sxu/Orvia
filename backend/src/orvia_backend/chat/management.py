"""V3会话管理：永久删除只作用于本地会话资料，不撤销或删除用户文件。"""
import asyncio
import json
import os
import shutil
import stat
from uuid import UUID

from ..computer.paths import ToolError


async def deletion_blockers(chat, cid):
    """检查全部账本而非最近20条；未知状态保守阻止，不能丢弃恢复/核验入口。"""
    if cid in chat._active:
        return True
    processes = getattr(chat, 'processes', None)
    if processes is not None and await processes.has_unresolved(cid):
        return True
    shell = getattr(chat, 'shell', None)
    if shell is not None and await shell.has_unresolved(cid):
        return True
    automation = chat.automation
    if any(item['cid'] == cid and not item['task'].done() for item in automation.active.values()):
        return True
    if any(automation.scripts.live.get(oid, {}).get('cid') == cid and not task.done()
           for oid, task in automation.scripts.tasks.items()):
        return True
    if automation.browser and any(s.cid == cid and not s.closed for s in automation.browser._sessions.values()):
        return True
    async with chat.store._lock:
        db = chat.store._db()
        checks = (
            ("SELECT 1 FROM m20_workflows WHERE conversation_id=? AND state IN ('running','waiting_input','waiting_approval')",),
            ("SELECT 1 FROM operation_tasks WHERE mission_id=? AND status NOT IN ('completed','undone','failed')",),
            ("SELECT 1 FROM m18_operations WHERE conversation_id=? AND status NOT IN ('completed','verified','failed','cancelled','rejected')",),
            ("SELECT 1 FROM m17_cleanup WHERE conversation_id=? AND status IN ('planned','running','interrupted','partial')",),
        )
        for (sql,) in checks:
            async with db.execute(sql + ' LIMIT 1', (cid,)) as cursor:
                if await cursor.fetchone():
                    return True
        async with db.execute('SELECT plan_json FROM m17_drafts WHERE conversation_id=?', (cid,)) as cursor:
            for row in await cursor.fetchall():
                if any(item.get('status') == 'pending' for item in json.loads(row[0]).get('files', [])):
                    return True
        # 隔离文件仍是用户文件：先恢复，不能把删除聊天变成永久清理或切断恢复入口。
        async with db.execute("SELECT plan_json FROM m17_cleanup WHERE conversation_id=?", (cid,)) as cursor:
            for row in await cursor.fetchall():
                if any(e.get('status') in {'moved','moving','uncertain'} for e in json.loads(row[0]).get('entries', [])):
                    return True
    return False


def remove_private_script(root, oid):
    """仅删除已结束任务的私有副本；固定UUID子目录、完整预检且拒绝重解析点。"""
    oid = str(UUID(oid))
    target = root / oid
    if not os.path.lexists(target):
        return
    for parent in (target, *target.parents):
        if getattr(parent.lstat(), 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT or parent.is_symlink():
            raise ToolError('DELETE_UNAVAILABLE', '私有任务目录异常，未删除会话')
    if target.resolve().parent != root.resolve():
        raise ToolError('DELETE_UNAVAILABLE', '私有任务路径越界')
    for directory, dirs, files in os.walk(target, followlinks=False):
        for name in dirs + files:
            entry = type(target)(directory) / name
            if getattr(entry.lstat(), 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT or entry.is_symlink():
                raise ToolError('DELETE_UNAVAILABLE', '私有副本含链接，停止删除')
    shutil.rmtree(target)


async def purge(chat, cid):
    """已确认删除的幂等收尾；journal先阻断旧身份，跨文件/数据库中断可在启动重做清理。"""
    chat.gateway.revoke(cid)
    processes = getattr(chat, 'processes', None)
    if processes is not None:
        # 仅撤销本应用审批缓存；删除会话不能结束任何用户应用进程。
        processes.forget_previews(cid)
    shell = getattr(chat, 'shell', None)
    if shell is not None:
        # 只清独立任务私有副本；原生选的输入/工作目录及已回传成品永不随会话删除。
        await shell.purge_files(cid)
        shell.forget_previews(cid)
    if chat.automation.desktop:
        chat.automation.desktop.revoke(cid)
    async with chat.store._lock:
        async with chat.store._db().execute("SELECT id FROM m18_operations WHERE conversation_id=? AND kind='script'", (cid,)) as cursor:
            scripts = [row[0] for row in await cursor.fetchall()]
    for oid in scripts:
        remove_private_script(chat.automation.scripts.root, oid)
        chat.automation.scripts.live.pop(oid, None)
        chat.automation.scripts.tasks.pop(oid, None)
    for cache in (chat.automation.plans, chat.automation.active):
        for oid, item in list(cache.items()):
            if item['cid'] == cid:
                del cache[oid]
    for key in list(chat.automation.browser_operations):
        if key[0] == cid:
            del chat.automation.browser_operations[key]
    if chat.automation.browser:
        for sid, session in list(chat.automation.browser._sessions.items()):
            if session.cid == cid:
                del chat.automation.browser._sessions[sid]
    await chat.graph.delete_conversation(cid)
    async with chat.store._lock:
        db = chat.store._db()
        await db.execute('BEGIN IMMEDIATE')
        try:
            await db.execute('DELETE FROM operation_entries WHERE task_id IN (SELECT id FROM operation_tasks WHERE mission_id=?)', (cid,))
            await db.execute('DELETE FROM context_chunks WHERE document_id IN (SELECT id FROM context_documents WHERE mission_id=?)', (cid,))
            # V4派生索引由片段FK级联清理；并发代数也删除，只留既有随机ID删除标记。
            # 初次迁移/启动恢复可能先于检索表创建，不能因此中断旧会话删除。
            async with db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='retrieval_epochs'") as cursor:
                has_retrieval_epochs = await cursor.fetchone() is not None
            if has_retrieval_epochs:
                await db.execute('DELETE FROM retrieval_epochs WHERE mission_id=?', (cid,))
            # 长期记忆及批准批次属于会话派生正文；删除必须在同一事实事务中清理。
            # 启动恢复可能早于新表迁移，只处理实际已存在的固定白名单表。
            for memory_table in ('memory_candidates', 'memory_records', 'memory_summaries', 'memory_batches', 'memory_attempts', 'memory_revocations', 'memory_fts'):
                async with db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (memory_table,)) as cursor:
                    if await cursor.fetchone():
                        await db.execute(f'DELETE FROM {memory_table} WHERE cid=?', (cid,))
            # 来源图谱及无正文调用事实同属被删除会话，不能通过重启或缓存恢复。
            for graph_table in ('graph_entities', 'graph_relations', 'graph_batches', 'graph_attempts', 'graph_processed', 'graph_revocations'):
                async with db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (graph_table,)) as cursor:
                    if await cursor.fetchone():
                        await db.execute(f'DELETE FROM {graph_table} WHERE cid=?', (cid,))
            for rewrite_table in ('rewrite_previews', 'rewrite_attempts', 'rewrite_records'):
                async with db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (rewrite_table,)) as cursor:
                    if await cursor.fetchone():
                        await db.execute(f'DELETE FROM {rewrite_table} WHERE cid=?', (cid,))
            # MCP调用事实属于会话，全局服务配置不授予会话权限，也不随会话删除外部数据。
            for mcp_table in ('mcp_attempts', 'mcp_executions'):
                async with db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (mcp_table,)) as cursor:
                    if await cursor.fetchone():
                        await db.execute(f'DELETE FROM {mcp_table} WHERE cid=?', (cid,))
            # 本地Skills计划/结果归属明确选择的会话，旧目录Mission不受此删除影响。
            for shell_table in ('shell_attempts', 'shell_executions', 'process_attempts', 'process_executions'):
                async with db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (shell_table,)) as cursor:
                    if await cursor.fetchone():
                        await db.execute(f'DELETE FROM {shell_table} WHERE cid=?', (cid,))
            async with db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='skills_executions'") as cursor:
                if await cursor.fetchone():
                    await db.execute('DELETE FROM skills_executions WHERE mission_id=?', (cid,))
            await db.execute('DELETE FROM m20_scan_entries WHERE scan_id IN (SELECT id FROM m20_scans WHERE conversation_id=?)', (cid,))
            for table in ('context_fts','context_documents','context_preferences','context_summaries','browser_evidence','document_evidence','operation_tasks'):
                await db.execute(f'DELETE FROM {table} WHERE mission_id=?', (cid,))
            for table in ('chat_messages','chat_requests','m17_drafts','m17_cleanup','m18_operations','m20_workflows','m20_removed_sources','m20_materials','m20_materials_initialized','m20_streams','m20_scans'):
                await db.execute(f'DELETE FROM {table} WHERE conversation_id=?', (cid,))
            await db.execute('DELETE FROM chat_conversations WHERE id=?', (cid,))
            await db.execute('DELETE FROM missions WHERE id=?', (cid,))
            # 仅保留随机ID墓碑防止旧请求复活，不保存标题、正文、证据或用户路径。
            await db.execute("UPDATE chat_deletions SET state='completed' WHERE id=?", (cid,))
            await db.commit()
        except BaseException:
            await db.rollback()
            raise


async def delete(chat, cid):
    async with chat._locks.setdefault(cid, asyncio.Lock()):
        async with chat.automation.locks.setdefault(cid, asyncio.Lock()):
            await chat.repository.get(cid)
            if await deletion_blockers(chat, cid):
                raise ToolError('DELETE_BLOCKED', '任务运行、待审批、结果不确定或隔离文件未恢复，请先处理任务；不会自动取消外部副作用')
            async with chat.store._lock:
                await chat.store._db().execute("INSERT INTO chat_deletions VALUES (?,'pending')", (cid,))
            try:
                await purge(chat, cid)
            except (OSError, ValueError) as exc:
                raise ToolError('DELETE_UNAVAILABLE', '删除尚未完成；重启后继续清理，不会恢复会话') from exc
    return {'deleted': True, 'id': cid}
