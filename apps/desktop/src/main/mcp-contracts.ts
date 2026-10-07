import {z} from 'zod';
const hash=z.string().regex(/^[a-f0-9]{64}$/);
const name=z.string().min(1).max(100);
const text=(count:number)=>z.string().max(count*2).refine(value=>Array.from(value).length<=count);
type Json=string|number|boolean|null|Json[]|{[key:string]:Json};
/** 先用有界迭代检查深度，避免renderer或不可信服务器的深层数据耗尽JS递归栈。 */
function isJson(value:unknown):value is Json{
  const pending:{value:unknown;depth:number}[]=[{value,depth:0}],seen=new Set<object>();let nodes=0;
  while(pending.length){const item=pending.pop()!;if(item.depth>24||++nodes>16384)return false;const v=item.value;
    if(v===null||typeof v==='boolean')continue;
    if(typeof v==='number'){if(!Number.isFinite(v)||Math.abs(v)>Number.MAX_SAFE_INTEGER)return false;continue;}
    if(typeof v==='string'){if(/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/u.test(v))return false;continue;}
    if(typeof v!=='object'||seen.has(v))return false;seen.add(v);
    if(!Array.isArray(v)&&Object.getPrototypeOf(v)!==Object.prototype&&Object.getPrototypeOf(v)!==null)return false;
    const entries=Array.isArray(v)?v:Object.entries(v).flatMap(([key,val])=>[key,val]);if(entries.length>(Array.isArray(v)?128:256))return false;
    for(const child of entries)pending.push({value:child,depth:item.depth+1});
  }return true;
}
const json=z.custom<Json>(isJson,'MCP只支持有界有限JSON值');
/** 准确JSON预算拒绝非JSON值及非有限数字；总字节上限包含参数字段。 */
function bounded<T extends z.ZodTypeAny>(schema:T,bytes:number):z.ZodEffects<T>{return schema.refine((value:z.output<T>)=>new TextEncoder().encode(JSON.stringify(value)).byteLength<=bytes,'MCP数据超过运输预算') as z.ZodEffects<T>;}
export const mcpArguments=bounded(z.record(json).refine(isJson,'MCP参数结构超过有界JSON预算'),8192);
const object=bounded(z.record(json).refine(isJson,'MCP对象结构超过有界JSON预算'),32768);
export const mcpServerInput=z.object({server_id:z.string().uuid()}).strict();
export const mcpApprovalInput=mcpServerInput.extend({revision:hash}).strict();
export const mcpHistoryInput=z.object({id:z.string().uuid()}).strict();
export const mcpCallInput=mcpHistoryInput.extend({server_id:z.string().uuid(),tool:name,arguments:mcpArguments}).strict();
export const mcpCallApprovalInput=mcpHistoryInput.extend({server_id:z.string().uuid(),revision:hash}).strict();
export const mcpCredentialInput=mcpServerInput.extend({key:z.string().regex(/^[\x21-\x7e]{1,4096}$/)}).strict();
const configBase={name:text(80).refine(value=>value.trim().length>0),allowed_tools:z.array(name).max(16).refine(items=>new Set(items).size===items.length)};
export const mcpConfig=z.discriminatedUnion('transport',[
  z.object({...configBase,transport:z.literal('stdio'),executable:text(1000).refine(value=>/^[A-Za-z]:[\\/]/.test(value)&&/\.exe$/i.test(value)),args:z.array(text(1000)).max(16).refine(items=>new TextEncoder().encode(JSON.stringify(items)).byteLength<=8192),cwd:text(1000).refine(value=>/^[A-Za-z]:[\\/]/.test(value)).optional()}).strict(),
  z.object({...configBase,transport:z.literal('https'),url:z.string().url().max(2048).refine(value=>{try{const url=new URL(value);return url.protocol==='https:'&&!url.username&&!url.password&&!url.search&&!url.hash;}catch{return false;}})}).strict(),
]);
export const mcpServer=z.object({id:z.string().uuid(),name:text(80),transport:z.enum(['stdio','https']),revision:hash,status:z.enum(['configured','review_required','ready','disconnected','error']),tools_count:z.number().int().min(0).max(32),blocked_count:z.number().int().min(0).max(32),reason:text(200).nullable(),credential_configured:z.boolean()}).strict();
export const mcpList=bounded(z.object({servers:z.array(mcpServer).max(5)}).strict(),32768);
export const mcpConfigPreview=bounded(z.object({review_id:z.string().uuid(),revision:hash,config:mcpConfig}).strict(),32768);
export const mcpConnectPreview=bounded(z.object({server_id:z.string().uuid(),revision:hash,config:mcpConfig,identity:z.object({executable_hash:hash.nullable(),cwd:text(2048).nullable(),args_files:z.array(z.object({path:text(2048),sha256:hash,bytes:z.number().int().nonnegative()}).strict()).max(16)}).strict(),credential_configured:z.boolean(),purpose:z.literal('连接并发现 MCP 工具')}).strict(),32768);
export const mcpToolReview=bounded(z.object({server_id:z.string().uuid(),revision:hash,server_revision:hash,session_id:z.string().uuid(),server_info:object,capabilities:object,tools:z.array(z.object({name,metadata:object,allowed:z.boolean(),blocked_reason:text(200).nullable()}).strict()).max(32)}).strict(),32768);
export const mcpCallPreview=bounded(z.object({id:z.string().uuid(),server_id:z.string().uuid(),revision:hash,server_revision:hash,session_id:z.string().uuid(),server_name:text(80),tool:name,arguments:mcpArguments,metadata:object,purpose:z.literal('调用已审查的只读 MCP 工具')}).strict(),32768);
export const mcpExecution=bounded(z.object({id:z.string().uuid(),server_id:z.string().uuid(),revision:hash,server_name:text(80),tool:name,status:z.enum(['completed','failed','unknown','limited']),result:object.nullable(),error:z.object({code:z.string().max(100),message:text(200)}).strict().nullable()}).strict(),32768);
export const mcpHistory=bounded(z.object({executions:z.array(mcpExecution).max(16)}).strict(),32768);
export const mcpDisconnected=z.object({server_id:z.string().uuid(),closed:z.boolean(),children_reaped:z.boolean()}).strict();
export const mcpRemoved=z.object({server_id:z.string().uuid(),removed:z.literal(true)}).strict();
export type McpMethod='list'|'preview_config'|'configure'|'connect_preview'|'connect'|'approve_tools'|'call_preview'|'call'|'history'|'disconnect'|'remove'|'credential_replace';
export type McpServer=z.infer<typeof mcpServer>;
export type McpConfigPreview=z.infer<typeof mcpConfigPreview>;
export type McpConnectPreview=z.infer<typeof mcpConnectPreview>;
export type McpToolReview=z.infer<typeof mcpToolReview>;
export type McpCallPreview=z.infer<typeof mcpCallPreview>;
export type McpExecution=z.infer<typeof mcpExecution>;
export type McpHistory=z.infer<typeof mcpHistory>;
export type McpList=z.infer<typeof mcpList>;
export type McpDisconnected=z.infer<typeof mcpDisconnected>;
export type McpRemoved=z.infer<typeof mcpRemoved>;
export type McpCredentialStatus={encryption_available:boolean;configured:string[];loaded:boolean};
