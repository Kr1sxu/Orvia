import {beforeEach,describe,it,expect,vi} from 'vitest';
import {randomUUID} from 'node:crypto';
const native=vi.hoisted(()=>({message:vi.fn(),open:vi.fn(),save:vi.fn()}));
vi.mock('electron',()=>({dialog:{showMessageBox:native.message,showOpenDialog:native.open,showSaveDialog:native.save}}));
import {registerM18} from '../src/main/m18-ipc';
import type {BackendClient} from '../src/main/backend';
import type {BrowserWindow} from 'electron';

const cid=randomUUID(),oid=randomUUID(),revision='a'.repeat(64);
const plan={operation_id:oid,revision,status:'awaiting_approval',plan:{kind:'script',source:'pass',origin:'paste',expires_at:Date.now()/1000+300}};
function context(result:(suffix:string,input:object)=>unknown){
  const handlers=new Map<string,(...input:unknown[])=>Promise<unknown>>();
  const automation=vi.fn(async(suffix:string,input:object)=>result(suffix,input));
  const authorization=registerM18({handle:(channel,_count,fn)=>{handlers.set(channel,fn)},serial:async fn=>fn(),window:()=>({} as BrowserWindow),backend:()=>({automation} as unknown as BackendClient)});
  return {invoke:(channel:string,input:unknown)=>handlers.get(`orvia:m18-${channel}`)!(input),automation,authorization};
}
beforeEach(()=>{vi.clearAllMocks();native.message.mockResolvedValue({response:1});native.open.mockResolvedValue({canceled:false,filePaths:['C:\\synthetic\\source.py']});});
describe('M18主进程一次性原生授权（native/backend mock）',()=>{
  it('伪造审批、错误会话/版本、重连旧授权不派发写入',async()=>{
    const c=context(()=>plan);
    await expect(c.invoke('script-execute',{id:cid,operation_id:oid,revision})).rejects.toThrow();
    expect(c.automation).not.toHaveBeenCalled();
    await c.invoke('script-preview',{id:cid,source:'pass',inputs:[]});
    await expect(c.invoke('script-execute',{id:randomUUID(),operation_id:oid,revision})).rejects.toThrow();
    await expect(c.invoke('script-execute',{id:cid,operation_id:oid,revision:'b'.repeat(64)})).rejects.toThrow();
    c.authorization.clear();
    await expect(c.invoke('script-execute',{id:cid,operation_id:oid,revision})).rejects.toThrow();
    expect(native.message).not.toHaveBeenCalled();
  });
  it('native取消绝不调用执行，renderer不能注入路径/解释器/approved',async()=>{
    const c=context(()=>plan);native.message.mockResolvedValue({response:0});
    await c.invoke('script-preview',{id:cid,source:'pass',inputs:[]});
    expect(await c.invoke('script-execute',{id:cid,operation_id:oid,revision})).toEqual({cancelled:true});
    expect(c.automation.mock.calls.map(x=>x[0])).toEqual(['script.preview']);
    for(const input of [{id:cid,inputs:[],path:'C:\\secret.py'},{id:cid,inputs:[],runtime:'powershell'},{id:cid,inputs:[],approved:true}])await expect(c.invoke('script-file',input)).rejects.toThrow();
    expect(native.open).not.toHaveBeenCalled();
  });
  it('真实pending重新取版本后才独立决定外发，取消变为approved false',async()=>{
    const pending={status:'awaiting_request',pending_request:{request_id:'actual',revision,url:'https://synthetic.example/message',method:'POST',fields:[{name:'text',value:'synthetic'}],bytes:9,sha256:revision,sensitive_redacted:false}};
    const c=context(suffix=>suffix==='browser.pending'?pending:{approved:false});
    const q={id:cid,session_id:'session',request_id:'actual',revision};
    await expect(c.invoke('browser-request',{...q,approved:true})).rejects.toThrow();
    await expect(c.invoke('browser-request',{...q,revision:'b'.repeat(64)})).rejects.toThrow();
    expect(native.message).not.toHaveBeenCalled();
    native.message.mockResolvedValue({response:0});
    expect(await c.invoke('browser-request',q)).toEqual({cancelled:true,result:{approved:false}});
    expect(c.automation).toHaveBeenLastCalledWith('browser.request',{...q,approved:false});
    const confirmation=native.message.mock.calls[0][1];expect(confirmation.message).toContain('POST https://synthetic.example/message');expect(confirmation.detail).toContain('text: synthetic');
  });
  it('站点类别只能通过原生确认授权，原生拒绝不会打开浏览器',async()=>{
    const c=context(()=>({}));native.message.mockResolvedValue({response:0});
    expect(await c.invoke('browser-open',{id:cid,url:'https://synthetic.example/',allowed_actions:['transaction'],get_write_paths:[]})).toEqual({cancelled:true});
    expect(c.automation).not.toHaveBeenCalled();
    await expect(c.invoke('browser-open',{id:cid,url:'https://synthetic.example/',allowed_actions:['transaction'],get_write_paths:[],origin_granted:true})).rejects.toThrow();
  });
  it('账本已取消的计划移除main批准身份，不再请求原生批准',async()=>{
    const c=context(suffix=>suffix==='cancel'?{operation_id:oid,revision,kind:'script',status:'cancelled',audit:{},created_at:'synthetic',updated_at:'synthetic'}:plan);
    await c.invoke('script-preview',{id:cid,source:'pass',inputs:[]});
    await c.invoke('cancel',{id:cid,operation_id:oid,revision});
    await expect(c.invoke('script-execute',{id:cid,operation_id:oid,revision})).rejects.toThrow();
    expect(native.message).not.toHaveBeenCalled();
    expect(c.automation.mock.calls.map(x=>x[0])).toEqual(['script.preview','cancel']);
  });
});
