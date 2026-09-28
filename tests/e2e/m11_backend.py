"""M11 合成模型：可控等待与失败，真实 stdio/SQLite，不读取凭据或联网。"""
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend/src'))
import orvia_backend.chat as chat
from orvia_backend.configuration.client import Completion, ModelUnavailable
from orvia_backend.server import serve


class SyntheticModel:
    def __init__(self, registry):
        pass

    async def complete(self, profile, messages, **kwargs):
        assert profile.model == 'deepseek-flash'
        texts = [m['content'] for m in messages if m['role'] == 'user' and not m['content'].startswith('程序')]
        prompt = texts[-1] if texts else ''
        if '慢速' in prompt:
            await asyncio.sleep(30)
        if '失败' in prompt:
            raise ModelUnavailable('HTTP_503 synthetic-private-provider-body')
        proposal = {'kind': 'answer', 'text': '合成回复；没有执行文件动作。'}
        if '重命名' in prompt:
            proposal = {'kind': 'plan', 'actions': [{'kind': 'rename', 'source': 'sample.txt', 'destination': 'renamed.txt'}]}
        return Completion(None, ({'id': 'synthetic', 'type': 'function', 'function': {'name': 'propose', 'arguments': json.dumps(proposal)}},), 'tool_calls', {})


chat.ModelClient = SyntheticModel
asyncio.run(serve(sys.stdin.buffer, sys.stdout.buffer))
