"""V3-004 逐目标事实状态；与执行权限分离，重开只投影，不重放业务。"""
import json

from ..computer.paths import ToolError
from .verification import snapshot, digest, require, rows

DONE = {'completed', 'accepted'}


class TaskProgress:
    def __init__(self, chat):
        self.chat = chat

    async def install(self, cid, rid, plan):
        states = [{'status': 'not_started', 'detail': '', 'result_id': None} for _ in plan.steps]
        async with self.chat.store._lock:
            await self.chat.store._db().execute(
                "UPDATE m20_workflows SET plan_json=?,step_states=? WHERE conversation_id=? AND request_id=? AND position=0 AND state IN('running','waiting_input','waiting_approval') AND conversation_id NOT IN(SELECT id FROM chat_deletions)",
                (plan.model_dump_json(), json.dumps(states), cid, rid))

    async def set(self, cid, rid, index, status, detail='', result_id=None, context=None):
        """只更新当前目标；成功须准确证据封印，终态迟到结果不能覆盖旧结论。"""
        async with self.chat.store._lock:
            db = self.chat.store._db()
            async with db.execute('SELECT * FROM m20_workflows WHERE conversation_id=? AND request_id=?', (cid, rid)) as cursor:
                row = await cursor.fetchone()
            if not row or row['state'] not in {'running','waiting_input','waiting_approval'}:return False
            if await rows(db,'SELECT 1 FROM chat_deletions WHERE id=?',(cid,)):return False
            states = json.loads(row['step_states'])
            if not 0 <= index < len(states):
                return  # 旧库和尚未完成路由的请求没有逐目标事实，不补造成功。
            require(index==row['position'])
            if states[index]['status'] in DONE:return False
            require(status!='accepted')  # 用户接受只走事务内消费continuation的专用入口。
            item={'status': status, 'detail': detail[:600], 'result_id': result_id,'baseline':states[index].get('baseline',row['baseline'])}
            if states[index].get('review'):item['review']=states[index]['review']
            if status=='running' and states[index]['status']=='not_started':
                item['baseline']=(await rows(db,'SELECT COALESCE(MAX(sequence),0) FROM chat_messages WHERE conversation_id=?',(cid,)))[0][0]
            if status=='completed':
                kind=json.loads(row['plan_json'])['steps'][index]['kind']
                require(kind in {'list','search','space','read_url','web_search','material_quote','answer','task_summary'})
                require(not any(s.get('result_id')==result_id for s in states[:index] if s['status']=='completed'))
                item['verification']=await snapshot(db,dict(row),index,item,context)
            states[index]=item
            await db.execute('UPDATE m20_workflows SET step_states=? WHERE conversation_id=? AND request_id=?', (json.dumps(states, ensure_ascii=False), cid, rid))
            return True

    async def bind_review(self,cid,rid,token,workflow):
        """接续规范只存内部逐步账本，保持公开workflow与UI schema不变。"""
        async with self.chat.store._lock:
            db=self.chat.store._db();await db.execute('BEGIN IMMEDIATE')
            try:
                values=await rows(db,'SELECT * FROM m20_workflows WHERE conversation_id=? AND request_id=?',(cid,rid))
                if not values:
                    await db.rollback();return False
                row=dict(values[0])
                if row['state'] not in {'waiting_input','waiting_approval'} or row['continuation_id']!=token or await rows(db,'SELECT 1 FROM chat_deletions WHERE id=?',(cid,)):
                    await db.rollback();return False
                states=json.loads(row['step_states']);steps=json.loads(row['plan_json'])
                if isinstance(steps,dict) and 0<=row['position']<len(states):
                    states[row['position']]['review']={'token':token,'step':digest(steps['steps'][row['position']]),'workflow':digest(workflow)}
                    await db.execute('UPDATE m20_workflows SET step_states=? WHERE conversation_id=? AND request_id=?',(json.dumps(states,ensure_ascii=False),cid,rid))
                # 无步骤的路由降级也只改变当前请求等待事实，不伪造动作完成封印。
                await db.execute("UPDATE chat_requests SET status=? WHERE conversation_id=? AND request_id=? AND status IN('pending','waiting_input','waiting_approval')",(row['state'],cid,rid))
                await db.commit();return True
            except BaseException:await db.rollback();raise

    async def complete_continuation(self,cid,rid,index,token,result_id,context):
        """准确结果、步骤封印、接续token消费与推进共用事务，避免重复/迟到通知串步。"""
        return await self._continue(cid,rid,index,token,result_id,context,False)

    async def accept(self,cid,rid,index,token):
        """只有用户明确accept_limit的可信分支可调用；接受事实不声称任务实际执行。"""
        return await self._continue(cid,rid,index,token,None,None,True)

    async def _continue(self,cid,rid,index,token,result_id,context,accepted):
        async with self.chat.store._lock:
            db=self.chat.store._db();await db.execute('BEGIN IMMEDIATE')
            try:
                values=await rows(db,'SELECT * FROM m20_workflows WHERE conversation_id=? AND request_id=?',(cid,rid))
                require(values and not await rows(db,'SELECT 1 FROM chat_deletions WHERE id=?',(cid,)))
                row=dict(values[0])
                if row['state'] not in {'waiting_input','waiting_approval'} or row['position']!=index or row['continuation_id']!=token:
                    raise ToolError('STALE_CONTINUATION','接续身份或目标已变化，没有推进或重放')
                states=json.loads(row['step_states']);require(index<len(states) and states[index]['status'] not in DONE)
                workflow=json.loads(row['workflow_json']);require(workflow['continuation_id']==token)
                review=states[index].get('review',{});step=json.loads(row['plan_json'])['steps'][index]
                require(review=={'token':token,'step':digest(step),'workflow':digest(workflow)})
                if not accepted:
                    require(context and context.get('action')==workflow['action'] and context.get('continuation_id')==token)
                    actual=dict(context.get('input',{}));expected=dict(workflow.get('input',{}))
                    if workflow['action'] in {'synthesis','stream_fallback'}:actual.pop('revision',None);expected.pop('revision',None)
                    require(actual==expected)
                item={'status':'accepted' if accepted else 'completed','detail':states[index].get('detail','') if accepted else '', 'result_id':result_id,'baseline':states[index].get('baseline',row['baseline'])}
                if accepted:
                    require(workflow['action']=='task_decision' and states[index]['status'] in {'limited','unsupported','blocked'})
                    step=json.loads(row['plan_json'])['steps'][index]
                    data={'request_id':rid,'position':index,'step_revision':digest(step),'continuation_id':token}
                    message=self.chat.repository._message('user','接受此项目标未执行或仅有受限结果，继续检查剩余目标。','task_acceptance',data)
                    await db.execute('INSERT INTO chat_messages(conversation_id,message_json) VALUES(?,?)',(cid,json.dumps(message,ensure_ascii=False)))
                    item['result_id']=message['id'];context={'continuation_id':token}
                require(not any(s.get('result_id')==item['result_id'] for s in states[:index] if s['status'] in DONE))
                item['verification']=await snapshot(db,row,index,item,context);states[index]=item
                await db.execute("UPDATE m20_workflows SET step_states=?,state='running',position=?,continuation_id=NULL,workflow_json=NULL WHERE conversation_id=? AND request_id=?",(json.dumps(states,ensure_ascii=False),index+1,cid,rid))
                await db.execute("UPDATE chat_requests SET status='pending' WHERE conversation_id=? AND request_id=? AND status IN('waiting_input','waiting_approval')",(cid,rid))
                await db.commit()
            except BaseException:await db.rollback();raise

    async def terminal(self, row, state):
        """逐目标重读当前事实；封印无效或未完成不允许整体成功，旧传入row不可信。"""
        async with self.chat.store._lock:
            db=self.chat.store._db()
            current=await rows(db,'SELECT * FROM m20_workflows WHERE conversation_id=? AND request_id=?',(row['conversation_id'],row['request_id']))
            require(current);row=dict(current[0]);await self._check(db,row,state)

    async def _check(self,db,row,state):
        states=json.loads(row['step_states']);plan=json.loads(row['plan_json'])
        count = len(plan.get('steps', [])) if isinstance(plan, dict) else 0
        if state == 'completed' and count and (len(states) != count or row['position'] != count or any(item['status'] not in DONE for item in states)):
            raise ToolError('TASK_NOT_COMPLETE', '仍有未完成或尚未接受的目标，不能结束为已完成')
        if state=='completed':
            if not count:
                messages=await rows(db,"SELECT 1 FROM chat_messages WHERE conversation_id=? AND json_extract(message_json,'$.kind')='natural_answer' AND json_extract(message_json,'$.data.origin')='local' AND json_extract(message_json,'$.data.request_id')=?",(row['conversation_id'],row['request_id']))
                require(messages)  # 无步骤仅允许真实已保存的本地寒暄，不允许空计划结束动作。
            for index,item in enumerate(states):
                seal=item.get('verification');require(seal)
                require(await snapshot(db,row,index,item,seal.get('context'))==seal)

    async def finish(self,cid,rid,state):
        """终态验证与workflow/request封存同事务；重复和迟到结束通知无副作用。"""
        async with self.chat.store._lock:
            require(state in {'completed','failed','cancelled'})
            db=self.chat.store._db();await db.execute('BEGIN IMMEDIATE')
            try:
                values=await rows(db,'SELECT * FROM m20_workflows WHERE conversation_id=? AND request_id=?',(cid,rid))
                if not values or values[0]['state'] in {'completed','cancelled','failed','interrupted'}:
                    await db.rollback();return None
                require(not await rows(db,'SELECT 1 FROM chat_deletions WHERE id=?',(cid,)))
                row=dict(values[0]);await self._check(db,row,state);states=json.loads(row['step_states'])
                if state in {'failed','cancelled'}:
                    for index,item in enumerate(states):
                        if item['status'] not in DONE and (state=='cancelled' or index==row['position']):item.update(status=state,detail='未完成；没有自动重试或重放。',result_id=None)
                await db.execute('UPDATE m20_workflows SET state=?,continuation_id=NULL,workflow_json=NULL,step_states=? WHERE conversation_id=? AND request_id=?',(state,json.dumps(states,ensure_ascii=False),cid,rid))
                await db.execute('UPDATE chat_requests SET status=? WHERE conversation_id=? AND request_id=?',(state,cid,rid))
                await db.commit();return row
            except BaseException:await db.rollback();raise

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
