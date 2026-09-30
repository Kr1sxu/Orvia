"""真实可见Chromium探针：只用合成页面/网络，环境与产品私有管道相同。"""

import asyncio
import ctypes
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import sys

import httpx
import psutil
from playwright.async_api import BrowserType, Error as PlaywrightError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from orvia_backend.automation.browser import BrowserAdapter
from orvia_backend.automation.windows_isolation import _Native
from orvia_backend.browser.write_network import WriteNetwork
from orvia_backend.computer.paths import ToolError
from test_browser import dns, response
from test_m18_browser_engine import MARKUP, click, wait_pending, wait_result


def owned_chrome():
    return [child for child in psutil.Process().children(recursive=True) if child.name().casefold() == 'chrome.exe']


def visible_owned_windows():
    """只枚举自有Chrome的可见性；不读其他应用标题、正文或截图。"""
    pids = {child.pid for child in owned_chrome()}
    native = ctypes.WinDLL('user32', use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    native.IsWindowVisible.argtypes, native.IsWindowVisible.restype = [w.HWND], w.BOOL
    native.GetWindowThreadProcessId.argtypes, native.GetWindowThreadProcessId.restype = [w.HWND, ctypes.POINTER(w.DWORD)], w.DWORD
    native.EnumWindows.argtypes, native.EnumWindows.restype = [callback_type, w.LPARAM], w.BOOL
    found = []
    def check(hwnd, parameter):
        pid = w.DWORD()
        native.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and native.IsWindowVisible(hwnd):
            found.append(True)
        return True
    callback = callback_type(check)
    native.EnumWindows(callback, 0)
    return bool(found)


def renderer_tokens():
    """原生读回本探针renderer的非提升/低完整性，而不把launch选项当作OS证明。"""
    native = _Native()
    native.k.OpenProcess.argtypes, native.k.OpenProcess.restype = [w.DWORD, w.BOOL, w.DWORD], w.HANDLE
    facts = []
    for child in owned_chrome():
        arguments = child.cmdline()
        assert '--no-sandbox' not in arguments
        if '--type=renderer' not in arguments:
            continue
        process = native.k.OpenProcess(0x1000, False, child.pid)
        token = w.HANDLE()
        try:
            assert process and native.a.OpenProcessToken(process, 0x8, ctypes.byref(token))
            integrity = native.token_info(token, 25)
            sid = native.sid_string(ctypes.cast(integrity, ctypes.POINTER(w.LPVOID))[0])
            elevation = int.from_bytes(native.token_info(token, 20).raw[:4], 'little')
            assert sid in {'S-1-16-0', 'S-1-16-4096'} and elevation == 0
            facts.append({'integrity': sid, 'elevated': False})
        finally:
            if token: native.k.CloseHandle(token)
            if process: native.k.CloseHandle(process)
    assert facts, '没有读回自有renderer令牌'
    return facts


async def run(report):
    diagnostic = {'headless': False, 'clean_environment': set(os.environ) <= {'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP'}, 'phase': 'initial', 'chromium_sandbox': True}
    original = BrowserType.launch
    async def launch(self, *args, **kwargs):
        assert kwargs['headless'] is False and kwargs['chromium_sandbox'] is True
        assert kwargs['proxy'] == {'server': 'http://127.0.0.1:9'}
        assert Path(kwargs['executable_path']).is_relative_to(Path(os.environ['TEMP'])/'runtime')
        return await original(self, *args, **kwargs)
    BrowserType.launch = launch
    calls = []
    def handler(request):
        calls.append((request.method, request.url.path))
        return response(MARKUP if request.url.path == '/' else '合成业务完成:form', **{'content-type': 'text/html'})
    adapter = BrowserAdapter(WriteNetwork(transport=httpx.MockTransport(handler), resolver=dns), headless=False, runtime_root=Path(os.environ['TEMP'])/'runtime')
    identities = []
    try:
        opened = await adapter.open('visible', 'https://m18.example/', allowed_actions=['form'])
        diagnostic['phase'] = 'opened'
        sid = opened['session_id']
        diagnostic['visible_window'] = visible_owned_windows()
        assert diagnostic['visible_window'] and opened['controls']
        diagnostic['renderer_tokens'] = renderer_tokens()
        identities = [(child.pid, child.create_time()) for child in owned_chrome()]
        await adapter._sessions[sid].page.screenshot(path=str(report.parent/'visible-browser.png'))
        await click(adapter, 'visible', sid, '提交表单', 'form')
        pending = (await wait_pending(adapter, 'visible', sid))['pending_request']
        assert calls == [('GET', '/')]
        await adapter.approve_request('visible', sid, pending['request_id'], pending['revision'], True)
        await wait_result(adapter, 'visible', sid)
        verified = await adapter.verify_result('visible', sid, '合成业务完成:form')
        assert verified['verified'] and calls == [('GET', '/'), ('POST', '/form')]
        diagnostic.update(phase='verified', verified=True, requests=len(calls), writes=1)
    except ToolError as error:
        diagnostic['code'] = error.code
    except (PlaywrightError, OSError, AssertionError, TimeoutError) as error:
        diagnostic['code'] = type(error).__name__
    finally:
        await adapter.close_all()
        BrowserType.launch = original
        remaining = []
        for pid, created in identities:
            try:
                if psutil.Process(pid).create_time() == created: remaining.append(pid)
            except psutil.NoSuchProcess:
                pass
        diagnostic['owned_processes_reaped'] = not remaining
        report.write_text(json.dumps(diagnostic, ensure_ascii=False), encoding='utf-8')
    return 0 if diagnostic.get('verified') and diagnostic['owned_processes_reaped'] else 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(run(Path(sys.argv[1]))))
