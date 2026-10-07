import {beforeEach,describe,it,expect,vi} from 'vitest';
import {randomUUID} from 'node:crypto';
import type {BackendClient} from '../src/main/backend';
import type {BrowserWindow} from 'electron';
const native=vi.hoisted(()=>({message:vi.fn()}));
vi.mock('electron',()=>({dialog:{showMessageBox:native.message}}));
import {registerResearch} from '../src/main/research-ipc';
import {researchCreateInput,researchPreviewInput,researchGenerateInput,researchOperation,researchTask,researchHistory,researchPacket} from '../src/main/research-contracts';

const cid=randomUUID(),oid=randomUUID(),revision='a'.repeat(64),source={kind:'document',evidence_id:'b'.repeat(64)};
const request={id:cid,question:'合成项目的公开进展',urls:['https://example.com/'],queries:['合成项目 进展'],sites:['example.com'],sources:[source]};
const task={...request,operation_id:oid,revision,state:'planned',pages:[],searches:[],batches:[],final:{revision:null,state:'not_requested',message_id:null},publications:[],coverage:{attempted_pages:0,ready_pages:0,search_rounds:0,search_unavailable:false,distinct_final_pages:0,limitations:[]},error:null};
const system='只依据准确原文和覆盖生成带引用答案。',input='合成资料原文。';
const packet={id:cid,operation_id:oid,stage:'final',revision,supplier:'Main · deepseek-flash · https://api.deepseek.com',purpose:'调研最终综合',system,input,bytes:new TextEncoder().encode(system+input).length,fragments:[{citation:'document:'+source.evidence_id+':1:1',kind:'document',evidence_id:source.evidence_id,locator:'第1段',unit:1,chunk:1,text:'合成资料原文。'}],coverage:[{kind:'document',evidence_id:source.evidence_id,title:'合成资料',accessed_at:null,selected_chunks:1,available_chunks:2,source_truncated:false,missing_units:[],ocr_available:false,ocr_selected:false}],source_ids:[source],limits:{input_bytes:43008,timeout_seconds:30,max_tokens:4096}};
const operation={id:cid,operation_id:oid},preview={...operation,stage:'final'},approval={...preview,revision};
function context(response:(method:string,params:Record<string,unknown>)=>unknown=method=>({create:task,status:task,collect:{...task,state:'collected'},preview:packet,generate:{...task,state:'ready',final:{revision,state:'saved',message_id:randomUUID()}},cancel:{...task,state:'cancelled'},history:{tasks:[task],truncated:false}}[method]),serial=<T>(fn:()=>Promise<T>)=>fn()){
  const handlers=new Map<string,(...args:unknown[])=>Promise<unknown>>(),research=vi.fn(async(method:string,params:Record<string,unknown>)=>response(method,params));
  const authorization=registerResearch({handle:(name,_count,fn)=>handlers.set(name,fn),serial,window:()=>({} as BrowserWindow),backend:()=>({research} as unknown as BackendClient)});
  return{research,authorization,invoke:(method:string,input:unknown)=>handlers.get('orvia:research-'+method)!(input)};
}
beforeEach(()=>{vi.clearAllMocks();native.message.mockResolvedValue({response:1});});

