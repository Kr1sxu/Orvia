import {beforeEach,describe,it,expect,vi} from 'vitest';
import {randomUUID} from 'node:crypto';
import type {BackendClient} from '../src/main/backend';
import type {BrowserWindow} from 'electron';
const native=vi.hoisted(()=>({message:vi.fn(),open:vi.fn()}));
vi.mock('electron',()=>({dialog:{showMessageBox:native.message,showOpenDialog:native.open}}));
import {registerProcesses} from '../src/main/process-ipc';
import {processId,processOperation,processApproval,processLaunchInput,processActionInput,processIdentity,processList,processPreview,processExecution,processHistory} from '../src/main/process-contracts';

const cid=randomUUID(),oid=randomUUID(),revision='a'.repeat(64),ticks='134358720000000001';
const target={pid:31415,create_time:1780905600,creation_ticks:ticks,name:'synthetic.exe',executable:'C:\\synthetic\\synthetic.exe',sha256:'b'.repeat(64)};
const preview={id:cid,operation_id:oid,revision,action:'wait',target,launch:null,wait_seconds:3,purpose:'等待准确普通用户进程',risk:'只观察准确进程，不关闭或终止。'};
const launch={...preview,action:'launch',target:null,launch:{name:target.name,executable:target.executable,args:['--synthetic','合成参数'],cwd:'C:\\synthetic',sha256:target.sha256},purpose:'启动普通权限程序',risk:'普通账户启动程序。'};
const result={id:cid,operation_id:oid,revision,action:'wait',status:'still_running',target,exit_code:null,started_at:'2026-10-08T00:00:00Z',finished_at:'2026-10-08T00:00:03Z',verified:true,close_sent:false,error:null};
const action={id:cid,action:'wait',pid:target.pid,create_time:target.create_time,creation_ticks:ticks,wait_seconds:3};
const launchRequest={id:cid,args:launch.launch.args,choose_cwd:false,wait_seconds:3};
const approval={id:cid,operation_id:oid,revision};
function context(response:(method:string,params:Record<string,unknown>)=>unknown=(method)=>({list:{processes:[target],truncated:false,unavailable_reason:null},preview_launch:launch,preview_action:preview,review:preview,execute:result,status:result,history:{executions:[result],truncated:false}}[method]),serial=<T>(fn:()=>Promise<T>)=>fn()){
  const handlers=new Map<string,(...args:unknown[])=>Promise<unknown>>(),processes=vi.fn(async(method:string,params:Record<string,unknown>)=>response(method,params));
  const authorization=registerProcesses({handle:(channel,_count,fn)=>handlers.set(channel,fn),serial,window:()=>({} as BrowserWindow),backend:()=>({processes} as unknown as BackendClient)});
  return{processes,authorization,invoke:(method:string,input:unknown)=>handlers.get(`orvia:process-${method}`)!(input)};
}
beforeEach(()=>{vi.clearAllMocks();native.message.mockResolvedValue({response:1});native.open.mockResolvedValue({canceled:false,filePaths:[target.executable]});});

