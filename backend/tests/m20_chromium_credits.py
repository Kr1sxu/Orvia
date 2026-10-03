"""只读锁定完整Chromium内置credits；独立合成profile、原生沙箱、所有外部路由拒绝。"""
import asyncio
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import runpy
from uuid import uuid4

import playwright
from playwright.async_api import async_playwright
from orvia_backend.automation.browser_runtime import prepare_chromium

ROOT=Path(__file__).resolve().parents[2]
BUILD=ROOT/'artifacts/test-results/M20/build'


def checksum(file):
    with file.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


async def main():
    sdk=Path(playwright.__file__).parent/'driver/package/browsers.json'
    item=next(item for item in json.loads(sdk.read_text())['browsers'] if item['name']=='chromium')
    source=Path(os.environ['LOCALAPPDATA'])/'ms-playwright'/('chromium-'+item['revision'])
    executable=source/'chrome-win64/chrome.exe'
    # 固定SDK缓存及其完整清单拒绝链接和额外解释器入口；不下载或更新依赖。
    inventory=runpy.run_path(str(ROOT/'packaging/build_backend.py'))['resource_files'](source)
    assert (source/'INSTALLATION_COMPLETE').is_file() and executable.is_file()
    relative='third-party-licenses/chromium-'+item['browserVersion']+'/credits.txt'
    output=BUILD/relative
    receipt=BUILD/'chromium-credits.json'
    identity={'playwright':importlib.metadata.version('playwright'),'revision':item['revision'],
              'browser_version':item['browserVersion'],'executable_sha256':checksum(executable),
              'source_files':inventory,'file':relative,'source':'chrome://credits/'}
    if output.exists() or receipt.exists():
        saved=json.loads(receipt.read_text(encoding='utf-8'))
        assert all(saved[key]==value for key,value in identity.items())
        assert output.stat().st_size==saved['bytes'] and checksum(output)==saved['sha256']
        print(json.dumps({'status':'existing original credits verified','bytes':saved['bytes'],'outbound_requests':0}))
        return
    profile=ROOT/'artifacts/test-results/M20'/('c-'+uuid4().hex[:8])
    profile.mkdir();blocked=[];context=None
    # 本机SDK flat CfT原目录的SxS已在M18验证不可启动；复用字节不变的私有版本布局。
    private=ROOT/'artifacts/test-results/M20'/('k-'+uuid4().hex[:8])
    runnable=prepare_chromium(str(executable),private)
    assert checksum(runnable)==identity['executable_sha256']
    async with async_playwright() as manager:
        try:
            context=await manager.chromium.launch_persistent_context(str(profile),executable_path=str(runnable),
                headless=False,chromium_sandbox=True,timeout=15_000,
                proxy={'server':'http://127.0.0.1:9'},permissions=[],accept_downloads=False,service_workers='block',
                args=['--disable-background-networking','--disable-component-update',
                      '--force-webrtc-ip-handling-policy=disable_non_proxied_udp',
                      '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost'])
            async def abort(route):
                blocked.append(route.request.url.split(':',1)[0]);await route.abort()
            await context.route('**/*',abort)
            await context.route_web_socket('**/*',lambda socket:socket.close())
            page=context.pages[0]
            await page.goto('chrome://credits/',wait_until='domcontentloaded',timeout=15_000)
            assert page.url=='chrome://credits/'
            # textContent包含默认折叠的原许可；innerText会漏掉display:none正文。
            text=await page.locator('body').text_content(timeout=15_000)
            data=text.encode('utf-8')
            assert 100_000<len(data)<=32*1024*1024 and 'Chromium' in text and 'Copyright' in text
            version=context.browser.version
            assert version==item['browserVersion']
            output.parent.mkdir(parents=True)
            with output.open('xb') as stream:stream.write(data)
            saved={**identity,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'profile':profile.name,
                   'headless':False,'chromium_sandbox':True,'runtime_layout':'M18 private-version-directory, original bytes',
                   'outbound_requests':0,'blocked_routes':len(blocked),
                   'real_models':0,'scope':'锁定完整Chromium内置原credits文本；不代表专业法律意见或业务验收'}
            receipt.write_text(json.dumps(saved,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({'status':'actual built-in credits saved','version':version,'bytes':len(data),
                              'blocked_routes':len(blocked),'outbound_requests':0}))
        finally:
            if context:await context.close()


if __name__=='__main__':asyncio.run(main())
