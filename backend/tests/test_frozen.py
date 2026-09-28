"""冻结后端验收：显式选择实际 EXE，清空开发路径，仅用临时合成资料。"""
import asyncio
import json
import os
from pathlib import Path
import subprocess
from uuid import uuid4

import pytest

EXE = os.environ.get('ORVIA_FROZEN_BACKEND')
pytestmark = pytest.mark.skipif(not EXE, reason='须显式选择冻结后端')


class Frozen:
    async def start(self, directory):
        self.directory = directory
        env = {k: os.environ[k] for k in ('SystemRoot', 'WINDIR', 'TEMP', 'TMP') if k in os.environ}
        # 不依赖开发 PATH 或缓存；进程仅有系统基本环境与打包资源。
        env['PATH'] = str(Path(os.environ['SystemRoot']) / 'System32')
        self.process = await asyncio.create_subprocess_exec(str(Path(EXE).resolve()), cwd=directory, env=env,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW)
        self.stderr = asyncio.create_task(self.process.stderr.read())
        assert (await self.call('hello'))['python'].startswith('3.12.')
        await self.call('initialize', {'data_directory': str(directory), 'credentials': {}})
        return self

    async def call(self, method, params=None):
        request={'v':1,'id':str(uuid4()),'method':method,'params':params or {}}
        self.process.stdin.write((json.dumps(request,ensure_ascii=False)+'\n').encode('utf-8'))
        await self.process.stdin.drain()
        line = await asyncio.wait_for(self.process.stdout.readline(), timeout=30)
        if not line:
            await self.process.wait()
            # 仅合成验收子进程，错误正文仍只进入忽略的本地报告。
            (self.directory/'frozen-stderr.txt').write_bytes(await self.stderr)
        assert line, '冻结进程未返回协议，见 frozen-stderr.txt'
        reply=json.loads(line)
        assert reply['ok'], reply.get('error')
        return reply['result']

    async def close(self):
        if self.process.returncode is None:
            self.process.stdin.close()
            try:
                await asyncio.wait_for(self.process.wait(), 5)
            except TimeoutError:
                self.process.kill()
                await self.process.wait()
                raise
        (self.directory/'frozen-stderr.txt').write_bytes(await self.stderr)
        assert self.process.returncode == 0


def test_frozen_fts_checkpoint_approval_and_restart(tmp_path):
    async def scenario():
        client = await Frozen().start(tmp_path)
        root=tmp_path/'合成 文件目录'; root.mkdir()
        (root/'草稿.txt').write_text('合成验收资料',encoding='utf-8')
        try:
            assert (await client.call('health'))['status']=='ok'
            mission=await client.call('missions.create', {'client_request_id':str(uuid4()),'title':'安装包合成验收'})
            mission_id=mission['id']
            await client.call('context.index', {'mission_id':mission_id,'source':'synthetic.md','text':'合成任务移动文件前必须审批。'})
            assert (await client.call('context.search',{'mission_id':mission_id,'query':'审批'}))['evidence']
            assert (await client.call('browser.search',{'mission_id':mission_id,'query':'合成搜索'}))['error']['code']=='SEARCH_UNAVAILABLE'
            plan=await client.call('mission.run',{'mission_id':mission_id,'goal':'合成整理','root':str(root),'thread_id':'frozen-thread','actions':[{'kind':'rename','source':'草稿.txt','destination':'完成.txt'}]})
            assert plan['phase']=='awaiting_approval' and (root/'草稿.txt').exists()
        finally:
            await client.close()
        client=await Frozen().start(tmp_path)
        try:
            assert (await client.call('missions.get',{'id':mission_id}))['title']=='安装包合成验收'
            completed=await client.call('mission.approve',{'thread_id':'frozen-thread'})
            assert completed['phase']=='completed' and (root/'完成.txt').exists()
            await client.call('computer.undo_latest',{'mission_id':mission_id})
            assert (root/'草稿.txt').exists() and not (root/'完成.txt').exists()
        finally:
            await client.close()
    asyncio.run(scenario())
