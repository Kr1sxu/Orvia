import {describe,it,expect,vi,beforeEach} from 'vitest';
import type {BackendClient} from '../src/main/backend';
import type {BrowserWindow} from 'electron';
const native=vi.hoisted(()=>({open:vi.fn(),message:vi.fn()}));
vi.mock('electron',()=>({dialog:{showOpenDialog:native.open,showMessageBox:native.message}}));
import {registerSkills} from '../src/main/skills-ipc';
const cid='a1234567-1234-4234-8234-123456789abc',plan={plan_id:'b1234567-1234-4234-8234-123456789abc',revision:'a'.repeat(64),mission_id:cid,grant_id:null,steps:[{tool:'memory_context'}]};
function context(){
  const handlers=new Map<string,(...args:unknown[])=>Promise<unknown>>();
  const skills=vi.fn(async(method:string)=>method==='plan'?plan:{status:'completed'});
  const chat=vi.fn(async()=>({id:cid})),grant=vi.fn(),mission=vi.fn();
  registerSkills({handle:(channel,_count,action)=>handlers.set(channel,action),serial:async action=>action(),window:()=>({} as BrowserWindow),backend:()=>({skills,chat,grantComputer:grant,createMission:mission} as unknown as BackendClient)});
  return{skills,chat,grant,mission,run:(input:unknown)=>handlers.get('orvia:skills-run')!(input)};
}
beforeEach(()=>{vi.clearAllMocks();native.message.mockResolvedValue({response:1});native.open.mockRejectedValue(new Error('本地流程不得选择目录'));});
describe('V4-006 本地Skills独立原生计划与文件授权边界',()=>{
  it('明确会话只读组合不创建目录grant或任务，计划准确展示并批准后执行',async()=>{
    const c=context(),inputs={query:'合成问题',revision:''};
    expect(await c.run({skill_id:'query-rewrite',inputs,conversation_id:cid})).toEqual({cancelled:false,result:{status:'completed'}});
    expect(c.chat).toHaveBeenCalledWith('chat.get',{id:cid});expect(c.skills).toHaveBeenNthCalledWith(1,'plan',{skill_id:'query-rewrite',inputs,mission_id:cid,grant_id:null});
    expect(c.skills).toHaveBeenNthCalledWith(2,'execute',{plan_id:plan.plan_id,revision:plan.revision,mission_id:cid,grant_id:null});
    expect(native.message.mock.calls[0]![1].detail).toContain(JSON.stringify(plan,null,2));
    expect(native.open).not.toHaveBeenCalled();expect(c.grant).not.toHaveBeenCalled();expect(c.mission).not.toHaveBeenCalled();
  });
  it('取消记录计划中断、零execute；原生窗口异常也不得执行',async()=>{
    const c=context();native.message.mockResolvedValueOnce({response:0});
    expect(await c.run({skill_id:'memory-context',inputs:{query:'合成'},conversation_id:cid})).toEqual({cancelled:true});
    expect(c.skills.mock.calls.map(call=>call[0])).toEqual(['plan','cancel']);
    const d=context();native.message.mockRejectedValueOnce(new Error('dialog interrupted'));
    await expect(d.run({skill_id:'memory-context',inputs:{query:'合成'},conversation_id:cid})).rejects.toThrow();expect(d.skills.mock.calls.map(call=>call[0])).toEqual(['plan']);
  });
  it('会话不存在或后端拒绝含文件叶时不弹批准，不容renderer注入grant',async()=>{
    const c=context();c.chat.mockRejectedValueOnce(new Error('NOT_FOUND'));
    await expect(c.run({skill_id:'memory-context',inputs:{query:'合成'},conversation_id:cid})).rejects.toThrow();expect(c.skills).not.toHaveBeenCalled();
    const d=context();d.skills.mockRejectedValueOnce(new Error('SKILL_GRANT'));
    await expect(d.run({skill_id:'file-organize',inputs:{path:'.'},conversation_id:cid})).rejects.toThrow();expect(native.message).not.toHaveBeenCalled();
    await expect(d.run({skill_id:'memory-context',inputs:{query:'合成'},conversation_id:cid,grant_id:null})).rejects.toThrow();
  });
});
