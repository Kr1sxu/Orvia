import {beforeEach,afterEach,describe,it,expect,vi} from 'vitest';
import {randomUUID} from 'node:crypto';
import {promises as fs} from 'node:fs';
import path from 'node:path';
import type {BackendClient} from '../src/main/backend';
import type {BrowserWindow} from 'electron';
const native=vi.hoisted(()=>({message:vi.fn(),open:vi.fn(),save:vi.fn()}));
vi.mock('electron',()=>({dialog:{showMessageBox:native.message,showOpenDialog:native.open,showSaveDialog:native.save}}));
import {registerShell} from '../src/main/shell-ipc';
import {shellId,shellOperation,shellApproval,shellPreviewInput,shellExportInput,shellPreview,shellRun,shellHistory,shellOutputName} from '../src/main/shell-contracts';

const cid=randomUUID(),rid=randomUUID(),revision='a'.repeat(64),script='Write-Output "SYNTHETIC"\nWrite-Output "SECOND"';
const interpreter={id:'powershell',label:'PowerShell 7 合成',executable:'C:\\synthetic\\pwsh.exe',version:'7.5',sha256:'b'.repeat(64),available:true,reason:null,distro:null};
const packet={id:cid,run_id:rid,revision,interpreter,script,cwd:'C:\\synthetic\\work',inputs:[],output_names:['artifact.txt'],timeout_seconds:20,expected_stdout:null,budgets:{script_bytes:16384,stdout_bytes:16384,stderr_bytes:16384,file_bytes:1048576,total_file_bytes:2097152},purpose:'执行普通账户 Shell 脚本'};
const request={id:cid,interpreter_id:'powershell',script,timeout_seconds:20,output_names:['artifact.txt'],choose_cwd:false,choose_inputs:false};
const approval={id:cid,run_id:rid,revision};
const run={id:cid,run_id:rid,revision,interpreter_id:'powershell',status:'exited',exit_code:0,stdout:'SYNTHETIC',stderr:'',stdout_truncated:false,stderr_truncated:false,children_reaped:true,started_at:'2026-10-08T00:00:00Z',finished_at:'2026-10-08T00:00:01Z',verification:{status:'not_requested',details:[]},outputs:[],error:null};
const exportPacket={id:cid,run_id:rid,name:'artifact.txt',bytes:12,sha256:'c'.repeat(64),revision,purpose:'回传 Shell 产物为新文件'};
const exportRequest={id:cid,run_id:rid,name:'artifact.txt'};
let root:string;
beforeEach(async()=>{vi.clearAllMocks();native.message.mockResolvedValue({response:1});native.open.mockResolvedValue({canceled:false,filePaths:['C:\\synthetic\\chosen']});native.save.mockResolvedValue({canceled:true});const artifacts=path.resolve('artifacts/test-results/V4-008');await fs.mkdir(artifacts,{recursive:true});root=await fs.mkdtemp(path.join(artifacts,'desktop-shell-'));});
afterEach(()=>vi.restoreAllMocks());
function context(result:(method:string,params:Record<string,unknown>)=>unknown=(method)=>({detect:{interpreters:[interpreter]},preview:packet,review:packet,execute:run,status:{...run,status:'running'},cancel:{...run,status:'cancelled'},history:{executions:[run],truncated:false},export_preview:exportPacket,export:{filename:path.join(root,'new.txt'),bytes:12,sha256:exportPacket.sha256,verified:true}}[method]),serial=<T>(fn:()=>Promise<T>)=>fn()){
  const handlers=new Map<string,(...args:unknown[])=>Promise<unknown>>(),shell=vi.fn(async(method:string,params:Record<string,unknown>)=>result(method,params));
  const authorization=registerShell({handle:(channel,_count,fn)=>handlers.set(channel,fn),serial,window:()=>({} as BrowserWindow),backend:()=>({shell} as unknown as BackendClient)});
  return{shell,authorization,invoke:(method:string,input?:unknown)=>handlers.get(`orvia:shell-${method}`)!(...(input===undefined?[]:[input]))};
}

