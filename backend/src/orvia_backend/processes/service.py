"""逐次进程审批与SQLite事实；不按名称批量关闭或自动升级终止。"""

import asyncio
import copy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from uuid import uuid4

from ..computer.paths import PathPolicy, ToolError
from ..memory.service import SENSITIVE, encoded, digest, size

SAFE_REFUSAL={'PROCESS_'+code for code in ('PLATFORM','API','TOKEN','ELEVATED','ISOLATED','USER','CRITICAL','PROTECTED','JOB','EXE','KEY','CHANGED','IDENTITY','PID','UNAVAILABLE','BUDGET','ARGS','CWD','LAUNCH')}


class ProcessError(ToolError):
    """公开稳定错误，不记录真实命令行、令牌SID或窗口内容。"""


def fail(code,message):
    raise ProcessError(code,message)


def utc():
    return datetime.now(timezone.utc).isoformat()


class ProcessService:
    """所有动作均需可信主进程准确原生批准，普通账户权限由native实际核验。"""

    def __init__(self,store,chat,computer,native=None):
        self.store,self.chat,self.computer=store,chat,computer
        self.native=native
        self._previews,self._pending,self._active={},set(),{}
        self._closed=False

    def _adapter(self):
        if self.native is None:
            from . import native
            return native
        return self.native

    async def _rows(self,db,sql,args=()):
        async with db.execute(sql,args) as cursor:
            return await cursor.fetchall()

    async def _alive(self,db,cid):
        if not await self._rows(db,'SELECT 1 FROM chat_conversations WHERE id=? AND id NOT IN(SELECT id FROM chat_deletions)',(cid,)):
            fail('PROCESS_CONVERSATION','所属会话不存在或正在删除')

    async def _invoke(self,method,*args,late=None,**kwargs):
        """原生线程不能安全硬取消；保持所有权直至收尾，绝不遗弃后到启动。"""
        task=asyncio.create_task(asyncio.to_thread(getattr(self._adapter(),method),*args,**kwargs))
        self._pending.add(task)
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            try:
                # 再次取消也不能取消to_thread Future，否则实际线程仍启动而身份回执丢失。
                while True:
                    try:
                        value=await asyncio.shield(task)
                        break
                    except asyncio.CancelledError:
                        if task.cancelled():
                            raise
                if late is not None:
                    late['result']=value
            except (ToolError,OSError,ValueError,RuntimeError):
                pass
            raise
        finally:
            self._pending.discard(task)

    async def open(self):
        """启动仅迁移事实并标记遗留运行结果未知，不重启程序或恢复批准。"""
        if self._active:
            fail('PROCESS_RUNNING','运行中不能执行启动恢复')
        self._previews.clear()
        async with self.store._lock:
            db=self.store._db()
            await db.execute('CREATE TABLE IF NOT EXISTS process_attempts(cid TEXT NOT NULL,operation_id TEXT NOT NULL,revision TEXT NOT NULL,state TEXT NOT NULL,PRIMARY KEY(cid,operation_id))')
            await db.execute('CREATE TABLE IF NOT EXISTS process_executions(cid TEXT NOT NULL,operation_id TEXT NOT NULL,data_json TEXT NOT NULL CHECK(json_valid(data_json)),PRIMARY KEY(cid,operation_id))')
            await db.execute('BEGIN IMMEDIATE')
            try:
                rows=await self._rows(db,"SELECT e.cid,e.operation_id,e.data_json FROM process_executions e JOIN process_attempts a ON a.cid=e.cid AND a.operation_id=e.operation_id WHERE a.state='running'")
                await db.execute("UPDATE process_attempts SET state='unknown' WHERE state='running'")
                for cid,oid,body in rows:
                    value=json.loads(body)
                    value.update(status='unknown',verified=False,error={'code':'PROCESS_INTERRUPTED','message':'上次操作中断，结果未知；未自动重试'})
                    await db.execute('UPDATE process_executions SET data_json=? WHERE cid=? AND operation_id=?',(encoded(value),cid,oid))
                await db.commit()
            except BaseException:
                await db.rollback();raise

    @staticmethod
    def _wait(value):
        if type(value) is not int or not 1<=value<=15:
            fail('PROCESS_WAIT','等待须为1～15秒')
        return value

    async def list(self,cid):
        """只列当前同用户普通、非关键且身份可读目标，不读取真实参数或窗口文本。"""
        async with self.store._lock:
            await self._alive(self.store._db(),cid)
        result=await self._invoke('list')
        values=[]
        for value in result['processes'][:50]:
            if size({'processes':values+[value],'truncated':True,'unavailable_reason':result.get('unavailable_reason')})>49152:
                break
            values.append(value)
        async with self.store._lock:
            await self._alive(self.store._db(),cid)
        return {'processes':values,'truncated':bool(result['truncated']) or len(result['processes'])>len(values),'unavailable_reason':result.get('unavailable_reason')}

    async def _remember(self,packet,policy=None):
        packet['revision']=digest(packet)
        if size(packet)>49152:
            fail('PROCESS_PREVIEW_LIMIT','完整进程审批包超过48KiB')
        async with self.store._lock:
            await self._alive(self.store._db(),packet['id'])
            if self._closed:
                fail('PROCESS_CLOSED','进程服务已关闭')
            while len(self._previews)>=20:
                self._previews.pop(next(iter(self._previews)))
            self._previews[packet['operation_id']]={'packet':copy.deepcopy(packet),'policy':policy}
        return packet

    async def preview_launch(self,cid,executable,args,cwd=None,wait_seconds=3):
        """准确程序路径和可选目录仅由原生选择提供；完整参数不是环境变量许可。"""
        self._wait(wait_seconds)
        async with self.store._lock:
            await self._alive(self.store._db(),cid)
        if self._closed:
            fail('PROCESS_CLOSED','进程服务已关闭')
        if not isinstance(args,list) or len(args)>16 or any(not isinstance(a,str) or len(a)>1000 or '\x00' in a for a in args) or size({'args':args})>8192 or SENSITIVE.search(encoded(args)):
            fail('PROCESS_ARGS','参数最多16项/8KiB，不能包含密钥或敏感字段')
        # 复用Computer角色与普通父目录策略；native还会独立核验.exe和令牌。
        policy,name=self.computer.selected_file('computer',executable)
        target=policy.resolve(name,'file')
        identity=await self._invoke('executable',str(target))
        cwd_policy=PathPolicy(cwd) if cwd is not None else PathPolicy(str(target.parent))
        launch={**identity,'args':copy.deepcopy(args),'cwd':str(cwd_policy.root)}
        packet={'id':cid,'operation_id':str(uuid4()),'action':'launch','target':None,'launch':launch,'wait_seconds':wait_seconds,'purpose':'启动准确普通权限程序','risk':'以当前普通账户权限启动，程序可产生文件或网络副作用；不会因Orvia关闭自动终止'}
        return await self._remember(packet,cwd_policy)

    async def preview_action(self,cid,action,pid,create_time,creation_ticks,wait_seconds=3):
        """PID、创建时间及100ns原始身份均匹配；关闭和终止不能互相替代。"""
        self._wait(wait_seconds)
        async with self.store._lock:
            await self._alive(self.store._db(),cid)
        if self._closed:
            fail('PROCESS_CLOSED','进程服务已关闭')
        if action not in {'wait','close','terminate'} or type(pid) is not int or not 1<=pid<=4294967295 or type(create_time) not in (int,float) or not math.isfinite(create_time) or create_time<=0 or not isinstance(creation_ticks,str) or not creation_ticks.isascii() or not creation_ticks.isdigit() or not 1<=len(creation_ticks)<=20:
            fail('PROCESS_TARGET','动作或准确目标身份无效')
        target=await self._inspect_target(cid,pid,create_time,creation_ticks)
        descriptions={'wait':('等待准确进程退出','仅观察，不因等待超时关闭或终止'),'close':('温和关闭准确进程','可能丢失未保存内容；只发送WM_CLOSE，未退出不会自动强制终止'),'terminate':('强制终止准确进程','可能立即丢失未保存内容和产生不完整文件；不能通用撤销')}
        purpose,risk=descriptions[action]
        packet={'id':cid,'operation_id':str(uuid4()),'action':action,'target':target,'launch':None,'wait_seconds':wait_seconds,'purpose':purpose,'risk':risk}
        return await self._remember(packet)

    async def _inspect_target(self,cid,pid,create_time,creation_ticks):
        """重启后仅从本会话已核验启动事实重建Job归属，绝不恢复动作批准。"""
        try:
            return await self._invoke('inspect',pid,create_time,creation_ticks)
        except ToolError as exc:
            if exc.code not in {'PROCESS_JOB','PROCESS_KEY'}:
                raise
            # 只查询当前准确目标的一条原生launch事实；未知、取消、其它会话均不能登记。
            async with self.store._lock:
                db=self.store._db();await self._alive(db,cid)
                rows=await self._rows(db,"SELECT data_json FROM process_executions WHERE cid=? AND json_extract(data_json,'$.action')='launch' AND json_extract(data_json,'$.status')='still_running' AND json_type(data_json,'$.verified')='true' AND json_extract(data_json,'$.target.pid')=? AND json_extract(data_json,'$.target.create_time')=? AND json_extract(data_json,'$.target.creation_ticks')=? ORDER BY rowid DESC LIMIT 1",(cid,pid,create_time,creation_ticks))
            if not rows:
                raise
            identity=json.loads(rows[0][0])['target']
            await self._invoke('restore_launched',identity)
            async with self.store._lock:
                await self._alive(self.store._db(),cid)
            return await self._invoke('inspect',pid,create_time,creation_ticks)

    async def review(self,cid,operation_id):
        """返回同一完整审查包并现查身份，不静默更新SHA或创建新操作身份。"""
        async with self.store._lock:
            await self._alive(self.store._db(),cid)
            entry=self._previews.get(operation_id)
            if not entry or entry['packet']['id']!=cid or self._closed:
                fail('PROCESS_REVIEW','准确审批不存在或已消费')
            packet=copy.deepcopy(entry['packet'])
        if packet['action']=='launch':
            launch=packet['launch']
            identity=await self._invoke('executable',launch['executable'])
            if identity!={k:launch[k] for k in ('name','executable','sha256')}:
                fail('PROCESS_IDENTITY_CHANGED','准确程序身份或全文SHA256变化')
            entry['policy'].resolve('.','directory')
        else:
            target=packet['target']
            current=await self._inspect_target(cid,target['pid'],target['create_time'],target['creation_ticks'])
            if current!=target:
                fail('PROCESS_IDENTITY_CHANGED','准确进程身份变化，不能使用旧批准')
        async with self.store._lock:
            await self._alive(self.store._db(),cid)
            if self._previews.get(operation_id) is not entry:
                fail('PROCESS_REVIEW','审批已撤销或消费')
        return packet

    def _blank(self,packet):
        return {'id':packet['id'],'operation_id':packet['operation_id'],'revision':packet['revision'],'action':packet['action'],'status':'running','target':packet['target'],'exit_code':None,'started_at':utc(),'finished_at':None,'verified':False,'close_sent':False,'error':None}

    async def _save(self,value):
        async with self.store._lock:
            db=self.store._db()
            await db.execute('BEGIN IMMEDIATE')
            try:
                await self._alive(db,value['id'])
                if not await self._rows(db,'SELECT 1 FROM process_attempts WHERE cid=? AND operation_id=?',(value['id'],value['operation_id'])):
                    fail('PROCESS_ATTEMPT_LOST','操作账本已删除，拒绝迟到正文')
                await db.execute('UPDATE process_attempts SET state=? WHERE cid=? AND operation_id=?',(value['status'],value['id'],value['operation_id']))
                await db.execute('INSERT OR REPLACE INTO process_executions VALUES(?,?,?)',(value['id'],value['operation_id'],encoded(value)))
                await db.execute('DELETE FROM process_executions WHERE cid=? AND rowid NOT IN(SELECT rowid FROM process_executions WHERE cid=? ORDER BY rowid DESC LIMIT 32)',(value['id'],value['id']))
                await db.commit()
            except BaseException:
                await db.rollback();raise

    async def execute(self,cid,operation_id,revision):
        """先消费独立账本再操作；未知不重试、温和关闭未退不自动强制终止。"""
        async with self.store._lock:
            db=self.store._db()
            await self._alive(db,cid)
            if await self._rows(db,'SELECT 1 FROM process_attempts WHERE cid=? AND operation_id=?',(cid,operation_id)):
                fail('PROCESS_ALREADY_ATTEMPTED','准确操作已经尝试，不能重放旧批准')
        packet=await self.review(cid,operation_id)
        if packet['revision']!=revision:
            fail('PROCESS_REVIEW','批准版本不一致')
        value=self._blank(packet)
        async with self.store._lock:
            db=self.store._db()
            await db.execute('BEGIN IMMEDIATE')
            try:
                await self._alive(db,cid)
                if await self._rows(db,'SELECT 1 FROM process_attempts WHERE cid=? AND operation_id=?',(cid,operation_id)):
                    fail('PROCESS_ALREADY_ATTEMPTED','该操作已尝试，不能重放')
                if (await self._rows(db,'SELECT count(*) FROM process_attempts WHERE cid=?',(cid,)))[0][0]>=128:
                    fail('PROCESS_ATTEMPT_LIMIT','本会话操作尝试达到128次')
                await db.execute('INSERT INTO process_attempts VALUES(?,?,?,?)',(cid,operation_id,revision,'running'))
                await db.execute('INSERT INTO process_executions VALUES(?,?,?)',(cid,operation_id,encoded(value)))
                current=self._previews.get(operation_id)
                if self._closed or not current or current['packet']!=packet:
                    fail('PROCESS_REVIEW','审批已撤销或服务关闭，未发出原生动作')
                await db.commit()
            except BaseException:
                await db.rollback();raise
            self._previews.pop(operation_id,None)
            self._active[operation_id]=asyncio.current_task()
        late={}
        try:
            # 最后原生操作会使用同一核验HANDLE，service比对不替代native安全检查。
            if packet['action']=='launch':
                launch=packet['launch']
                result=await self._invoke('launch',launch['executable'],launch['args'],launch['cwd'],packet['wait_seconds'],sha256=launch['sha256'],late=late)
            else:
                result=await self._invoke(packet['action'],packet['target'],packet['wait_seconds'],late=late)
            value.update(status={'running':'still_running','exited':'exited','unknown':'unknown'}.get(result['state'],'unknown'),target=result['identity'],exit_code=result['exit_code'],close_sent=result['close_sent'])
            value['verified']=value['status'] in {'still_running','exited'}
            if not value['verified']:
                value['error']={'code':'PROCESS_UNKNOWN','message':'未完整核验操作结果；不会自动重试'}
        except asyncio.CancelledError:
            result=late.get('result')
            if result:
                value.update(target=result['identity'],close_sent=result['close_sent'])
            value.update(status='unknown',verified=False,finished_at=utc(),error={'code':'PROCESS_CANCELLED','message':'通信取消，操作结果未知；原生线程已收尾，不自动重试'})
            await asyncio.shield(self._save(value))
            raise
        except ToolError as exc:
            value.update(status='failed' if exc.code in SAFE_REFUSAL else 'unknown',verified=False,error={'code':exc.code,'message':'原生安全检查拒绝操作' if exc.code in SAFE_REFUSAL else '原生操作未完整核验，不自动重试'})
        except (OSError,ValueError,RuntimeError):
            value.update(status='unknown',verified=False,error={'code':'PROCESS_NATIVE','message':'原生操作未完整核验，不自动重试'})
        finally:
            self._active.pop(operation_id,None)
        value['finished_at']=utc()
        await self._save(value)
        return value

    async def status(self,cid,operation_id):
        """只读本会话实际操作事实；历史数据不成为后续授权。"""
        async with self.store._lock:
            db=self.store._db();await self._alive(db,cid)
            rows=await self._rows(db,'SELECT data_json FROM process_executions WHERE cid=? AND operation_id=?',(cid,operation_id))
        if not rows:
            fail('PROCESS_EXECUTION','操作事实不存在或已超出正文保留预算')
        return json.loads(rows[0][0])

    async def history(self,cid):
        """最近十条/48KiB正文；独立尝试账本不随历史展示淘汰。"""
        async with self.store._lock:
            db=self.store._db();await self._alive(db,cid)
            rows=await self._rows(db,'SELECT data_json FROM process_executions WHERE cid=? ORDER BY rowid DESC LIMIT 11',(cid,))
        values=[]
        for row in rows[:10]:
            value=json.loads(row[0])
            if size({'executions':values+[value],'truncated':True})>49152:
                break
            values.append(value)
        return {'executions':values,'truncated':len(rows)>len(values)}

    async def has_unresolved(self,cid):
        """运行中和未知阻止永久删除；已知仍运行不等于操作结果未知。"""
        async with self.store._lock:
            return bool(await self._rows(self.store._db(),"SELECT 1 FROM process_attempts WHERE cid=? AND state IN('running','unknown') LIMIT 1",(cid,)))

    def forget_previews(self,cid):
        """撤销内存审批，已启动的普通程序不被自动终止。"""
        for oid,entry in list(self._previews.items()):
            if entry['packet']['id']==cid:
                del self._previews[oid]

    async def close(self):
        """只等待当前有限原生操作，不因Orvia关闭杀用户已启动目标。"""
        self._closed=True;self._previews.clear()
        tasks=[t for t in self._active.values() if t is not asyncio.current_task()]
        if tasks:
            await asyncio.shield(asyncio.gather(*tasks,return_exceptions=True))
        if self._pending:
            await asyncio.shield(asyncio.gather(*list(self._pending),return_exceptions=True))