describe('V4-010调研准确范围与每批原生许可',()=>{
  it('renderer只接受固定范围，不接收路径、SQL、自由method、模型、批准或凭据',()=>{
    for(const [schema,value] of [[researchCreateInput,request],[researchPreviewInput,preview],[researchGenerateInput,approval],[researchOperation,operation]] as const){expect(schema.safeParse(value).success).toBe(true);for(const extra of [{path:'C:/private'},{sql:'SELECT *'},{method:'write'},{approved:true},{model:'other'},{credential:'synthetic'}])expect(schema.safeParse({...value,...extra}).success).toBe(false);}
  });
  it('问题按Unicode码点计500，拒空白/NUL/无效Unicode，不截断搜索原问',()=>{
    expect(researchCreateInput.parse({...request,question:'😀'.repeat(500)}).question).toHaveLength(1000);for(const question of ['😀'.repeat(501),' ','合成\0内容','\ud800'])expect(researchCreateInput.safeParse({...request,question}).success).toBe(false);expect(researchCreateInput.parse({...request,queries:['  原检索  ']}).queries).toEqual(['  原检索  ']);
  });
  it('准确公共URL最多十页、搜索两轮、站点五个，拒URL内凭据及非HTTP地址',()=>{
    expect(researchCreateInput.safeParse({...request,urls:Array.from({length:10},(_,i)=>`https://example.com/${i}`),queries:['一轮','二轮']}).success).toBe(true);
    for(const extra of [{urls:Array.from({length:11},()=>request.urls[0])},{queries:['一','二','三']},{queries:['汉'.repeat(201)]},{sites:Array.from({length:6},()=> 'example.com')},{urls:['https://user:secret@example.com/']},{urls:['file:///private']},{sites:['example.com/path']}])expect(researchCreateInput.safeParse({...request,...extra}).success).toBe(false);
  });
  it('本地来源最多三项且去重；模型发送最大十项、禁止任意kind与不准确identity',()=>{
    const sources=Array.from({length:10},(_,i)=>({kind:'browser',evidence_id:i.toString().repeat(64)}));expect(researchPreviewInput.safeParse({...preview,sources}).success).toBe(true);expect(researchPreviewInput.safeParse({...preview,sources:[...sources,source]}).success).toBe(false);for(const selected of [[source,source],[{kind:'filesystem',evidence_id:source.evidence_id}],[{kind:'document',evidence_id:'path'}],sources.slice(0,4)])expect(researchCreateInput.safeParse({...request,sources:selected}).success).toBe(false);
  });
  it('准确包固定Main和预算，实测UTF8必须等于bytes，stage/purpose不可错配',()=>{
    expect(researchPacket.parse(packet).bytes).toBe(packet.bytes);for(const extra of [{supplier:'Other'},{bytes:packet.bytes+1},{stage:'batch'},{limits:{...packet.limits,max_tokens:8192}},{input:'汉'.repeat(14337),system:'',bytes:43011},{system:'\ud800',input:'',bytes:3}])expect(researchPacket.safeParse({...packet,...extra}).success).toBe(false);
    const control='\u0001'.repeat(10000);expect(researchPacket.safeParse({...packet,input:control,system:'',bytes:10000}).success).toBe(false);
  });
  it('事实有界十页两轮十条历史与真实成品核验，不能把采集或缓存称业务完成',()=>{
    expect(researchTask.safeParse(task).success).toBe(true);expect(researchTask.safeParse({...task,state:'completed'}).success).toBe(false);expect(researchTask.safeParse({...task,pages:Array.from({length:11},()=>({url:request.urls[0],final_url:null,state:'failed',evidence_id:null,error:null}))}).success).toBe(false);expect(researchHistory.safeParse({tasks:Array.from({length:11},()=>task),truncated:false}).success).toBe(false);
    const receipt={message_id:randomUUID(),filename:'合成报告.docx',format:'docx',revision,source_revision:revision,pages:2,verified:true};expect(researchTask.safeParse({...task,publications:[receipt]}).success).toBe(true);expect(researchTask.safeParse({...task,publications:[{...receipt,verified:false}]}).success).toBe(false);
  });
  it('创建只保存实际规范化计划、不采集不调用模型；准确原问不可被替换',async()=>{
    const c=context(()=>({...task,question:'合成项目的公开进展',urls:['https://example.com/']}));await c.invoke('create',{...request,question:' 合成项目的公开进展 ',urls:['https://EXAMPLE.com']});expect(c.research.mock.calls.map(call=>call[0])).toEqual(['create']);expect(native.message).not.toHaveBeenCalled();
    const d=context(()=>({...task,question:'偷偷改变问题'}));await expect(d.invoke('create',request)).rejects.toThrow();await expect(d.invoke('collect',operation)).rejects.toThrow();
  });
  it('原生采集取消零collect/cloud，许可已消耗不能用历史或原包重放',async()=>{
    const c=context();await c.invoke('create',request);native.message.mockResolvedValueOnce({response:0});expect(await c.invoke('collect',operation)).toEqual({cancelled:true});await expect(c.invoke('collect',operation)).rejects.toThrow();expect(c.research.mock.calls.map(call=>call[0])).toEqual(['create','status']);const detail=native.message.mock.calls[0][1].detail;for(const accurate of ['example.com',request.queries[0],'Tavily','10个公共网页','两轮检索','120秒','不调用Main'])expect(detail).toContain(accurate);
  });
  it('Skill或历史planned只可重新核对完整计划，仍要新原生批准且已尝试拒绝',async()=>{
    const c=context();await expect(c.invoke('collect',operation)).rejects.toThrow();await c.invoke('review-collect',operation);expect(native.message).not.toHaveBeenCalled();native.message.mockResolvedValueOnce({response:0});expect(await c.invoke('collect',operation)).toEqual({cancelled:true});expect(c.research.mock.calls.map(call=>call[0])).toEqual(['status','status']);await expect(c.invoke('collect',operation)).rejects.toThrow();
    const d=context(()=>({...task,state:'collected'}));await expect(d.invoke('review-collect',operation)).rejects.toThrow('尚未尝试');expect(d.research.mock.calls.map(call=>call[0])).toEqual(['status']);
  });
  it('采集fresh完整范围比较，同revision新增URL也拒绝且不弹批准',async()=>{
    const c=context(method=>method==='create'?task:{...task,urls:['https://other.example/']});await c.invoke('create',request);await expect(c.invoke('collect',operation)).rejects.toThrow('已变化');expect(native.message).not.toHaveBeenCalled();expect(c.research.mock.calls.map(call=>call[0])).toEqual(['create','status']);await expect(c.invoke('collect',operation)).rejects.toThrow();
  });
  it('未预览、错会话、错版本不得generate；批准需准确完整system/input及供应商费用',async()=>{
    const c=context();await expect(c.invoke('generate',approval)).rejects.toThrow();await c.invoke('preview',preview);await expect(c.invoke('generate',{...approval,id:randomUUID()})).rejects.toThrow();await expect(c.invoke('generate',{...approval,revision:'f'.repeat(64)})).rejects.toThrow();await c.invoke('generate',approval);const detail=native.message.mock.calls[0][1].detail;for(const accurate of [system,input,source.evidence_id,'deepseek-flash','https://api.deepseek.com','42KiB','30秒','4096','费用','零自动重试'])expect(detail).toContain(accurate);expect(c.research.mock.calls.map(call=>call[0])).toEqual(['preview','preview','generate']);
  });
  it('每批原生取消零模型，并且不能自动沿用旧批准',async()=>{
    const c=context();await c.invoke('preview',preview);native.message.mockResolvedValueOnce({response:0});expect(await c.invoke('generate',approval)).toEqual({cancelled:true});await expect(c.invoke('generate',approval)).rejects.toThrow();expect(c.research.mock.calls.map(call=>call[0])).toEqual(['preview','preview']);
  });
  it('同revision正文或原文变化亦拒旧批准，明确选源不能被扩大',async()=>{
    let changed=false;const c=context(()=>changed?{...packet,input:input+'变',bytes:packet.bytes+3}:packet);await c.invoke('preview',preview);changed=true;await expect(c.invoke('generate',approval)).rejects.toThrow('已变化');expect(native.message).not.toHaveBeenCalled();
    const d=context(()=>packet);await expect(d.invoke('preview',{...preview,sources:[{kind:'browser',evidence_id:'c'.repeat(64)}]})).rejects.toThrow('不对应');await expect(d.invoke('generate',approval)).rejects.toThrow();
  });
  it('unknown或原生窗口异常消费许可且不重试，重连clear不恢复历史许可',async()=>{
    const c=context(method=>{if(method==='generate')throw Error('synthetic unknown');return packet;});await c.invoke('preview',preview);await expect(c.invoke('generate',approval)).rejects.toThrow('synthetic unknown');await expect(c.invoke('generate',approval)).rejects.toThrow();expect(c.research.mock.calls.map(call=>call[0])).toEqual(['preview','preview','generate']);
    const d=context();await d.invoke('preview',preview);native.message.mockRejectedValueOnce(Error('dialog unknown'));await expect(d.invoke('generate',approval)).rejects.toThrow();await expect(d.invoke('generate',approval)).rejects.toThrow();await d.invoke('create',request);d.authorization.clear();await expect(d.invoke('collect',operation)).rejects.toThrow();
  });
  it('status/history/cancel旁路长请求，不依赖serial释放；cancel撤销已有两种许可',async()=>{
    const c=context(undefined,async<T>(_fn:()=>Promise<T>)=>{throw Error('serial must not be used');});await c.invoke('status',operation);await c.invoke('history',{id:cid});await c.invoke('cancel',operation);expect(c.research.mock.calls.map(call=>call[0])).toEqual(['status','history','cancel']);
    const d=context();await d.invoke('create',request);await d.invoke('preview',preview);await d.invoke('cancel',operation);await expect(d.invoke('collect',operation)).rejects.toThrow();await expect(d.invoke('generate',approval)).rejects.toThrow();
  });
  it('batch与final独立准确包，不把摘要变成原文引用，限制二十条待审包',async()=>{
    const c=context((_method,params)=>({...packet,operation_id:params.operation_id,stage:params.stage,purpose:params.stage==='batch'?'调研批次摘要':'调研最终综合'}));await c.invoke('preview',preview);await c.invoke('preview',{...preview,stage:'batch'});native.message.mockResolvedValueOnce({response:0});await c.invoke('generate',{...approval,stage:'batch'});expect(native.message.mock.calls[0][1].detail).toContain('批摘要不能替代原文引用');native.message.mockResolvedValueOnce({response:0});await c.invoke('generate',approval);
    await c.invoke('preview',preview);for(let i=0;i<20;i++)await c.invoke('preview',{...preview,operation_id:randomUUID()});await expect(c.invoke('generate',approval)).rejects.toThrow();
  });
  it('原生弹窗等待期间cancel或重连撤销批准，后来点批准也零外发',async()=>{
    for(const mutation of ['cancel','clear']){
      const c=context();await c.invoke('preview',preview);let release!:(value:{response:number})=>void;let shown!:()=>void;const visible=new Promise<void>(resolve=>{shown=resolve;});native.message.mockImplementationOnce(()=>{shown();return new Promise(resolve=>{release=resolve;});});
      const sending=c.invoke('generate',approval);await visible;if(mutation==='cancel')await c.invoke('cancel',operation);else c.authorization.clear();release({response:1});await expect(sending).rejects.toThrow('撤销');expect(c.research.mock.calls.filter(call=>call[0]==='generate')).toHaveLength(0);
    }
    const c=context();await c.invoke('create',request);let release!:(value:{response:number})=>void;let shown!:()=>void;const visible=new Promise<void>(resolve=>{shown=resolve;});native.message.mockImplementationOnce(()=>{shown();return new Promise(resolve=>{release=resolve;});});const collecting=c.invoke('collect',operation);await visible;await c.invoke('cancel',operation);release({response:1});await expect(collecting).rejects.toThrow('撤销');expect(c.research.mock.calls.filter(call=>call[0]==='collect')).toHaveLength(0);
  });
  it('采集或生成返回另会话/任务不能当本次成功事实，已消费许可不再调用',async()=>{
    const c=context(method=>method==='collect'?{...task,id:randomUUID(),state:'collected'}:task);await c.invoke('create',request);await expect(c.invoke('collect',operation)).rejects.toThrow('返回采集事实');await expect(c.invoke('collect',operation)).rejects.toThrow();
    const d=context(method=>method==='generate'?{...task,operation_id:randomUUID(),state:'ready'}:packet);await d.invoke('preview',preview);await expect(d.invoke('generate',approval)).rejects.toThrow('返回生成事实');await expect(d.invoke('generate',approval)).rejects.toThrow();expect(d.research.mock.calls.filter(call=>call[0]==='generate')).toHaveLength(1);
  });
});
