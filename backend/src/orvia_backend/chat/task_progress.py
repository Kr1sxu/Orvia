"""V3-004 逐目标事实状态；与执行权限分离，重开只投影，不重放业务。"""
import json

from ..computer.paths import ToolError

DONE = {'completed', 'accepted'}


class TaskProgress:
    def __init__(self, chat):
        self.chat = chat

    async def install(self, cid, rid, plan):
        states = [{'status': 'not_started', 'detail': '', 'result_id': None} for _ in plan.steps]
        async with self.chat.store._lock:
            await self.chat.store._db().execute(
                'UPDATE m20_workflows SET plan_json=?,step_states=? WHERE conversation_id=? AND request_id=?',
                (plan.model_dump_json(), json.dumps(states), cid, rid))

    async def set(self, cid, rid, index, status, detail='', result_id=None):
        async with self.chat.store._lock:
            db = self.chat.store._db()
            async with db.execute('SELECT step_states FROM m20_workflows WHERE conversation_id=? AND request_id=?', (cid, rid)) as cursor:
                row = await cursor.fetchone()
            states = json.loads(row[0]) if row else []
            if not 0 <= index < len(states):
                return  # 旧库和尚未完成路由的请求没有逐目标事实，不补造成功。
            states[index] = {'status': status, 'detail': detail[:600], 'result_id': result_id}
            await db.execute('UPDATE m20_workflows SET step_states=? WHERE conversation_id=? AND request_id=?', (json.dumps(states, ensure_ascii=False), cid, rid))

    async def terminal(self, row, state):
        states = json.loads(row['step_states'])
        plan = json.loads(row['plan_json'])
        count = len(plan.get('steps', [])) if isinstance(plan, dict) else 0
        if state == 'completed' and count and (len(states) != count or row['position'] != count or any(item['status'] not in DONE for item in states)):
            raise ToolError('TASK_NOT_COMPLETE', '仍有未完成或尚未接受的目标，不能结束为已完成')
        if state in {'failed', 'cancelled'}:
            for index, item in enumerate(states):
                if item['status'] not in DONE and (state == 'cancelled' or index == row['position']):
                    await self.set(row['conversation_id'], row['request_id'], index, state, '未完成；没有自动重试或重放。')

    async def project(self, cid):
        row = await self.chat.natural.row(cid)
        if not row:
            return None
        raw = json.loads(row['plan_json'])
        steps = raw.get('steps', []) if isinstance(raw, dict) else []
        states = json.loads(row['step_states'])
        if not states:
            return None
        projected = []
        for index, step in enumerate(steps):
            item = states[index] if index < len(states) else {'status': 'not_started', 'detail': ''}
            status = item['status']
            if row['state'] == 'interrupted' and status not in DONE | {'not_started', 'unsupported', 'limited', 'failed', 'cancelled'}:
                status = 'interrupted'
            if status == 'not_started' and step['kind'] == 'unsupported':
                status = 'unsupported'
            projected.append({'index': index, 'title': (step.get('goal') or step.get('query') or step['kind'])[:300],
                              'kind': step['kind'], 'status': status, 'detail': item.get('detail') or (step['query'][:600] if step['kind'] == 'unsupported' else '')})
        result = {'request_id': row['request_id'], 'state': row['state'], 'instruction': row['text'], 'steps': projected}
        # 完整原文与每项目标身份必须保留；展示短摘录有独立预算，不能挤爆stdio快照。
        # 详细原因仍在当前workflow/消息及逐步骤账本中，缩短不影响状态或审批。
        while len(json.dumps(result, ensure_ascii=False).encode('utf-8')) > 12 * 1024:
            candidates = [(item, key) for item in projected for key in ('detail', 'title') if len(item[key]) > 13]
            if not candidates:
                break
            item, key = max(candidates, key=lambda pair: len(pair[0][pair[1]].encode('utf-8')))
            item[key] = item[key][:max(12, len(item[key]) // 2)] + '…'
        return result

    async def summary(self, cid, rid):
        """摘要只汇总本请求程序状态，绝不把目录属性提升为清理/闲置结论。"""
        row = await self.chat.natural.row(cid, rid)
        plan = json.loads(row['plan_json'])
        states = json.loads(row['step_states'])
        labels = {'completed': '已完成', 'accepted': '已接受未执行/受限范围', 'unsupported': '不支持',
                  'limited': '仅部分结果', 'failed': '失败', 'cancelled': '已取消', 'running': '处理中',
                  'waiting_authorization': '等待授权', 'waiting_approval': '等待审批', 'waiting_input': '等待必要信息',
                  'not_started': '未开始', 'blocked': '前置结果缺失', 'interrupted': '已中断'}
        lines = []
        for step, item in zip(plan.get('steps', []), states):
            if step['kind'] == 'task_summary':
                continue
            lines.append(f"{labels[item['status']]}：{(step.get('goal') or step.get('query') or step['kind'])[:180]}" +
                         (f"（{item['detail'][:200]}）" if item.get('detail') else ''))
        return '本次目标进度：\n' + '\n'.join(lines)
