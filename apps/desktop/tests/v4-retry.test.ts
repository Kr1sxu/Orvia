import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {beforeEach,describe,it,expect,vi} from 'vitest';
import {randomUUID} from 'node:crypto';
import type {BackendClient} from '../src/main/backend';
import {retryId,retryAttempt,retryRun,retryHistory} from '../src/main/retry-contracts';
import {registerRetry} from '../src/main/retry-ipc';
import {RetryRecord,RetryPanel} from '../src/renderer/RetryPanel';

const cid=randomUUID(),started='2026-10-08T00:00:00.123456+00:00',finished='2026-10-08T00:00:01.123456+00:00';
const first={sequence:1,state:'failed',started_at:started,finished_at:finished,reason:'connect_before_send',delay_seconds:0,error_code:'CONNECT_ERROR'};
const second={sequence:2,state:'succeeded',started_at:finished,finished_at:finished,reason:'success',delay_seconds:0.1,error_code:null};
const run={business_id:randomUUID(),tool:'browser.static_read',parameter_digest:'a'.repeat(64),state:'succeeded',started_at:started,finished_at:finished,attempts:[first,second]};
const history={id:cid,runs:[run],truncated:false};
const forbidden=vi.hoisted(()=>({native:vi.fn(),model:vi.fn(),execute:vi.fn()}));
vi.mock('electron',()=>({dialog:{showOpenDialog:forbidden.native,showMessageBox:forbidden.native}}));
function context(response:unknown=history){const handlers=new Map<string,(...args:unknown[])=>Promise<unknown>>(),read=vi.fn(async()=>response);registerRetry({handle:(name,_count,fn)=>handlers.set(name,fn),backend:()=>({retryHistory:read,chatSend:forbidden.model,execute:forbidden.execute} as unknown as BackendClient)});return{handlers,read,invoke:(input:unknown)=>handlers.get('orvia:retry-history')!(input)};}
beforeEach(()=>{vi.clearAllMocks();});

