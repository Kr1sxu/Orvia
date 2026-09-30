"""M18 Electron合成验收：真实LPAC/UIA/Chromium，仅模型、DNS/HTTP与原生确认用替身。"""
import asyncio
import json
import os
from pathlib import Path
import sys

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend/src"))
from orvia_backend.automation.service import AutomationService
from orvia_backend.automation.desktop import DesktopAdapter
from orvia_backend.automation.browser import BrowserAdapter
from orvia_backend.browser.write_network import WriteNetwork
from orvia_backend.configuration.client import Completion, ModelClient
from orvia_backend.server import serve


class Body(httpx.AsyncByteStream):
    def __init__(self, text): self.data = text.encode("utf-8")
    async def __aiter__(self): yield self.data


MARKUP = """<!doctype html><meta charset=utf-8><title>M18合成写操作</title>
<label>合成正文<input id=text></label><button id=send>提交合成消息</button><output id=result></output>
<script>document.getElementById('send').onclick=async()=>{const r=await fetch('/message',{
method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({text:document.getElementById('text').value})});
document.getElementById('result').textContent=await r.text();};</script>"""


def handler(request):
    if request.url.path == "/":
        return httpx.Response(200,headers={"content-type":"text/html"},stream=Body(MARKUP))
    # 只保存合成计数，绝不记录原始网络正文。
    counter=Path(os.environ["ORVIA_M18_COUNTER"])
    previous=int(counter.read_text()) if counter.exists() else 0
    counter.write_text(str(previous+1))
    assert request.method == "POST" and request.url.path == "/message"
    return httpx.Response(200,headers={"content-type":"text/plain"},stream=Body("合成消息完成:唯一回执"))


async def dns(host, port):
    assert host == "m18.example"
    return ["93.184.216.34"]


class FixtureDesktop(DesktopAdapter):
    async def _worker(self, payload, cancel_event=None):
        if payload["op"] == "windows": payload={**payload,"filter_pid":int(os.environ["ORVIA_M18_FIXTURE_PID"])}
        return await super()._worker(payload,cancel_event)


original_init=AutomationService.__init__
def synthetic_init(self, chat, **kwargs):
    original_init(self,chat,desktop=FixtureDesktop(staging_root=chat.store.path.parent/"automation/desktop-staging",timeout=12),
                  browser=BrowserAdapter(WriteNetwork(transport=httpx.MockTransport(handler),resolver=dns),headless=False,
                                         runtime_root=chat.store.path.parent/"automation/browser-runtime"))
AutomationService.__init__=synthetic_init


async def synthetic_complete(self, profile, messages, **kwargs):
    assert profile.role == "computer" and profile.model == "glm-5.3-flashx"
    assert profile.base_url == "https://open.bigmodel.cn/api/paas/v4" and kwargs["max_tokens"] == 4096
    return Completion(json.dumps({"source":"from pathlib import Path\nPath('output/model.txt').write_text('synthetic model draft',encoding='utf-8')"}),(),"stop",{})
ModelClient.complete=synthetic_complete
asyncio.run(serve(sys.stdin.buffer,sys.stdout.buffer))