describe('V4-009普通用户进程单次准确许可',()=>{
  it('renderer不能提交路径、程序、环境、任意method、提权或伪造批准',()=>{
    for(const [schema,input] of [[processId,{id:cid}],[processOperation,{id:cid,operation_id:oid}],[processApproval,approval],[processLaunchInput,launchRequest],[processActionInput,action]] as const){expect(schema.safeParse(input).success).toBe(true);for(const extra of [{path:'C:/private'},{executable:'other.exe'},{cwd:'C:/private'},{env:{key:'synthetic'}},{method:'kill-all'},{approved:true},{elevated:true},{model:'other'}])expect(schema.safeParse({...input,...extra}).success).toBe(false);}
  });
  it('启动参数必须有界纯字符串数组，拒对象/deep/NUL/无效Unicode与实际UTF8超8KiB',()=>{
    for(const args of [[{}],[['deep']],['a\0b'],['\ud800'],Array.from({length:17},()=>''),Array.from({length:3},()=> '汉'.repeat(1000))])expect(processLaunchInput.safeParse({...launchRequest,args}).success).toBe(false);
    expect(processLaunchInput.safeParse({...launchRequest,args:['😀'.repeat(1000)]}).success).toBe(true);expect(processLaunchInput.safeParse({...launchRequest,args:['😀'.repeat(1001)]}).success).toBe(false);
  });
  it('动作需准确PID与原始FILETIME，JS创建时间不能代替ticks，等待限1至15秒',()=>{
    expect(processActionInput.safeParse({...action,creation_ticks:undefined}).success).toBe(false);expect(processActionInput.safeParse({...action,creation_ticks:Number(ticks)}).success).toBe(false);
    expect(processActionInput.parse(action).creation_ticks).toBe(ticks);for(const wait_seconds of [0,16,1.5,Infinity])expect(processActionInput.safeParse({...action,wait_seconds}).success).toBe(false);
    expect(processActionInput.safeParse({...action,action:'kill_all'}).success).toBe(false);expect(processActionInput.safeParse({...action,pid:0}).success).toBe(false);
  });
  it('列表无命令行/env/window正文，只受限50身份且真实48KiB总预算',()=>{
    expect(processIdentity.parse(target).creation_ticks).toBe(ticks);for(const extra of [{cmdline:['private']},{env:{value:'private'}},{window_text:'private'}])expect(processIdentity.safeParse({...target,...extra}).success).toBe(false);
    expect(processList.safeParse({processes:Array.from({length:51},()=>target),truncated:false,unavailable_reason:null}).success).toBe(false);
    expect(processList.safeParse({processes:Array.from({length:50},()=>({...target,executable:'汉'.repeat(1500)})),truncated:false,unavailable_reason:null}).success).toBe(false);
  });
  it('执行事实仍运行/close_sent=false不能伪称发送关闭或业务完成，历史最多十条',()=>{
    expect(processExecution.parse(result)).toMatchObject({status:'still_running',verified:true,close_sent:false});expect(processExecution.safeParse({...result,status:'completed'}).success).toBe(false);expect(processExecution.safeParse({...result,business_complete:true}).success).toBe(false);
    expect(processHistory.safeParse({executions:Array.from({length:11},()=>result),truncated:false}).success).toBe(false);expect(processPreview.safeParse({...preview,action:'launch'}).success).toBe(false);
  });
  it('原生exe或cwd取消均零backend预览/启动，只原生路径经主私有传递',async()=>{
    const c=context();native.open.mockResolvedValueOnce({canceled:true,filePaths:[]});expect(await c.invoke('launch-preview',launchRequest)).toEqual({cancelled:true});native.open.mockResolvedValueOnce({canceled:false,filePaths:[target.executable]}).mockResolvedValueOnce({canceled:true,filePaths:[]});expect(await c.invoke('launch-preview',{...launchRequest,choose_cwd:true})).toEqual({cancelled:true});expect(c.processes).not.toHaveBeenCalled();
    native.open.mockResolvedValueOnce({canceled:false,filePaths:[target.executable]}).mockResolvedValueOnce({canceled:false,filePaths:[launch.launch.cwd]});expect(await c.invoke('launch-preview',{...launchRequest,choose_cwd:true})).toMatchObject({cancelled:false});expect(c.processes).toHaveBeenCalledWith('preview_launch',{id:cid,args:launch.launch.args,wait_seconds:3,executable:target.executable,cwd:launch.launch.cwd});
  });
  it('程序或参数预览与原生选择不对应时拒绝，renderer无法偷偷启动其它程序',async()=>{
    const c=context(()=>({...launch,launch:{...launch.launch,executable:'C:/other.exe'}}));await expect(c.invoke('launch-preview',launchRequest)).rejects.toThrow();const d=context(()=>({...launch,launch:{...launch.launch,args:['--different']}}));await expect(d.invoke('launch-preview',launchRequest)).rejects.toThrow();expect(native.message).not.toHaveBeenCalled();
  });
  it('PID重用即使JS浮点创建时间一样，只要原始ticks改变就拒绝预览',async()=>{
    const c=context(()=>({...preview,target:{...target,creation_ticks:'134358720000000002'}}));await expect(c.invoke('action-preview',action)).rejects.toThrow();await expect(c.invoke('execute',approval)).rejects.toThrow();expect(native.message).not.toHaveBeenCalled();
  });
  it('缺审查、错会话/revision不能执行；原生取消零动作且许可消耗',async()=>{
    const c=context();await expect(c.invoke('execute',approval)).rejects.toThrow();expect(c.processes).not.toHaveBeenCalled();await c.invoke('action-preview',action);await expect(c.invoke('execute',{...approval,id:randomUUID()})).rejects.toThrow();await expect(c.invoke('execute',{...approval,revision:'c'.repeat(64)})).rejects.toThrow();
    native.message.mockResolvedValue({response:0});expect(await c.invoke('execute',approval)).toEqual({cancelled:true});await expect(c.invoke('execute',approval)).rejects.toThrow();expect(c.processes.mock.calls.map(call=>call[0])).toEqual(['preview_action','review']);
    const detail=native.message.mock.calls.at(-1)![1].detail;expect(detail).toContain(ticks);expect(detail).toContain(target.sha256);expect(detail).toContain('只等待');expect(detail).toContain('不表示业务全部完成');
  });
  it('完整保存包fresh重核，程序哈希变化即使revision未变也拒绝旧许可',async()=>{
    let changed=false;const c=context(()=>changed?{...preview,target:{...target,sha256:'f'.repeat(64)}}:preview);await c.invoke('action-preview',action);changed=true;await expect(c.invoke('execute',approval)).rejects.toThrow();expect(native.message).not.toHaveBeenCalled();expect(c.processes.mock.calls.map(call=>call[0])).toEqual(['preview_action','review']);
  });
  it('原生批准仅单次执行，unknown与窗口异常均不自动重放',async()=>{
    const c=context(method=>{if(method==='execute')throw Error('synthetic unknown');return preview;});await c.invoke('action-preview',action);await expect(c.invoke('execute',approval)).rejects.toThrow('synthetic unknown');await expect(c.invoke('execute',approval)).rejects.toThrow();expect(c.processes.mock.calls.map(call=>call[0])).toEqual(['preview_action','review','execute']);
    const d=context();await d.invoke('action-preview',action);native.message.mockRejectedValueOnce(Error('synthetic dialog unknown'));await expect(d.invoke('execute',approval)).rejects.toThrow();await expect(d.invoke('execute',approval)).rejects.toThrow();expect(d.processes.mock.calls.map(call=>call[0])).toEqual(['preview_action','review']);
  });
  it('温和关闭未退出只返回仍运行，明确未保存风险，不自动升级终止',async()=>{
    const closePreview={...preview,action:'close'},closed={...result,action:'close',close_sent:true};const c=context(method=>method==='execute'?closed:closePreview);await c.invoke('action-preview',{...action,action:'close'});expect(await c.invoke('execute',approval)).toMatchObject({result:{status:'still_running',close_sent:true}});expect(c.processes.mock.calls.map(call=>call[0])).toEqual(['preview_action','review','execute']);const detail=native.message.mock.calls.at(-1)![1].detail;expect(detail).toContain('未保存提示');expect(detail).toContain('不自动升级');
    const terminate=context(method=>method==='execute'?{...result,action:'terminate',status:'exited'}:{...preview,action:'terminate'});await terminate.invoke('action-preview',{...action,action:'terminate'});await terminate.invoke('execute',approval);const risk=native.message.mock.calls.at(-1)![1].detail;expect(risk).toContain('所示单个PID');expect(risk).toContain('不递归、不批量');expect(risk).toContain('无法撤销');
  });
  it('长wait串行未结束时list/status/history旁路可读，不依赖serial释放',async()=>{
    const c=context(undefined,async<T>(_fn:()=>Promise<T>)=>{throw Error('serial must not be used');});await c.invoke('list',{id:cid});await c.invoke('status',{id:cid,operation_id:oid});await c.invoke('history',{id:cid});expect(c.processes.mock.calls.map(call=>call[0])).toEqual(['list','status','history']);
  });
  it('最多二十个预览，重连clear/历史读均不恢复旧动作批准',async()=>{
    const c=context((_method,params)=>({...preview,id:params.id,operation_id:randomUUID()}));const first=await c.invoke('action-preview',action) as {operation_id:string};for(let i=0;i<20;i++)await c.invoke('action-preview',action);await expect(c.invoke('execute',{...approval,operation_id:first.operation_id})).rejects.toThrow();
    const d=context();await d.invoke('action-preview',action);await d.invoke('history',{id:cid});d.authorization.clear();await expect(d.invoke('execute',approval)).rejects.toThrow();
  });
  it('返回事实身份必须对应本次准确批准，其它会话或复用PID结果不作成功响应',async()=>{
    for(const other of [{...result,id:randomUUID()},{...result,target:{...target,creation_ticks:'134358720000000002'}}]){const c=context(method=>method==='execute'?other:preview);await c.invoke('action-preview',action);await expect(c.invoke('execute',approval)).rejects.toThrow('返回进程事实');await expect(c.invoke('execute',approval)).rejects.toThrow();expect(c.processes.mock.calls.map(call=>call[0])).toEqual(['preview_action','review','execute']);}
  });
});