describe('V4-011仅本机只读的安全读取重试事实',()=>{
  it('输入仅准确会话UUID，不接工具分类、URL、正文、SQL、路径、密钥或写许可',()=>{
    expect(retryId.parse({id:cid})).toEqual({id:cid});for(const extra of [{tool:'mcp.read'},{classification:'safe'},{url:'https://example.com'},{body:'合成正文'},{sql:'select *'},{path:'C:/private'},{credential:'synthetic'},{approved:true},{attempts:[]}])expect(retryId.safeParse({id:cid,...extra}).success).toBe(false);for(const id of ['','other',7,null])expect(retryId.safeParse({id}).success).toBe(false);
  });
  it('只允许程序固定静态读/SQLite读，MCP/动态GET/模型/Shell/进程声明不能授予资格',()=>{
    expect(retryRun.parse(run).tool).toBe('browser.static_read');expect(retryRun.safeParse({...run,tool:'context.sqlite_read'}).success).toBe(true);for(const tool of ['mcp.read','browser.dynamic_get','model.generate','shell.execute','process.wait','file.move'])expect(retryRun.safeParse({...run,tool}).success).toBe(false);expect(retryRun.safeParse({...run,readOnlyHint:true}).success).toBe(false);
  });
  it('输出只有业务身份与参数sha，不返回URL/正文/凭据或伪造verified/completed',()=>{
    for(const extra of [{url:'https://example.com'},{request_body:'正文'},{credential:'synthetic'},{verified:true},{completed:true}])expect(retryRun.safeParse({...run,...extra}).success).toBe(false);for(const business_id of ['https://example.com','../private/leaf','\u0000','汉'.repeat(4),'a'.repeat(129)])expect(retryRun.safeParse({...run,business_id}).success).toBe(false);for(const parameter_digest of ['path','F'.repeat(64),'a'.repeat(63)])expect(retryRun.safeParse({...run,parameter_digest}).success).toBe(false);
  });
  it('尝试最多三次、序号从一连续且不重用，有界等待不得越过0.5秒',()=>{
    expect(retryRun.safeParse({...run,attempts:[first,second,{...second,sequence:3}]}).success).toBe(true);for(const attempts of [[second],[first,first],[first,{...second,sequence:3}],[first,second,{...second,sequence:3},{...second,sequence:4}]])expect(retryRun.safeParse({...run,attempts}).success).toBe(false);for(const delay_seconds of [-1,0.51,NaN,Infinity])expect(retryAttempt.safeParse({...first,delay_seconds}).success).toBe(false);
  });
  it('全部完成或未批准不是合法attempt状态，未知只作停止事实',()=>{
    for(const state of ['completed','approved','goal_complete']){expect(retryRun.safeParse({...run,state}).success).toBe(false);expect(retryAttempt.safeParse({...first,state}).success).toBe(false);}for(const reason of ['MCP says safe','retry_all','authentication','formatted_wrong'])expect(retryAttempt.safeParse({...first,reason}).success).toBe(false);for(const error_code of ['Secret: value','https://example.com','a'.repeat(65),'lowercase','A\nB'])expect(retryAttempt.safeParse({...first,error_code}).success).toBe(false);
  });
  it('时间是有界ISO UTC/offset事实，运行中可无结束时间，不接无时区或任意正文',()=>{
    expect(retryRun.safeParse({...run,state:'running',finished_at:null,attempts:[{...first,state:'running',finished_at:null}]}).success).toBe(true);for(const started_at of ['yesterday','2026-10-08T00:00:00','用户私人正文','2026-13-08T00:00:00Z'])expect(retryAttempt.safeParse({...first,started_at}).success).toBe(false);
  });
  it('历史最多32业务且执行真实UTF8/JSON32KiB预算，不按条数冒充大小限制',()=>{
    expect(retryHistory.safeParse({id:cid,runs:Array.from({length:32},()=>({...run,attempts:[]})),truncated:true}).success).toBe(true);expect(retryHistory.safeParse({id:cid,runs:Array.from({length:33},()=>run),truncated:false}).success).toBe(false);const heavy={...run,business_id:'a'.repeat(128),attempts:Array.from({length:3},(_,index)=>({...first,sequence:index+1,error_code:'A'.repeat(64)}))};const over={id:cid,runs:Array.from({length:32},()=>heavy),truncated:false};expect(new TextEncoder().encode(JSON.stringify(over)).length).toBeGreaterThan(32768);expect(retryHistory.safeParse(over).success).toBe(false);
  });
  it('只有一个本机history固定handler，查询不弹原生、不调用模型、不执行业务',async()=>{
    const c=context();expect([...c.handlers.keys()]).toEqual(['orvia:retry-history']);expect(await c.invoke({id:cid})).toEqual(history);expect(c.read).toHaveBeenCalledOnce();expect(c.read).toHaveBeenCalledWith({id:cid});expect(forbidden.native).not.toHaveBeenCalled();expect(forbidden.model).not.toHaveBeenCalled();expect(forbidden.execute).not.toHaveBeenCalled();
  });
  it('非法输入在调用后端前拒绝，跨会话返回即拒绝且不显示他会话事实',async()=>{
    const c=context();await expect(c.invoke({id:cid,url:'https://example.com'})).rejects.toThrow();expect(c.read).not.toHaveBeenCalled();const d=context({...history,id:randomUUID()});await expect(d.invoke({id:cid})).rejects.toThrow('会话不对应');expect(d.read).toHaveBeenCalledOnce();
  });
  it('后端malformed不能补造成功，状态读取失败不重放',async()=>{
    const c=context({...history,runs:[{...run,state:'goal_complete'}]});await expect(c.invoke({id:cid})).rejects.toThrow();const d=context();d.read.mockRejectedValueOnce(Error('synthetic disconnected'));await expect(d.invoke({id:cid})).rejects.toThrow('synthetic disconnected');expect(d.read).toHaveBeenCalledOnce();expect(forbidden.execute).not.toHaveBeenCalled();
  });
  it('视图逐次显示工具/业务/序号/错误/时间/等待/终态原因，成功不称全目标完成',()=>{
    const html=renderToStaticMarkup(React.createElement(RetryRecord,{run:retryRun.parse(run)}));for(const expected of [run.business_id,run.tool,run.parameter_digest,'第 1 次','第 2 次','CONNECT_ERROR','发送前连接失败',started,'0.1','收到成功结果','读取尝试已结束，不代表全任务完成','逐项目标证据核验'])expect(html).toContain(expected);expect(html).not.toContain('全部目标已完成');expect(html).not.toContain('<button');
  });
  it('只读面板明确上限与排除范围、现有取消入口，不提供自动重试所有请求开关',()=>{
    const html=renderToStaticMarkup(React.createElement(RetryPanel));for(const expected of ['最多三次尝试','原请求总预算','MCP','未知结果不自动重试','所属任务已有取消入口','重试记录所属会话','刷新安全读取重试记录'])expect(html).toContain(expected);expect(html).not.toContain('自动重试所有请求');expect(html).not.toContain('type="checkbox"');
  });
});

it('发送后未知状态是实际终态而非成功，面板明确不自动重试',()=>{const record={...run,state:'unknown' as const,attempts:[{...first,state:'unknown' as const,reason:'not_retryable' as const,error_code:'NETWORK_UNKNOWN'}]};expect(retryRun.parse(record).state).toBe('unknown');const html=renderToStaticMarkup(React.createElement(RetryRecord,{run:retryRun.parse(record)}));expect(html).toContain('结果未知，未重试');expect(html).toContain('NETWORK_UNKNOWN');expect(html).not.toContain('全部目标已完成');});

it('真实用户接受限制及逐目标汇总消息可经过后端快照契约，不能伪装工具成功',async()=>{const {chatMessageSchema}=await import('../src/main/chat-contracts');const base={id:randomUUID(),role:'user' as const,text:'接受有限结果',created_at:started,data:{request_id:cid,position:0,step_revision:'a'.repeat(64),continuation_id:randomUUID()}};expect(chatMessageSchema.parse({...base,kind:'task_acceptance'}).kind).toBe('task_acceptance');expect(chatMessageSchema.parse({...base,role:'assistant',kind:'task_summary',text:'仅部分目标已经核验'}).kind).toBe('task_summary');expect(chatMessageSchema.safeParse({...base,kind:'all_goals_verified'}).success).toBe(false);});
