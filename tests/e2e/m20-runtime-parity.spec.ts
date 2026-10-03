/** 实际开发/安装后端的LPAC、UIA、可见Chromium对照；仅合成原生批准，无模型或网络替换。 */
import {_electron as electron,expect,test} from '@playwright/test';
import {mkdir,mkdtemp,writeFile,readFile,stat} from 'node:fs/promises';
import {execFile,spawn} from 'node:child_process';
import {promisify} from 'node:util';
import {randomBytes} from 'node:crypto';
import path from 'node:path';

const mode=process.env.ORVIA_M20_PARITY_MODE;
const run=promisify(execFile);
// 外部探针只读取应用子树的Chrome进程和原生令牌，不枚举其他窗口标题、数据或个人浏览器。
const chromeProbe=String.raw`
import ctypes,json,sys
from ctypes import wintypes as w
from pathlib import Path
import psutil
from orvia_backend.automation.windows_isolation import _Native
parent=int(sys.argv[1]);root=Path(sys.argv[2]);native=_Native()
native.k.OpenProcess.argtypes,native.k.OpenProcess.restype=[w.DWORD,w.BOOL,w.DWORD],w.HANDLE
children=[p for p in psutil.Process(parent).children(recursive=True) if p.name().lower()=='chrome.exe']
facts=[];identities=[]
for child in children:
 args=child.cmdline();assert '--no-sandbox' not in args
 assert Path(child.exe()).is_relative_to(root)
 identities.append({'pid':child.pid,'created':child.create_time()})
 if '--type=renderer' not in args:continue
 process=native.k.OpenProcess(0x1000,False,child.pid);token=w.HANDLE()
 try:
  assert process and native.a.OpenProcessToken(process,0x8,ctypes.byref(token))
  integrity=native.token_info(token,25);sid=native.sid_string(ctypes.cast(integrity,ctypes.POINTER(w.LPVOID))[0])
  elevation=int.from_bytes(native.token_info(token,20).raw[:4],'little')
  assert sid in {'S-1-16-0','S-1-16-4096'} and elevation==0
  facts.append({'integrity':sid,'elevated':False})
 finally:
  if token:native.k.CloseHandle(token)
  if process:native.k.CloseHandle(process)
user=ctypes.WinDLL('user32',use_last_error=True);callback=ctypes.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
user.IsWindowVisible.argtypes,user.IsWindowVisible.restype=[w.HWND],w.BOOL
user.GetWindowThreadProcessId.argtypes,user.GetWindowThreadProcessId.restype=[w.HWND,ctypes.POINTER(w.DWORD)],w.DWORD
user.EnumWindows.argtypes,user.EnumWindows.restype=[callback,w.LPARAM],w.BOOL
pids={p.pid for p in children};visible=[]
def check(hwnd,_):
 pid=w.DWORD();user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
 if pid.value in pids and user.IsWindowVisible(hwnd):visible.append(True)
 return True
user.EnumWindows(callback(check),0)
assert facts and visible
print(json.dumps({'rendererTokens':facts,'ownedIdentities':identities,'visible':True,'privateRuntime':True,'sandbox':True}))
`;

