"""逐次冻结审批与执行账本；普通 Shell 不是 LPAC 沙箱。"""

import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
from uuid import UUID, uuid4

from ..computer.paths import PathPolicy, ToolError, sensitive, _reparse
from ..memory.service import SENSITIVE, encoded, digest, size, clip


class ShellError(ToolError):
    """稳定中文错误，不把脚本或私人路径拼接到异常。"""


def fail(code, message):
    raise ShellError(code, message)


def leaf(name):
    if not isinstance(name, str) or not name or len(name) > 100 or Path(name).name != name or Path(name).is_reserved() or any(c in name for c in ':\\/\x00') or name.endswith((' ', '.')) or name in {'.', '..'} or sensitive(name):
        fail('SHELL_OUTPUT_NAME', '产物名须为普通单文件名，不能包含路径')
    return name


class ShellService:
    """只供可信主进程在准确原生批准后执行；renderer 文本不授予权限。"""

    def __init__(self, store, chat, computer, runner=None):
        self.store, self.chat, self.computer = store, chat, computer
        self.root = store.path.parent / 'shell'
        self.runner = runner
        self._previews, self._exports, self._active, self._tasks = {}, {}, {}, {}
        self._closed = False

    async def _rows(self, db, sql, args=()):
        async with db.execute(sql, args) as cursor:
            return await cursor.fetchall()

    async def _alive(self, db, cid):
        if not await self._rows(db, 'SELECT 1 FROM chat_conversations WHERE id=? AND id NOT IN(SELECT id FROM chat_deletions)', (cid,)):
            fail('SHELL_CONVERSATION', '所属会话不存在或正在删除')

    async def open(self):
        """启动只恢复未知事实，不启动解释器或重放脚本。"""
        if self._active:
            fail('SHELL_RUNNING','运行中不能执行启动恢复')
        self._previews.clear();self._exports.clear()
        self.root.mkdir(parents=True, exist_ok=True)
        PathPolicy(str(self.root))
        async with self.store._lock:
            db = self.store._db()
            await db.execute('CREATE TABLE IF NOT EXISTS shell_attempts(cid TEXT NOT NULL,run_id TEXT NOT NULL,revision TEXT NOT NULL,state TEXT NOT NULL,PRIMARY KEY(cid,run_id))')
            await db.execute('CREATE TABLE IF NOT EXISTS shell_executions(cid TEXT NOT NULL,run_id TEXT NOT NULL,data_json TEXT NOT NULL CHECK(json_valid(data_json)),PRIMARY KEY(cid,run_id))')
            await db.execute('BEGIN IMMEDIATE')
            try:
                interrupted=await self._rows(db, "SELECT e.cid,e.run_id,e.data_json FROM shell_executions e JOIN shell_attempts a ON a.cid=e.cid AND a.run_id=e.run_id WHERE a.state='running'")
                await db.execute("UPDATE shell_attempts SET state='unknown' WHERE state='running'")
                for cid, rid, body in interrupted:
                    value = json.loads(body)
                    value.update(status='unknown', children_reaped=False, outputs=[], error={'code':'SHELL_INTERRUPTED', 'message':'上次执行中断，结果未知；未自动重跑'})
                    value['verification'] = {'status':'unknown', 'details':['执行中断，无法核验']}
                    await db.execute('UPDATE shell_executions SET data_json=? WHERE cid=? AND run_id=?', (encoded(value), cid, rid))
                await db.commit()
            except BaseException:
                await db.rollback()
                raise
            attempted={(row[0],row[1]) for row in await self._rows(db,'SELECT cid,run_id FROM shell_attempts')}
        # 跨重启审批失效；只清无尝试账本的规范UUID私有准备目录。
        # 账本独立保留，正文淘汰不能让已执行目录被当作未批准缓存删除。
        for conversation in self.root.iterdir():
            if not self._canonical_uuid(conversation.name):
                continue
            PathPolicy(str(conversation))
            for directory in conversation.iterdir():
                if self._canonical_uuid(directory.name) and (conversation.name,directory.name) not in attempted:
                    self._remove_directory(directory)

    async def detect(self):
        """只检测已安装解释器；缺失不安装，也不静默替换。"""
        if self.runner is None:
            from . import runtime
            return await runtime.detect()
        return await self.runner.detect()

    def _directory(self, cid, rid):
        try:
            if str(UUID(cid)) != cid or str(UUID(rid)) != rid:
                raise ValueError()
        except (ValueError, TypeError):
            fail('SHELL_ID', '会话或执行身份无效')
        PathPolicy(str(self.root))
        return self.root / cid / rid

    @staticmethod
    def _canonical_uuid(value):
        try:
            return str(UUID(value))==value
        except (ValueError, TypeError):
            return False

    def _input(self, path):
        policy, name = self.computer.selected_file('computer', path)
        target = policy.resolve(name, 'file')
        with target.open('rb') as stream:
            before = policy.validate_open_file(stream.fileno(), target)
            if before.st_nlink != 1 or before.st_size > 10 * 1024 * 1024:
                fail('SHELL_INPUT_LIMIT', '输入须为独立普通文件，单项最多10MiB')
            data = stream.read(10 * 1024 * 1024 + 1)
            after = policy.validate_open_file(stream.fileno(), target)
            policy.resolve(name, 'file')
            if len(data) > 10 * 1024 * 1024 or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                fail('SHELL_INPUT_CHANGED', '读取期间输入变化，请重新选择')
        return {'name':leaf(name), 'path':str(target), 'bytes':len(data), 'sha256':hashlib.sha256(data).hexdigest()}, data

    async def preview(self, cid, interpreter_id, script, timeout_seconds=20, expected_stdout=None, output_names=None, cwd=None, inputs=None):
        """冻结完整脚本、解释器版本、原生目录/输入和核验条件；此步零执行。"""
        if self._closed:
            fail('SHELL_CLOSED', 'Shell 服务已关闭')
        if not isinstance(script, str) or not script.strip() or '\x00' in script or len(script.encode('utf-8')) > 16384 or SENSITIVE.search(script):
            fail('SHELL_SCRIPT', '脚本须为最多16KiB的无密钥文本')
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 60:
            fail('SHELL_TIMEOUT', '时间预算须为1～60秒')
        if expected_stdout is not None and (not isinstance(expected_stdout, str) or not 1 <= len(expected_stdout) <= 1000 or '\x00' in expected_stdout or SENSITIVE.search(expected_stdout)):
            fail('SHELL_CHECK', '输出核验须为1～1000字符的无密钥文本')
        output_names = [] if output_names is None else output_names
        inputs = [] if inputs is None else inputs
        if not isinstance(output_names, list) or len(output_names) > 10 or len(set(n.casefold() for n in output_names if isinstance(n, str))) != len(output_names):
            fail('SHELL_OUTPUT_LIMIT', '产物最多10个不同文件名')
        names = [leaf(n) for n in output_names]
        if not isinstance(inputs, list) or len(inputs) > 3:
            fail('SHELL_INPUT_LIMIT', '显式输入最多3个')
        identities = (await self.detect())['interpreters']
        interpreter = next((item for item in identities if item['id'] == interpreter_id), None)
        if not interpreter or not interpreter['available']:
            fail('SHELL_UNAVAILABLE', '选择的解释器当前不可用，不会静默切换')
        infos = [self._input(p)[0] for p in inputs]
        if len({i['name'].casefold() for i in infos}) != len(infos) or sum(i['bytes'] for i in infos) > 30 * 1024 * 1024:
            fail('SHELL_INPUT_LIMIT', '输入同名或总量超过30MiB')
        rid = str(uuid4())
        directory = self._directory(cid, rid)
        async with self.store._lock:
            await self._alive(self.store._db(), cid)
        directory.mkdir(parents=True)
        for name in ('work', 'inputs', 'output'):
            (directory / name).mkdir()
        try:
            policy = PathPolicy(cwd) if cwd is not None else PathPolicy(str(directory / 'work'))
        except (ToolError, OSError):
            self._remove_directory(directory)
            raise
        value = {'id':cid, 'run_id':rid, 'interpreter':interpreter, 'script':script, 'cwd':str(policy.root), 'inputs':infos, 'output_names':names, 'timeout_seconds':timeout_seconds, 'expected_stdout':expected_stdout, 'budgets':{'script_bytes':16384,'stdout_bytes':16384,'stderr_bytes':16384,'file_bytes':1048576,'total_file_bytes':2097152}, 'purpose':'执行普通账户 Shell 脚本'}
        value['revision'] = digest(value)
        if size(value) > 48 * 1024:
            self._remove_directory(directory)
            fail('SHELL_PREVIEW_LIMIT', '完整审批预览超过48KiB')
        try:
            async with self.store._lock:
                await self._alive(self.store._db(), cid)
                while len(self._previews) >= 20:
                    old = next(iter(self._previews))
                    item = self._previews.pop(old)
                    self._remove_directory(self._directory(item['value']['id'], old))
                self._previews[rid] = {'value':copy.deepcopy(value), 'cwd_policy':policy}
        except (ToolError, OSError, asyncio.CancelledError):
            self._remove_directory(directory)
            raise
        return value

    def _remove_directory(self, directory):
        """仅删除已核验私有树；预检整树无重解析点，绝不跟随用户链接。"""
        if not directory.exists():
            return
        policy=PathPolicy(str(directory))
        root=PathPolicy(str(self.root)).root
        if policy.root==root or not policy.root.is_relative_to(root):
            fail('SHELL_PURGE_SCOPE','清理目标必须严格位于应用私有Shell根内')
        for current, dirs, files in os.walk(directory, followlinks=False):
            for name in dirs + files:
                if _reparse(Path(current) / name):
                    fail('SHELL_PURGE_LINK', '私有任务含重解析路径，不能安全清理')
        shutil.rmtree(directory)

    def _blank(self, packet):
        return {'id':packet['id'], 'run_id':packet['run_id'], 'revision':packet['revision'], 'interpreter_id':packet['interpreter']['id'], 'status':'running', 'exit_code':None, 'stdout':'', 'stderr':'', 'stdout_truncated':False, 'stderr_truncated':False, 'children_reaped':False, 'started_at':None, 'finished_at':None, 'verification':{'status':'unknown','details':['执行尚未结束']}, 'outputs':[], 'error':None}

    async def review(self, cid, run_id):
        """原生执行确认前读同一审批包；不生成新身份或暗中更新批准内容。"""
        async with self.store._lock:
            await self._alive(self.store._db(), cid)
            entry=self._previews.get(run_id)
            if not entry or entry['value']['id']!=cid:
                fail('SHELL_REVIEW','准确审批不存在或已消费')
            packet=copy.deepcopy(entry['value'])
        current=next((i for i in (await self.detect())['interpreters'] if i['id']==packet['interpreter']['id']),None)
        if current!=packet['interpreter']:
            fail('SHELL_IDENTITY_CHANGED','解释器身份或版本变化，请重新审批')
        entry['cwd_policy'].resolve('.', 'directory')
        if any(self._input(i['path'])[0]!=i for i in packet['inputs']):
            fail('SHELL_INPUT_CHANGED','输入版本变化，请重新审批')
        async with self.store._lock:
            await self._alive(self.store._db(),cid)
            if self._previews.get(run_id) is not entry:
                fail('SHELL_REVIEW','审批已撤销或消费')
        return packet

    async def _save(self, value):
        async with self.store._lock:
            db = self.store._db()
            await db.execute('BEGIN IMMEDIATE')
            try:
                await self._alive(db, value['id'])
                await db.execute('UPDATE shell_attempts SET state=? WHERE cid=? AND run_id=?', (value['status'], value['id'], value['run_id']))
                # 删除墓碑或已删除账本不能因迟到结果再创建正文。
                rows = await self._rows(db, 'SELECT 1 FROM shell_attempts WHERE cid=? AND run_id=?', (value['id'], value['run_id']))
                if not rows:
                    fail('SHELL_ATTEMPT_LOST', '执行事实已删除，不接受迟到正文')
                await db.execute('INSERT OR REPLACE INTO shell_executions VALUES(?,?,?)', (value['id'],value['run_id'],encoded(value)))
                await db.execute('DELETE FROM shell_executions WHERE cid=? AND rowid NOT IN(SELECT rowid FROM shell_executions WHERE cid=? ORDER BY rowid DESC LIMIT 32)', (value['id'],value['id']))
                await db.commit()
            except BaseException:
                await db.rollback()
                raise

    def _outputs(self, directory, names):
        policy = PathPolicy(str(directory / 'output'))
        infos, total = [], 0
        for name in names:
            path = policy.resolve(name, 'file')
            with path.open('rb') as stream:
                before = policy.validate_open_file(stream.fileno(), path)
                if before.st_nlink != 1 or before.st_size > 1048576:
                    fail('SHELL_OUTPUT_LIMIT', '产物不是独立普通文件或超过1MiB')
                data = stream.read(1048577)
                after = policy.validate_open_file(stream.fileno(), path)
                policy.resolve(name, 'file')
                if len(data) > 1048576 or (before.st_size,before.st_mtime_ns) != (after.st_size,after.st_mtime_ns):
                    fail('SHELL_OUTPUT_CHANGED', '核验时产物变化')
            total += len(data)
            if total > 2097152:
                fail('SHELL_OUTPUT_LIMIT', '产物合计超过2MiB')
            infos.append({'name':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
        return infos

    async def execute(self, cid, run_id, revision):
        """一次性消费批准后启动；退出零仅表示进程退出，不表示业务完成。"""
        async with self.store._lock:
            db = self.store._db()
            await self._alive(db, cid)
            if await self._rows(db, 'SELECT 1 FROM shell_attempts WHERE cid=? AND run_id=?', (cid,run_id)):
                fail('SHELL_ALREADY_ATTEMPTED', '该执行已尝试，不能重放旧批准')
        review = self._previews.get(run_id)
        if not review or review['value']['id'] != cid or review['value']['revision'] != revision or self._closed:
            fail('SHELL_REVIEW', '准确审批不存在、已变更或已消费')
        packet = copy.deepcopy(review['value'])
        current = next((i for i in (await self.detect())['interpreters'] if i['id'] == packet['interpreter']['id']), None)
        if current != packet['interpreter']:
            fail('SHELL_IDENTITY_CHANGED', '解释器身份或版本已变化，请重新审批')
        review['cwd_policy'].resolve('.', 'directory')
        copies = []
        for original in packet['inputs']:
            info, data = self._input(original['path'])
            if info != original:
                fail('SHELL_INPUT_CHANGED', '输入全文版本变化，请重新审批')
            copies.append((info['name'], data))
        directory = self._directory(cid, run_id)
        PathPolicy(str(directory))
        # 在启动任何进程前持久化 running；独立尝试不会因历史正文淘汰失效。
        value = self._blank(packet)
        async with self.store._lock:
            db = self.store._db()
            await db.execute('BEGIN IMMEDIATE')
            try:
                await self._alive(db, cid)
                if await self._rows(db,'SELECT 1 FROM shell_attempts WHERE cid=? AND run_id=?',(cid,run_id)):
                    fail('SHELL_ALREADY_ATTEMPTED', '该执行已尝试，不能重放')
                if (await self._rows(db,'SELECT count(*) FROM shell_attempts WHERE cid=?',(cid,)))[0][0] >= 128:
                    fail('SHELL_ATTEMPT_LIMIT','本会话尝试达到128次，不再启动')
                await db.execute('INSERT INTO shell_attempts VALUES(?,?,?,?)',(cid,run_id,revision,'running'))
                await db.execute('INSERT INTO shell_executions VALUES(?,?,?)',(cid,run_id,encoded(value)))
                await db.commit()
            except BaseException:
                await db.rollback()
                raise
            self._previews.pop(run_id, None)
            event = asyncio.Event()
            self._active[run_id] = {'cid':cid,'event':event}
            self._tasks[run_id] = asyncio.current_task()
        try:
            for name, data in copies:
                path = PathPolicy(str(directory / 'inputs')).new_file(name)
                with path.open('xb') as stream:
                    stream.write(data)
            suffix = '.ps1' if packet['interpreter']['id'] in {'powershell','windows_powershell'} else '.sh'
            script_path = directory / ('script' + suffix)
            script_path.write_text(packet['script'], encoding='utf-8-sig' if suffix == '.ps1' else 'utf-8')
            async with self.store._lock:
                await self._alive(self.store._db(), cid)
            review['cwd_policy'].resolve('.', 'directory')
            if self.runner is None:
                from . import runtime
                runner = runtime
            else:
                runner = self.runner
            result = await runner.run(packet['interpreter'],script_path,packet['cwd'],packet['timeout_seconds'],event,directory/'output',input_root=directory/'inputs')
            value.update(status={'completed':'exited','failed':'failed','timeout':'timed_out','cancelled':'cancelled','unavailable':'failed'}.get(result['state'],'unknown'), exit_code=result['exit_code'], stdout=clip(result['stdout'],16384), stderr=clip(result['stderr'],16384), stdout_truncated=result['stdout_truncated'] or len(result['stdout'].encode('utf-8'))>16384, stderr_truncated=result['stderr_truncated'] or len(result['stderr'].encode('utf-8'))>16384, children_reaped=result['children_reaped'], started_at=result['started_at'], finished_at=result['finished_at'])
            if not value['children_reaped']:
                value['status'] = 'unknown'
            safe = value['status']=='exited' and value['exit_code']==0 and not value['stdout_truncated'] and not value['stderr_truncated']
            checks, passed = [], True
            if packet['expected_stdout'] is not None:
                match = packet['expected_stdout'] in value['stdout']
                checks.append('stdout包含批准文本' if match else 'stdout未包含批准文本')
                passed &= match
            if packet['output_names'] and safe:
                try:
                    value['outputs'] = self._outputs(directory, packet['output_names'])
                    checks.append('指定产物已核验大小与全文SHA256')
                except ToolError as exc:
                    checks.append('指定产物未通过核验')
                    passed = False
                    value['error'] = {'code':exc.code,'message':exc.message}
            requested = bool(packet['output_names']) or packet['expected_stdout'] is not None
            value['verification'] = {'status':('passed' if passed else 'failed') if safe and requested else ('not_requested' if safe else 'unknown'), 'details':checks or ['未声明业务核验条件' if safe else '超时、取消、失败、截断或回收未知，无法通过核验']}
            # JSON控制字符会膨胀，不能只按流的UTF8原文预算判断协议包大小。
            while size(value)>49152:
                field='stdout' if len(value['stdout'])>=len(value['stderr']) else 'stderr'
                value[field]=clip(value[field],max(0,len(value[field].encode('utf-8'))-1024))
                value[field+'_truncated']=True
                value['outputs']=[]
                value['verification']={'status':'unknown','details':['完整JSON输出超过预算，正文已截断']}
        except asyncio.CancelledError:
            event.set()
            value.update(status='unknown',error={'code':'SHELL_CANCELLED','message':'通信取消，结果未知；未重试'})
            value['verification']={'status':'unknown','details':['通信中断，无法核验']}
            await asyncio.shield(self._save(value))
            raise
        except (ToolError, OSError, ValueError, RuntimeError) as exc:
            value.update(status='unknown',error={'code':exc.code if isinstance(exc,ToolError) else 'SHELL_RUNTIME','message':'执行结果未完整核验；未自动重试'})
            value['verification']={'status':'unknown','details':['未完整获得退出与回收证据']}
        finally:
            self._active.pop(run_id,None)
            self._tasks.pop(run_id,None)
        await self._save(value)
        return value

    async def status(self, cid, run_id):
        """仅返回本会话持久化事实，历史不授予执行或保存许可。"""
        async with self.store._lock:
            db=self.store._db()
            await self._alive(db,cid)
            rows=await self._rows(db,'SELECT data_json FROM shell_executions WHERE cid=? AND run_id=?',(cid,run_id))
        if not rows:
            fail('SHELL_EXECUTION','执行事实不存在或已超出历史保留预算')
        return json.loads(rows[0][0])

    async def cancel(self, cid, run_id):
        """取消只通知当前自有任务，不升级成其它进程操作或重试。"""
        value=await self.status(cid,run_id)
        active=self._active.get(run_id)
        if active and active['cid']==cid:
            active['event'].set()
        return value

    async def history(self, cid):
        """正文展示最多十条/48KiB，独立128次账本不被正文淘汰。"""
        async with self.store._lock:
            db=self.store._db()
            await self._alive(db,cid)
            rows=await self._rows(db,'SELECT data_json FROM shell_executions WHERE cid=? ORDER BY rowid DESC LIMIT 11',(cid,))
        values=[]
        for row in rows[:10]:
            value=json.loads(row[0])
            if size({'executions':values+[value],'truncated':True})>49152:
                break
            values.append(value)
        return {'executions':values,'truncated':len(rows)>len(values)}

    async def export_preview(self,cid,run_id,name):
        """独立产物回传准备；原执行审批不批准写入用户目录。"""
        value=await self.status(cid,run_id)
        name=leaf(name)
        if value['status']!='exited' or not value['children_reaped']:
            fail('SHELL_EXPORT_STATE','仅完整退出及回收的已核验产物可回传')
        original=next((o for o in value['outputs'] if o['name']==name),None)
        if original is None or self._outputs(self._directory(cid,run_id),[name])[0]!=original:
            fail('SHELL_OUTPUT_CHANGED','产物不在核验记录或已变化')
        packet={'id':cid,'run_id':run_id,**original,'purpose':'回传 Shell 产物为新文件'}
        packet['revision']=digest(packet)
        async with self.store._lock:
            await self._alive(self.store._db(),cid)
            while len(self._exports)>=20:
                self._exports.pop(next(iter(self._exports)))
            self._exports[(cid,run_id,name)]=copy.deepcopy(packet)
        return packet

    async def export(self,cid,run_id,name,path,revision):
        """可信原生保存框单文件授权；独占新建、fsync和全文读回拒覆盖。"""
        key=(cid,run_id,name)
        approved=self._exports.pop(key,None)
        if not approved or approved['revision']!=revision:
            fail('SHELL_EXPORT_REVIEW','准确产物批准不存在或已消费')
        fresh=await self.export_preview(cid,run_id,name)
        self._exports.pop(key,None)
        if fresh!=approved:
            fail('SHELL_OUTPUT_CHANGED','批准后产物变化')
        policy=PathPolicy(str(self._directory(cid,run_id)/'output'))
        source=policy.resolve(name,'file')
        with source.open('rb') as stream:
            before=policy.validate_open_file(stream.fileno(),source)
            data=stream.read(1048577)
            after=policy.validate_open_file(stream.fileno(),source)
            if before.st_nlink!=1 or (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns) or len(data)!=approved['bytes'] or hashlib.sha256(data).hexdigest()!=approved['sha256']:
                fail('SHELL_OUTPUT_CHANGED','回传读取时产物变化')
        target_policy,target_name=self.computer.selected_file('computer',path)
        target=target_policy.new_file(target_name)
        # 持锁复核墓碑直至写入完成，删除不能与保存穿插产生迟到写入。
        async with self.store._lock:
            await self._alive(self.store._db(),cid)
            try:
                with target.open('x+b') as stream:
                    target_policy.validate_open_file(stream.fileno(),target)
                    stream.write(data);stream.flush();os.fsync(stream.fileno())
                    target_policy.resolve(target_name,'file')
                    target_policy.validate_open_file(stream.fileno(),target)
                    stream.seek(0)
                    if stream.read(len(data)+1)!=data:
                        fail('SHELL_EXPORT_VERIFY','回传读回未通过，请人工核对新文件')
            except FileExistsError:
                fail('EXPORT_EXISTS','目标已存在，请重新选择新文件名')
        return {'filename':target_name,'bytes':len(data),'sha256':approved['sha256'],'verified':True}

    async def has_unresolved(self,cid):
        """运行中和未知事实阻止永久删除，进程回收不证明业务副作用解决。"""
        async with self.store._lock:
            return bool(await self._rows(self.store._db(),"SELECT 1 FROM shell_attempts WHERE cid=? AND state IN('running','unknown') LIMIT 1",(cid,)))

    def forget_previews(self,cid):
        """撤销会话审批缓存；不将撤销缓存误作已运行任务结束。"""
        for rid,review in list(self._previews.items()):
            if review['value']['id']==cid:
                del self._previews[rid]
        for key in list(self._exports):
            if key[0]==cid:
                del self._exports[key]

    async def purge_files(self,cid):
        """永久删除仅清应用私有会话树；用户目录、输入原件、导出文件保留。"""
        if await self.has_unresolved(cid):
            fail('SHELL_DELETE_BLOCKED','运行中或结果未知的 Shell 阻止删除')
        self.forget_previews(cid)
        # UUID验证后只构造固定私有根内一级会话目录，不使用用户cwd路径。
        directory=self._directory(cid,str(uuid4())).parent
        self._remove_directory(directory)

    async def close(self):
        """关闭通知全部自有任务取消并等待实际回收，不启动新任务。"""
        self._closed=True
        for active in self._active.values():
            active['event'].set()
        tasks=[t for t in self._tasks.values() if t is not asyncio.current_task()]
        if tasks:
            await asyncio.gather(*tasks,return_exceptions=True)
        self._previews.clear();self._exports.clear()
