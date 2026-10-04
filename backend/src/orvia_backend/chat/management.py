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
