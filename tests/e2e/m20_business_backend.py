"""M20业务L3：仅合成模型/HTTPS响应/Temp定位；stdio、审批账本、文件与隔离真实。"""
import asyncio
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m20_backend as base
import httpx
from orvia_backend.automation.service import AutomationService
from orvia_backend.automation.browser import BrowserAdapter
from orvia_backend.automation.desktop import DesktopAdapter
from orvia_backend.browser.write_network import WriteNetwork
from orvia_backend.cleanup.service import CleanupService


original_content = base.content_for


def content_for(payload):
    """固定角色仍由真实ModelClient核对，仅返回有限合成建议，不批准或执行。"""
    system = payload['messages'][0]['content']
    if '意图理解器' in system:
        instruction = json.loads(payload['messages'][1]['content'])['instruction']
        if 'Python' in instruction and '生成' in instruction:
            return {'steps': [{'kind': 'script', 'kind_hint': 'model', 'query': instruction}]}
        if 'https://m20-write.example/' in instruction and '发送消息' in instruction:
            return {'steps': [{'kind': 'browser', 'url': 'https://m20-write.example/', 'query': instruction}]}
    if 'Main文件助手' in system:
        observed = any('程序只读观察' in message['content'] for message in payload['messages'])
        return {'kind': 'plan', 'actions': [{'kind': 'rename', 'source': 'alpha.txt', 'destination': 'beta.txt'}]} if observed else {
            'kind': 'inspect', 'tool': 'list_directory', 'arguments': {'path': '.', 'limit': 100}}
    if payload['model'] == 'glm-5.3-flashx':
        if '原型提案器' in system:
            return {'title': 'M20合成原型', 'pages': [
                {'id': 'home', 'title': '首页', 'body': '演示数据', 'buttons': [{'label': '详情', 'target': 'detail'}], 'form': None},
                {'id': 'detail', 'title': '详情页', 'body': '离线演示', 'buttons': [{'label': '返回', 'target': 'home'}],
                 'form': {'label': '姓名', 'success': '演示已提交'}},
            ]}
        if 'Python' in system:
            return {'source': "from pathlib import Path\nPath('output/model.txt').write_text('M20 synthetic model LPAC',encoding='utf-8')\nprint('synthetic model executed')"}
        return {'files': [{'path': 'App.tsx', 'content': 'export const App = () => <p>M20 new synthetic</p>;'}]}
    return original_content(payload)


base.content_for = content_for
original_cleanup = CleanupService.__init__


def cleanup_init(self, store, local_base=None):
    # 仅当前测试目录的同结构Local/Temp；生产定位逻辑不接受环境覆盖。
    original_cleanup(self, store, Path(os.environ['ORVIA_M20_BUSINESS_LOCAL']))


CleanupService.__init__ = cleanup_init

MARKUP = """<!doctype html><meta charset=utf-8><title>M20合成写操作</title>
<label>合成正文<input id=text></label><button id=send>提交合成消息</button><output id=result></output>
<script>document.getElementById('send').onclick=async()=>{const r=await fetch('/message',{
method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({text:document.getElementById('text').value})});
document.getElementById('result').textContent=await r.text();};</script>"""


def website(request):
    # 真WriteNetwork固定公共IP并保留Host/SNI，不能让mock要求客户端绕过该出口。
    assert request.url.host == '93.184.216.34' and request.headers['host'] == 'm20-write.example'
    if request.method == 'GET' and request.url.path == '/':
        return httpx.Response(200, headers={'content-type': 'text/html'}, stream=base.Body(MARKUP))
    if request.method == 'GET':
        return httpx.Response(404, headers={'content-type': 'text/plain'}, stream=base.Body('synthetic resource absent'))
    assert request.method == 'POST' and request.url.path == '/message'
    # 不保存正文或原始响应，仅证明另批之前外发数为0、之后为1。
    count = Path(os.environ['ORVIA_M20_BUSINESS_NETWORK_COUNT'])
    previous = int(count.read_text()) if count.exists() else 0
    count.write_text(str(previous + 1))
    return httpx.Response(200, headers={'content-type': 'text/plain'}, stream=base.Body('M20合成消息完成:唯一回执'))


async def dns(host, port):
    assert host == 'm20-write.example'
    return ['93.184.216.34']


original_automation = AutomationService.__init__


class FixtureDesktop(DesktopAdapter):
    async def _worker(self, payload, cancel_event=None):
        # 只缩小原生枚举到本测试新启动的自有窗口；后续观察/执行保留真实UIA工作器。
        if payload['op'] == 'windows' and os.getenv('ORVIA_M20_BUSINESS_FIXTURE_PID'):
            payload = {**payload, 'filter_pid': int(os.environ['ORVIA_M20_BUSINESS_FIXTURE_PID'])}
        return await super()._worker(payload, cancel_event)


def automation_init(self, chat, **kwargs):
    original_automation(self, chat, desktop=FixtureDesktop(staging_root=chat.store.path.parent / 'automation/desktop-staging', timeout=12), browser=BrowserAdapter(
        WriteNetwork(transport=httpx.MockTransport(website), resolver=dns), headless=False,
        runtime_root=chat.store.path.parent / 'automation/browser-runtime'))


AutomationService.__init__ = automation_init

if __name__ == '__main__':
    asyncio.run(base.serve(sys.stdin.buffer, sys.stdout.buffer))
