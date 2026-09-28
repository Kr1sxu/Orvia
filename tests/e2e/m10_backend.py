"""仅 E2E 启动器使用：真实 stdio/Application/SQLite，模型被确定性合成提案替换。"""
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend/src'))
import orvia_backend.chat as chat
from orvia_backend.configuration.client import Completion
from orvia_backend.configuration.client import ModelUnavailable
from orvia_backend.server import serve


class SyntheticModel:
    def __init__(self, registry):
        pass

    async def complete(self, profile, messages, **kwargs):
        assert profile.model == 'deepseek-flash'
        texts = [message['content'] for message in messages if message['role'] == 'user' and not message['content'].startswith('程序')]
        prompt = texts[-1] if texts else ''
        if '合成模型失败' in prompt:
            raise ModelUnavailable('HTTP_503')
        if '重命名' in prompt:
            proposal = {'kind':'plan', 'actions':[{'kind':'rename','source':'合成说明.txt','destination':'已整理.txt'}]}
        else:
            proposal = {'kind':'answer','text':'这是合成模型建议。文件动作只在明确审批后执行。'}
        await asyncio.sleep(.15)
        return Completion(None, ({'id':'synthetic-call','type':'function','function':{'name':'propose','arguments':json.dumps(proposal,ensure_ascii=False)}},), 'tool_calls', {})


chat.ModelClient = SyntheticModel
asyncio.run(serve(sys.stdin.buffer, sys.stdout.buffer))
