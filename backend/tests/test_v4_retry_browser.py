"""真实本机合成HTTP/TCP验证；公网域名到fixture的映射仅测试transport注入。"""
import asyncio
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import socket
from time import monotonic
from uuid import uuid4

import httpx
import pytest

from orvia_backend.browser.network import SafeHTTP
from orvia_backend.browser.service import BrowserService
from orvia_backend.retry import RetryService
from pydantic import SecretStr
import orvia_backend.browser.service as browser_module


@contextmanager
def fixture(replies):
    calls=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            calls.append(self.path)
            status,headers,body=replies[min(len(calls)-1,len(replies)-1)]
            if status=='disconnect':self.connection.close();return
            self.send_response(status)
            for key,value in headers.items():self.send_header(key,value)
            self.send_header('Content-Length',str(len(body)));self.end_headers()
            try:self.wfile.write(body)
            except (BrokenPipeError,ConnectionResetError):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield server.server_port,calls
    finally:server.shutdown();server.server_close();thread.join(1)


class LocalFixtureTransport(httpx.AsyncBaseTransport):
    """保留真实HTTP栈，仅把已验证合成域名流量接到本地fixture；无产品策略改动。"""
    def __init__(self,port):self.port=port;self.real=httpx.AsyncHTTPTransport()
    async def handle_async_request(self,request):
        assert request.method=='GET' and request.headers['host']=='example.com'
        assert 'authorization' not in request.headers and 'cookie' not in request.headers
        target=request.url.copy_with(host='127.0.0.1',port=self.port)
        response=await self.real.handle_async_request(httpx.Request(request.method,target,headers=request.headers,stream=request.stream,extensions=request.extensions))
        return response
    async def aclose(self):await self.real.aclose()


async def public_resolver(host,port):return ['93.184.216.34']


def browser_for(port):
    retry=RetryService();cid=str(uuid4())
    return BrowserService(network=SafeHTTP(transport=LocalFixtureTransport(port),resolver=public_resolver),retry=retry),retry,cid


@pytest.mark.parametrize('status',[429,503])
def test_actual_http_transient_then_read_same_business(status):
    with fixture([(status,{'retry-after':'0'},b'transient'),(200,{'content-type':'text/plain'},'合成成功'.encode())]) as (port,calls):
        async def run():
            browser,retry,cid=browser_for(port);bid=str(uuid4())
            result=await browser.read('http://example.com/a',mode='http',cid=cid,business_id=bid)
            assert result['error'] is None and result['content']=='合成成功' and calls==['/a','/a']
            record=(await retry.history(cid))['runs'][0]
            assert record['business_id']==bid and [a['sequence'] for a in record['attempts']]==[1,2]
            assert record['attempts'][0]['reason']==f'http_{status}'
        asyncio.run(run())


@pytest.mark.parametrize('status',[401,403,404,500])
def test_actual_http_auth_permission_unsupported_not_retry(status):
    with fixture([(status,{},b'denied')]) as (port,calls):
        async def run():
            browser,retry,cid=browser_for(port)
            result=await browser.read('http://example.com/a',mode='http',cid=cid)
            assert result['error']['code']=='HTTP_FAILED' and len(calls)==1
            assert len((await retry.history(cid))['runs'][0]['attempts'])==1
        asyncio.run(run())


def test_actual_http_disconnect_after_request_unknown_not_retry():
    with fixture([('disconnect',{},b'')]) as (port,calls):
        async def run():
            browser,retry,cid=browser_for(port)
            result=await browser.read('http://example.com/a',mode='http',cid=cid)
            assert result['error']['code']=='READ_FAILED' and len(calls)==1
            assert (await retry.history(cid))['runs'][0]['attempts'][0]['reason']=='not_retryable'
            assert (await retry.history(cid))['runs'][0]['state']=='unknown'
        asyncio.run(run())


def test_actual_http_retryafter_too_long_stops_without_wait():
    with fixture([(429,{'retry-after':'30'},b'transient')]) as (port,calls):
        async def run():
            browser,retry,cid=browser_for(port)
            result=await browser.read('http://example.com/a',mode='http',cid=cid)
            assert result['error']['code']=='HTTP_FAILED' and len(calls)==1
            assert (await retry.history(cid))['runs'][0]['attempts'][0]['reason']=='budget_exhausted'
        asyncio.run(run())


def test_actual_http_redirect_and_retry_share_four_wire_requests():
    with fixture([(301,{'location':'/b'},b''),(302,{'location':'/c'},b''),(503,{},b'transient')]) as (port,calls):
        async def run():
            browser,retry,cid=browser_for(port)
            result=await browser.read('http://example.com/a',mode='http',cid=cid)
            assert result['error']['code']=='REDIRECT_LIMIT' and calls==['/a','/b','/c','/c']
            assert len((await retry.history(cid))['runs'][0]['attempts'])==3
        asyncio.run(run())