describe('V4-008普通账户Shell准确批准边界',()=>{
  it('renderer不能传路径、URL、自由参数、批准或解释器程序，只接受固定有界输入',()=>{
    for(const [schema,input] of [[shellId,{id:cid}],[shellOperation,{id:cid,run_id:rid}],[shellApproval,approval],[shellPreviewInput,request],[shellExportInput,exportRequest]] as const){expect(schema.safeParse(input).success).toBe(true);for(const extra of [{cwd:'C:/private'},{inputs:['private']},{path:'C:/private'},{url:'https://other.invalid'},{executable:'other.exe'},{args:['--other']},{approved:true},{method:'execute'}])expect(schema.safeParse({...input,...extra}).success).toBe(false);}
    expect(shellPreviewInput.safeParse({...request,interpreter_id:'C:/private.exe'}).success).toBe(false);expect(shellPreviewInput.safeParse({...request,timeout_seconds:61}).success).toBe(false);
  });
  it('准确脚本按UTF8限制，拒无效Unicode和NUL，产物普通leaf限制Windows危险名称',()=>{
    expect(shellPreviewInput.safeParse({...request,script:'汉'.repeat(5500)}).success).toBe(false);expect(shellPreviewInput.safeParse({...request,script:'\ud800'}).success).toBe(false);expect(shellPreviewInput.safeParse({...request,script:'a\0b'}).success).toBe(false);
    for(const name of ['../escape.txt','C:/escape.txt','CON.txt','COM¹.txt','output.','space ','a:b'])expect(shellOutputName.safeParse(name).success).toBe(false);expect(shellOutputName.parse('合成成果.txt')).toBe('合成成果.txt');expect(shellPreviewInput.safeParse({...request,output_names:['a.txt','A.txt']}).success).toBe(false);
  });
  it('stdout/stderr、完整执行与历史包分别受限，exit0仍不等于业务完成',()=>{
    expect(shellRun.parse(run).verification.status).toBe('not_requested');expect(shellRun.safeParse({...run,completed:true}).success).toBe(false);expect(shellRun.safeParse({...run,stdout:'汉'.repeat(5500)}).success).toBe(false);
    expect(shellHistory.safeParse({executions:Array.from({length:10},()=>({...run,stdout:'x'.repeat(8000)})),truncated:false}).success).toBe(false);expect(shellHistory.safeParse({executions:Array.from({length:11},()=>run),truncated:false}).success).toBe(false);
    expect(shellPreview.safeParse({...packet,inputs:Array.from({length:3},()=>({name:'input.txt',path:'C:/synthetic/input.txt',bytes:10485761,sha256:revision}))}).success).toBe(false);
  });
  it('原生目录或输入选择取消，及超三个输入均零后端预览与执行',async()=>{
    const c=context();native.open.mockResolvedValueOnce({canceled:true,filePaths:[]});expect(await c.invoke('preview',{...request,choose_cwd:true})).toEqual({cancelled:true});
    native.open.mockResolvedValueOnce({canceled:true,filePaths:[]});expect(await c.invoke('preview',{...request,choose_inputs:true})).toEqual({cancelled:true});
    native.open.mockResolvedValueOnce({canceled:false,filePaths:['a','b','c','d']});await expect(c.invoke('preview',{...request,choose_inputs:true})).rejects.toThrow();expect(c.shell).not.toHaveBeenCalled();
  });
  it('原生路径只经主私有预览传递，准确输入/目录不对应则拒绝审查',async()=>{
    const file='C:\\synthetic\\input.txt',cwd='C:\\synthetic\\chosen';native.open.mockResolvedValueOnce({canceled:false,filePaths:[cwd]}).mockResolvedValueOnce({canceled:false,filePaths:[file]});
    const c=context(()=>({...packet,cwd,inputs:[{name:'input.txt',path:file,bytes:12,sha256:revision}]}));expect(await c.invoke('preview',{...request,choose_cwd:true,choose_inputs:true})).toMatchObject({cancelled:false});expect(c.shell).toHaveBeenCalledWith('preview',{id:cid,interpreter_id:'powershell',script,timeout_seconds:20,output_names:['artifact.txt'],cwd,inputs:[file]});
    const wrong=context(()=>({...packet,inputs:[{name:'private.txt',path:'C:/private.txt',bytes:12,sha256:revision}]}));await expect(wrong.invoke('preview',request)).rejects.toThrow();expect(native.message).not.toHaveBeenCalled();
  });
  it('缺审查、错会话或revision不可执行；取消消耗许可且完整脚本与身份可见',async()=>{
    const c=context();await expect(c.invoke('execute',approval)).rejects.toThrow();expect(c.shell).not.toHaveBeenCalled();await c.invoke('preview',request);
    await expect(c.invoke('execute',{...approval,id:randomUUID()})).rejects.toThrow();native.message.mockResolvedValue({response:0});expect(await c.invoke('execute',approval)).toEqual({cancelled:true});await expect(c.invoke('execute',approval)).rejects.toThrow();expect(c.shell.mock.calls.map(call=>call[0])).toEqual(['preview','review']);
    const detail=native.message.mock.calls.at(-1)![1].detail;for(const text of [script,interpreter.sha256,packet.cwd.replaceAll('\\','\\\\'),'timeout_seconds','output_names','expected_stdout','不是 LPAC','退出码0'])expect(detail).toContain(text);
  });
  it('重核完整保存包，解释器或输入身份变化即使revision不变也不批准',async()=>{
    let changed=false;const c=context(()=>changed?{...packet,interpreter:{...interpreter,sha256:'f'.repeat(64)}}:packet);await c.invoke('preview',request);changed=true;await expect(c.invoke('execute',approval)).rejects.toThrow();expect(native.message).not.toHaveBeenCalled();expect(c.shell.mock.calls.map(call=>call[0])).toEqual(['preview','review']);
  });
  it('批准仅执行一次，未知结果和窗口异常不自动重放旧脚本',async()=>{
    const c=context(method=>{if(method==='execute')throw Error('synthetic unknown');return packet;});await c.invoke('preview',request);await expect(c.invoke('execute',approval)).rejects.toThrow('synthetic unknown');await expect(c.invoke('execute',approval)).rejects.toThrow();expect(c.shell.mock.calls.map(call=>call[0])).toEqual(['preview','review','execute']);
    const d=context();await d.invoke('preview',request);native.message.mockRejectedValueOnce(Error('synthetic native unknown'));await expect(d.invoke('execute',approval)).rejects.toThrow();await expect(d.invoke('execute',approval)).rejects.toThrow();expect(d.shell.mock.calls.map(call=>call[0])).toEqual(['preview','review']);
  });
  it('长执行串行挂起时cancel/status/detect/history仍可直接运行，不等serial释放',async()=>{
    const c=context(undefined,async<T>(_fn:()=>Promise<T>)=>{throw Error('serial should not be used');});await c.invoke('cancel',{id:cid,run_id:rid});await c.invoke('status',{id:cid,run_id:rid});await c.invoke('detect');await c.invoke('history',{id:cid});expect(c.shell.mock.calls.map(call=>call[0])).toEqual(['cancel','status','detect','history']);
  });
  it('预览最多二十个，clear关闭旧许可，历史不会恢复可执行批准',async()=>{
    const c=context((_method,params)=>({...packet,id:params.id,run_id:randomUUID()}));const first=await c.invoke('preview',request) as {result:{run_id:string}};for(let i=0;i<20;i++)await c.invoke('preview',request);await expect(c.invoke('execute',{...approval,run_id:first.result.run_id})).rejects.toThrow();
    const d=context();await d.invoke('preview',request);d.authorization.clear();await expect(d.invoke('execute',approval)).rejects.toThrow();
  });
  it('逐文件回传原生取消零写入，已有目的文件拒绝且保持内容',async()=>{
    const c=context();expect(await c.invoke('export',exportRequest)).toEqual({cancelled:true});expect(c.shell.mock.calls.map(call=>call[0])).toEqual(['export_preview']);
    const file=path.join(root,'existing.txt');await fs.writeFile(file,'existing');native.save.mockResolvedValueOnce({canceled:false,filePath:file});await expect(c.invoke('export',exportRequest)).rejects.toThrow('SHELL_DESTINATION_EXISTS');expect(await fs.readFile(file,'utf8')).toBe('existing');expect(c.shell.mock.calls.map(call=>call[0])).toEqual(['export_preview','export_preview']);
  });
  it('逐文件native准确哈希/大小/位置批准，产物版本变化拒绝，renderer不提供path',async()=>{
    const output=path.join(root,'new.txt');native.save.mockResolvedValue({canceled:false,filePath:output});const c=context();await c.invoke('export',exportRequest);expect(c.shell).toHaveBeenLastCalledWith('export',{...exportRequest,revision,path:output});const detail=native.message.mock.calls.at(-1)![1].detail;for(const text of [exportPacket.sha256,exportPacket.name,output,'12'])expect(detail).toContain(text);
    let count=0;const d=context(()=>count++===0?exportPacket:{...exportPacket,sha256:'d'.repeat(64)});await expect(d.invoke('export',exportRequest)).rejects.toThrow();expect(d.shell.mock.calls.map(call=>call[0])).toEqual(['export_preview','export_preview']);
  });
});
