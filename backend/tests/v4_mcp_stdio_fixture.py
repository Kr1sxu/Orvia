"""真实stdio MCP合成fixture，禁止读取用户文件或真实凭据。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
sys.stdin.reconfigure(encoding='utf-8');sys.stdout.reconfigure(encoding='utf-8')
mode=sys.argv[1] if len(sys.argv)>1 and not sys.argv[1].startswith('--') else 'normal'
state=Path(sys.argv[sys.argv.index('--state')+1]) if '--state' in sys.argv else None
if mode=='state':state=Path(__file__).with_suffix('.state.json')
child=None

def emit(value):
    sys.stdout.write(json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n');sys.stdout.flush()

def response(rid,result):emit({'jsonrpc':'2.0','id':rid,'result':result})

for line in sys.stdin:
    value=json.loads(line);method=value.get('method');rid=value.get('id')
    if method=='initialize':
        response(rid,{'protocolVersion':'2025-06-18' if mode!='version' else '2024-11-05','capabilities':{'tools':{'listChanged':True}},'serverInfo':{'name':'synthetic','version':'1.0'}})
    elif method=='notifications/initialized':
        if state:
            child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])
            state.write_text(json.dumps({'parent_pid':os.getpid(),'child_pid':child.pid,'calls':0}),encoding='utf-8')
        if mode=='notification':emit({'jsonrpc':'2.0','method':'notifications/tools/list_changed'})
    elif method=='tools/list':
        if mode=='disconnect':sys.exit(0)
        if mode=='timeout':time.sleep(60)
        if mode=='request':
            emit({'jsonrpc':'2.0','id':'server-request','method':'sampling/createMessage','params':{}})
            continue
        if mode=='oversize':
            response(rid,{'text':'a'*70000});continue
        if mode=='notifications':
            for i in range(33):emit({'jsonrpc':'2.0','method':'notifications/progress','params':{'progress':i}})
        if mode=='stderr':
            sys.stderr.write('synthetic-stderr '*20000);sys.stderr.flush();time.sleep(1)
        if mode=='escape':
            try:
                escape=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],creationflags=0x01000000)
            except OSError:
                response(rid,{'tools':[],'escape_denied':True});continue
            response(rid,{'tools':[],'escape_denied':False,'child_pid':escape.pid});continue
        if mode=='children':
            child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])
            response(rid,{'tools':[],'child_pid':child.pid,'environment_has_secret':any('API_KEY' in key or 'TOKEN' in key for key in os.environ)})
        else:
            tools=[{'name':'read_echo','description':'合成只读回显，不读取文件','inputSchema':{'type':'object','properties':{'query':{'type':'string','minLength':1,'maxLength':100}},'required':['query'],'additionalProperties':False},'outputSchema':{'type':'object','properties':{'query':{'type':'string','minLength':1,'maxLength':100}},'required':['query'],'additionalProperties':False},'annotations':{'readOnlyHint':True}}] if not value.get('params',{}).get('cursor') else [{'name':'write_delete','inputSchema':{'type':'object','properties':{},'additionalProperties':False},'annotations':{'readOnlyHint':False,'destructiveHint':True}}]
            response(rid,{'tools':tools,**({'nextCursor':'second'} if not value.get('params',{}).get('cursor') else {})})
        if mode=='duplicate':response(rid,{'tools':[]})
    elif method=='tools/call':
        if state:
            current=json.loads(state.read_text(encoding='utf-8'));current['calls']+=1;state.write_text(json.dumps(current),encoding='utf-8')
        query=value.get('params',{}).get('arguments',{}).get('query','合成只读结果')
        response(rid,{'content':[{'type':'text','text':query}],'structuredContent':{'query':query},'isError':False})
