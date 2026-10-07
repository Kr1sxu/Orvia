"""只在测试中启动的TLS合成HTTPS服务，不访问外部网络或用户文件。"""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import ssl
import threading

class Fixture:
    def __init__(self,cert,key,mode='json'):
        self.mode=mode;self.messages=[];self.headers=[];owner=self
        class Handler(BaseHTTPRequestHandler):
            protocol_version='HTTP/1.1'
            def log_message(self,*args):pass
            def do_DELETE(self):
                owner.headers.append(dict(self.headers));self.send_response(405 if owner.mode=='close_refused' else 204);self.send_header('Content-Length','0');self.end_headers()
            def do_POST(self):
                length=int(self.headers.get('Content-Length','0'));value=json.loads(self.rfile.read(length));owner.messages.append(value);owner.headers.append(dict(self.headers))
                if owner.mode=='redirect':
                    self.send_response(302);self.send_header('Location','https://example.invalid/escape');self.send_header('Content-Length','0');self.end_headers();return
                if owner.mode in {'auth','expired'}:
                    self.send_response(401 if owner.mode=='auth' else 404);self.send_header('Content-Length','0');self.end_headers();return
                if 'id' not in value or 'method' not in value:
                    self.send_response(202);self.send_header('Content-Length','0');self.end_headers();return
                if value['method']=='initialize':result={'protocolVersion':'2025-06-18','capabilities':{'tools':{'listChanged':True}},'serverInfo':{'name':'synthetic-tls','version':'1.0'}}
                elif value['method']=='tools/list':result={'tools':[],'nextCursor':'page2'} if not value['params'].get('cursor') else {'tools':[]}
                else:result={'content':[{'type':'text','text':'合成TLS结果'}],'isError':False}
                message={'jsonrpc':'2.0','id':value['id'],'result':result}
                if owner.mode=='unknown':message['id']=99
                payload=json.dumps(message,ensure_ascii=False).encode()
                media='application/json'
                if owner.mode in {'sse','request','duplicate','sse-invalid','notifications'}:
                    media='text/event-stream';prefix=b''
                    if value['method']!='initialize':
                        if owner.mode=='request':prefix=b'data: '+json.dumps({'jsonrpc':'2.0','id':901,'method':'elicitation/create','params':{}}).encode()+b'\n\n'
                        elif owner.mode=='notifications':prefix=b''.join(b'data: '+json.dumps({'jsonrpc':'2.0','method':'notifications/progress','params':{'progress':i}}).encode()+b'\n\n' for i in range(33))
                        else:prefix=b'data: {"jsonrpc":"2.0","method":"notifications/tools/list_changed"}\n\n'
                    payload=prefix+b'event: message\ndata: '+payload+b'\n\n'
                    if owner.mode=='duplicate':payload+=payload
                    if owner.mode=='sse-invalid':payload=b'retry: 1\ndata: '+json.dumps(message).encode()+b'\n\n'
                if owner.mode=='oversize':payload=b' '*70000
                if owner.mode=='media':media='text/html'
                self.send_response(200);self.send_header('Content-Type',media);self.send_header('Content-Length',str(len(payload)))
                self.send_header('Mcp-Session-Id','fixture-session' if owner.mode!='session-invalid' else 'bad session')
                if owner.mode=='gzip':self.send_header('Content-Encoding','gzip')
                self.end_headers();self.wfile.write(payload);self.wfile.flush()
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.load_cert_chain(cert,key);self.server.socket=ctx.wrap_socket(self.server.socket,server_side=True)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url='https://localhost:'+str(self.server.server_address[1])+'/mcp'
    def close(self):self.server.shutdown();self.server.server_close();self.thread.join(2)