def test_actual_http_backoff_cancel_no_second_request():
    with fixture([(503,{},b'transient')]) as (port,calls):
        async def run():
            browser,retry,cid=browser_for(port);event=asyncio.Event()
            task=asyncio.create_task(browser.read('http://example.com/a',mode='http',cid=cid,cancel_event=event))
            while not calls:await asyncio.sleep(.005)
            await asyncio.sleep(.03);event.set()
            with pytest.raises(asyncio.CancelledError):await task
            assert len(calls)==1 and (await retry.history(cid))['runs'][0]['state']=='cancelled'
        asyncio.run(run())


def test_dynamic_budget_path_has_no_retry_or_receipt():
    with fixture([(503,{},b'transient')]) as (port,calls):
        async def run():
            browser,retry,cid=browser_for(port)
            with retry.activate(cid,str(uuid4())):
                with pytest.raises(Exception):await browser._fetch_page('http://example.com/a',budget={'requests':30,'bytes':2000000})
            assert len(calls)==1 and (await retry.history(cid))['runs']==[]
        asyncio.run(run())


def test_actual_tcp_connect_before_send_retry_then_http_success():
    with fixture([(200,{'content-type':'text/plain'},b'synthetic')]) as (port,calls):
        blocker=socket.socket();blocker.bind(('127.0.0.1',0));closed_port=blocker.getsockname()[1]
        class FirstRefused(LocalFixtureTransport):
            def __init__(self):super().__init__(port);self.count=0
            async def handle_async_request(self,request):
                self.count+=1
                self.port=closed_port if self.count==1 else port
                return await super().handle_async_request(request)
        async def run():
            retry=RetryService();cid=str(uuid4());transport=FirstRefused()
            browser=BrowserService(network=SafeHTTP(transport=transport,resolver=public_resolver),retry=retry)
            result=await browser.read('http://example.com/a',mode='http',cid=cid)
            assert result['error'] is None and transport.count==2 and len(calls)==1
            assert (await retry.history(cid))['runs'][0]['attempts'][0]['reason']=='connect_before_send'
        try:asyncio.run(run())
        finally:blocker.close()


def test_actual_http_three_transient_attempts_no_fourth():
    with fixture([(503,{},b'transient')]) as (port,calls):
        async def run():
            browser,retry,cid=browser_for(port)
            result=await browser.read('http://example.com/a',mode='http',cid=cid)
            assert result['error']['code']=='HTTP_FAILED' and len(calls)==3
            assert len((await retry.history(cid))['runs'][0]['attempts'])==3
        asyncio.run(run())


def test_actual_http_format_rejection_not_refetched():
    with fixture([(200,{'content-type':'application/octet-stream'},b'synthetic')]) as (port,calls):
        async def run():
            browser,retry,cid=browser_for(port)
            result=await browser.read('http://example.com/a',mode='http',cid=cid)
            assert result['error']['code']=='RESOURCE_BLOCKED' and len(calls)==1
            assert len((await retry.history(cid))['runs'][0]['attempts'])==1
        asyncio.run(run())


def test_tavily_paid_post_excluded_even_connect_error():
    async def run():
        calls=[]
        async def fail(request):calls.append(request.method);raise httpx.ConnectError('synthetic')
        retry=RetryService();cid=str(uuid4())
        network=SafeHTTP(transport=httpx.MockTransport(fail),resolver=public_resolver)
        browser=BrowserService(SecretStr('synthetic-test-only'),network=network,retry=retry)
        with retry.activate(cid,str(uuid4())):result=await browser.web_search('合成查询')
        assert result['error']['code']=='SEARCH_FAILED' and calls==['POST'] and (await retry.history(cid))['runs']==[]
    asyncio.run(run())


def test_html_extraction_elapsed_original_deadline_does_not_complete_read(monkeypatch):
    with fixture([(200,{'content-type':'text/html'},b'<html><body><article>synthetic source</article></body></html>')]) as (port,calls):
        clock={'offset':0}
        monkeypatch.setattr(browser_module,'monotonic',lambda:monotonic()+clock['offset'])
        def after_extraction(markup):clock['offset']=21;return '合成标题'
        monkeypatch.setattr(browser_module,'page_title',after_extraction)
        async def run():
            browser,retry,cid=browser_for(port)
            result=await browser.read('http://example.com/a',mode='http',cid=cid)
            assert result['error']['code']=='READ_FAILED' and len(calls)==1
            assert (await retry.history(cid))['runs'][0]['state']=='succeeded','仅HTTP返回，不意味着正文/全业务完成'
        asyncio.run(run())