test.skip(!['development','installed'].includes(mode??''),'需显式选择真实运行时对照模式');
test(`M20 ${mode} 真实LPAC/UIA/可见Chromium外发拒绝与资源对照`,async()=>{
  test.setTimeout(180000);
  const results=path.resolve('artifacts/test-results/M20');await mkdir(results,{recursive:true});
  const work=await mkdtemp(path.join(results,'r-')),nativeTemp=path.join(results,'v-'+randomBytes(4).toString('hex'));
  await mkdir(nativeTemp);const profile=path.join(work,'profile');
  const outside=path.join(work,'outside-synthetic.txt');await writeFile(outside,'outside synthetic only','utf8');
  const title=`Orvia M20 ${mode} ${randomBytes(3).toString('hex')}`;
  const powershell=path.join(process.env.SystemRoot!,'System32/WindowsPowerShell/v1.0/powershell.exe');
  await run(powershell,['-NoProfile','-NonInteractive','-File',path.resolve('tests/e2e/m18_desktop_fixture.ps1'),'-OutputDirectory',work,'-PrepareOnly'],{windowsHide:true,env:{...process.env,TEMP:nativeTemp,TMP:nativeTemp}});
  const fixture=spawn(path.join(work,'m18_desktop_fixture.exe'),[title],{stdio:'ignore',windowsHide:false});
  const env:NodeJS.ProcessEnv={...process.env,TEMP:nativeTemp,TMP:nativeTemp,ORVIA_DEV_DATA_DIR:profile};
  for(const key of Object.keys(env))if(key==='ELECTRON_RUN_AS_NODE'||/^(DEEPSEEK|ZHIPU|MIMO|TAVILY)_|^PYTHON|^PLAYWRIGHT_/.test(key)||key.startsWith('ORVIA_M18_')||key.startsWith('ORVIA_M20_'))delete env[key];
  const installed=mode==='installed';let record:any;
  if(installed){
    record=JSON.parse((await readFile(path.join(results,'installation.json'),'utf8')).replace(/^\uFEFF/,''));
    expect(record).toMatchObject({module:'M20',appId:'cn.orvia.m20.fulltest',version:'0.3.0-rc.1',status:'installed'});
    expect(record.installRoot).toBe(path.join(results,'install-smoke'));
    env.PATH=path.join(process.env.SystemRoot!,'System32');delete env.ORVIA_DEV_DATA_DIR;
  }
  const app=await electron.launch(installed?{executablePath:path.join(results,'install-smoke/Orvia M20 Full Test.exe'),args:[`--user-data-dir=${profile}`],env}:
    {args:[path.resolve('tests/e2e/m20-runtime-parity-launch.cjs'),`--user-data-dir=${profile}`],env}).catch(error=>{fixture.kill();throw error;});
  let browserSession:string|undefined,conversation:string|undefined;
  try{
    await app.evaluate(({dialog,app},{title,work,root})=>{
      const load=(process as any).getBuiltinModule('node:module').createRequire((app.isPackaged?process.resourcesPath+'/app.asar':root)+'/dist/main/main.js');
      const allowed=new Set(['确认隔离运行完整脚本','逐步批准桌面动作','授权准确浏览器站点与动作']);
      dialog.showMessageBox=(async(_window:unknown,options:any)=>{
        if(options.title==='明确选择一个普通权限应用'){
          const index=options.buttons.findIndex((label:string)=>label.includes(title));
          const next=options.buttons.indexOf('下一页');
          return {response:index>0?index:next>0?next:0,checkboxChecked:false};
        }
        if(options.title==='另行确认实际外发请求')return {response:0,checkboxChecked:false};
        if(!allowed.has(options.title))throw Error('运行时测试出现未预期原生审批');
        return {response:1,checkboxChecked:false};
      }) as typeof dialog.showMessageBox;
      dialog.showSaveDialog=(async(_window:unknown,options:any)=>{
        if(!options.title.startsWith('逐文件回传已核验产物'))throw Error('运行时测试出现未预期保存批准');
        if(!['result-1.txt','result-2.txt'].includes(options.defaultPath))throw Error('运行时测试产物身份不符');
        return {canceled:false,filePath:load('node:path').join(work,'approved-'+options.defaultPath)};
      }) as typeof dialog.showSaveDialog;
      // 仅见证真实chat.continue派发次数；保留原方法、真实IPC/stdio和全部返回结果。
      const backend=load('./backend.js');
      const original=backend.BackendClient.prototype.chat;
      (globalThis as any).__orviaM20Continuations=[];
      backend.BackendClient.prototype.chat=function(method:string,input:any){
        if(method==='chat.continue')(globalThis as any).__orviaM20Continuations.push({request_id:input.request_id,continuation_id:input.continuation_id});
        return original.call(this,method,input);
      };
    },{title,work,root:path.resolve('apps/desktop')});
    const page=await app.firstWindow();
    try{await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible({timeout:30000});}
    catch(error){
      const status=await page.evaluate(()=>window.orvia.connectionStatus()).catch(()=>({unavailable:true}));
      const notices=await page.getByRole('status').allTextContents().catch(()=>[]);
      await writeFile(path.join(results,`runtime-parity-${mode}-startup-failure.json`),JSON.stringify({module:'M20',mode,work,status,notices,phase:'startup; no natural request sent',realModels:0},null,2),'utf8');throw error;
    }
    const readState=async()=>page.evaluate(async()=>{const list=await window.orvia.chatList();if(!list.ok)throw Error('chat list');const reply=await window.orvia.chatGet({id:list.result.conversations[0].id});if(!reply.ok)throw Error(reply.message);return reply.result;});
    const continuationCount=async()=>app.evaluate(()=> (globalThis as any).__orviaM20Continuations.length);
    const scriptFacts:any[]=[];const requestIds:string[]=[];
    for(let index=1;index<=2;index++){
      const source=`from pathlib import Path\nimport sys,json,os\nfacts={}\ndef denied(name,fn):\n try: fn();facts[name]=False\n except (OSError,ImportError): facts[name]=True\ndenied('outside_read',lambda:Path(${JSON.stringify(outside)}).read_text())\ndenied('outside_write',lambda:Path(${JSON.stringify(outside)}).write_text('changed'))\ndenied('runtime_write',lambda:Path(sys.prefix,'M20-denied.txt').write_text('denied'))\ndef network():\n import socket\n value=socket.socket();value.close()\ndenied('network_socket',network)\nfacts['environment_clean']=all(name not in os.environ for name in ('DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY','PYTHONPATH'))\nassert all(facts.values()),facts\nPath('output/result-${index}.txt').write_text('M20真实隔离产物${index}',encoding='utf-8')\nprint(json.dumps(facts))\n`;
      await page.getByLabel('输入需求').fill('请运行这个Python脚本：\n```python\n'+source+'```');await page.getByLabel('输入需求').press('Enter');
      const preview=page.getByLabel('脚本审批预览');await expect(preview).toContainText(`result-${index}.txt`);
      const state=await readState();expect(state.workflow?.action).toBe('script');
      if(conversation)expect(state.id).toBe(conversation);conversation=state.id;
      requestIds.push(state.workflow!.request_id);expect(new Set(requestIds).size).toBe(index);
      // 后端拒绝旧投影也不算通过：本次批准前必须没有发出任何新continue。
      expect(await continuationCount()).toBe(index-1);
      const history=await page.evaluate(id=>window.orvia.m18History({id}),conversation);if(!history.ok)throw Error(history.message);
      const pendingPlan=history.result.operations.find(item=>item.kind==='script'&&item.status==='awaiting_approval');if(!pendingPlan)throw Error('本次脚本审批事实缺失');
      const approval={id:conversation,operation_id:pendingPlan.operation_id,revision:pendingPlan.revision};
      await preview.getByRole('button',{name:'原生确认此脚本步骤',exact:true}).click();
      await expect.poll(async()=>{const fact=await page.evaluate(q=>window.orvia.m18ScriptStatus(q),{id:conversation!,operation_id:approval.operation_id});
        if(!fact.ok)throw Error(fact.message);if(fact.result.status==='failed')throw Error(JSON.stringify(fact.result.result));return fact.result.status;},{timeout:60000}).toBe('completed');
      const fact=await page.evaluate(q=>window.orvia.m18ScriptStatus(q),{id:conversation,operation_id:approval.operation_id});if(!fact.ok)throw Error(fact.message);
      expect(fact.result.result?.token_verified).toBe(true);expect(fact.result.result?.processes_reaped).toBe(true);
      const boundaries=JSON.parse(String(fact.result.result?.stdout).trim());expect(Object.values(boundaries).every(value=>value===true)).toBe(true);
      const scriptFact={operationId:approval.operation_id,requestId:requestIds.at(-1),tokenVerified:true,processesReaped:true,boundaries,newFileExportVerified:false,replayDenied:false};
      scriptFacts.push(scriptFact);
      await writeFile(path.join(results,`runtime-parity-${mode}-checkpoint.json`),JSON.stringify({module:'M20',mode,phase:'actual script completed before continuation',work,scriptFacts,continuations:await app.evaluate(()=>(globalThis as any).__orviaM20Continuations)},null,2),'utf8');
      try{await expect.poll(async()=>(await readState()).workflow,{timeout:15000}).toBeNull();}
      catch(error){
        const current=await readState(),actualResult=page.getByLabel('Python实际运行结果');
        const visible=await actualResult.count()?await actualResult.innerText():'';
        await writeFile(path.join(results,`runtime-parity-${mode}-failure.json`),JSON.stringify({module:'M20',mode,phase:'completed operation did not continue',work,scriptFacts,
          workflow:{action:current.workflow?.action,requestId:current.workflow?.request_id,token:current.workflow?.continuation_id,state:current.workflow?.state},
          continuations:await app.evaluate(()=>(globalThis as any).__orviaM20Continuations),visibleActualResult:visible.slice(0,8192)},null,2),'utf8');throw error;
      }
      expect(await continuationCount()).toBe(index);
      expect((await page.evaluate(q=>window.orvia.m18ScriptExecute(q),approval)).ok).toBe(false);
      const copy=await page.evaluate(q=>window.orvia.m18ScriptExport(q),{...approval,index:0});expect(copy.ok&&copy.result.cancelled===false).toBe(true);
      expect(await readFile(path.join(work,`approved-result-${index}.txt`),'utf8')).toBe(`M20真实隔离产物${index}`);
      scriptFact.newFileExportVerified=true;scriptFact.replayDenied=true;
    }
    expect(await readFile(outside,'utf8')).toBe('outside synthetic only');
    // 后续为直接API的运行时对照；先通过可访问入口打开详情，不把它冒充桌面NL流程。
    const executionSummary=page.locator('summary').filter({hasText:/^脚本、桌面与浏览器执行详情$/});
    if(!(await executionSummary.evaluate(element=>(element.parentElement as HTMLDetailsElement).open)))await executionSummary.click();
    const picked=await page.evaluate(id=>window.orvia.m18DesktopChoose({id}),conversation);if(!picked.ok||!picked.result.observation)throw Error('合成UIA窗口没有获准确授权');
    let observation=picked.result.observation;
    for(const step of [{action:'set_value' as const,value:'M20 synthetic UIA',name:''},{action:'invoke' as const,value:'',name:'M18 apply'}]){
      const control=observation.controls.find(item=>step.name?item.name===step.name:item.control_type==='Edit'&&item.patterns?.includes('value'));
      if(!control)throw Error('合成UIA唯一控件缺失');
      const planned=await page.evaluate(q=>window.orvia.m18DesktopPreview(q),{id:conversation,grant_id:observation.grant_id!,control_id:control.control_id,action:step.action,value:step.value,state_hash:observation.state_hash,category:'local' as const,expectation:'APPLIED:M20 synthetic UIA'});
      if(!planned.ok)throw Error(planned.message);const request={id:conversation,operation_id:planned.result.operation_id,revision:planned.result.revision};
      expect((await page.evaluate(q=>window.orvia.m18DesktopExecute(q),request)).ok).toBe(true);
      await expect.poll(async()=>{const history=await page.evaluate(id=>window.orvia.m18History({id}),conversation!);return history.ok?history.result.operations.find(item=>item.operation_id===request.operation_id)?.status:history.message;},{timeout:25000}).toBe('completed');
      const fresh=await page.evaluate(q=>window.orvia.m18DesktopObserve(q),{id:conversation,grant_id:observation.grant_id!});if(!fresh.ok)throw Error(fresh.message);observation=fresh.result;
    }
    expect(observation.controls.some(item=>item.name==='APPLIED:M20 synthetic UIA')).toBe(true);
    const opened=await page.evaluate(id=>window.orvia.m18BrowserOpen({id,url:'https://m20.example/_m20_gate',allowed_actions:['message'],get_write_paths:['/_m20_gate']}),conversation);
    if(!opened.ok||!opened.result.observation)throw Error(opened.ok?'专用浏览器观察缺失':opened.message);
    browserSession=opened.result.observation.session_id!;
    const pending=await page.evaluate(q=>window.orvia.m18BrowserPending(q),{id:conversation,session_id:browserSession});if(!pending.ok||!pending.result.pending_request)throw Error('实际初始GET没有暂停');
    expect(pending.result.pending_request).toMatchObject({method:'GET',url:'https://m20.example/_m20_gate',bytes:0});
    const python=path.resolve('backend/.venv/Scripts/python.exe');
    const raw=await run(python,['-X','utf8','-c',chromeProbe,String(app.process().pid),path.join(profile,'automation/browser-runtime')],{windowsHide:true,cwd:path.resolve('backend')});
    const browserFacts=JSON.parse(raw.stdout);
    const request=pending.result.pending_request;
    const refused=await page.evaluate(q=>window.orvia.m18BrowserRequest(q),{id:conversation,session_id:browserSession,request_id:request.request_id,revision:request.revision});
    expect(refused.ok&&refused.result.cancelled).toBe(true);
    expect((await page.evaluate(q=>window.orvia.m18BrowserRequest(q),{id:conversation,session_id:browserSession,request_id:request.request_id,revision:request.revision})).ok).toBe(false);
    expect((await page.evaluate(q=>window.orvia.m18BrowserClose(q),{id:conversation,session_id:browserSession})).ok).toBe(true);browserSession=undefined;
    const reaped=String.raw`import json,sys,psutil
remaining=[]
for item in json.loads(sys.argv[1]):
 try:
  if psutil.Process(item['pid']).create_time()==item['created']:remaining.append(item['pid'])
 except psutil.NoSuchProcess:pass
print(json.dumps({'reaped':not remaining}))`;
    await expect.poll(async()=>JSON.parse((await run(python,['-c',reaped,JSON.stringify(browserFacts.ownedIdentities)],{windowsHide:true})).stdout).reaped,{timeout:15000}).toBe(true);
    await page.screenshot({path:path.join(results,`runtime-parity-${mode}.png`)});
    await writeFile(path.join(results,`runtime-parity-${mode}.json`),JSON.stringify({module:'M20',mode,version:installed?record.version:'0.3.0-rc.1',realBackend:true,frozenBackend:installed,realModels:0,
      nativeApproval:'synthetic test decisions',script:{naturalRequests:2,sameConversation:true,previousSuccessNeverContinuesNextRequest:true,actualContinuations:await continuationCount(),facts:scriptFacts},
      desktop:{actualWorker:true,onlySyntheticWindow:true,valueAndInvokeVerified:true},browser:{...browserFacts,ownedIdentities:undefined,actualCompleteChromium:true,actualRequestPaused:true,nativeRefusalVerified:true,duplicateDenied:true,ownedProcessesReaped:true,outboundRequests:0,pageLoaded:false},
      scope:'实际LPAC/UIA/可见浏览器运行时和审批边界；浏览器目标未加载，不替代网络写入业务或独立Windows验收'},null,2),'utf8');
  }finally{
    try{
      if(browserSession&&conversation){const page=await app.firstWindow().catch(()=>undefined);await page?.evaluate(q=>window.orvia.m18BrowserClose(q),{id:conversation,session_id:browserSession}).catch(()=>{});}
    }finally{try{await app.close();}finally{fixture.kill();}}
  }
});
