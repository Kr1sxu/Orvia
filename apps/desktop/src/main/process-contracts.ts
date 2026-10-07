import {z} from 'zod';
const hash=z.string().regex(/^[a-f0-9]{64}$/);
const unicode=(value:string)=>!/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/u.test(value);
const text=(count:number)=>z.string().max(count*2).refine(value=>Array.from(value).length<=count&&unicode(value));
const args=z.array(text(1000).refine(value=>!value.includes('\0'))).max(16).refine(value=>new TextEncoder().encode(JSON.stringify(value)).byteLength<=8192);
const wait=z.number().int().min(1).max(15).default(3);
const pid=z.number().int().min(1).max(4294967295);
const created=z.number().finite().positive();
const ticks=z.string().regex(/^[0-9]{1,20}$/);
/** Renderer只提交有限身份与参数；exe、cwd、权限、批准和自由系统方法均不接受外部指定。 */
export const processId=z.object({id:z.string().uuid()}).strict();
export const processOperation=processId.extend({operation_id:z.string().uuid()}).strict();
export const processApproval=processOperation.extend({revision:hash}).strict();
export const processLaunchInput=processId.extend({args,choose_cwd:z.boolean(),wait_seconds:wait}).strict();
export const processActionInput=processId.extend({action:z.enum(['wait','close','terminate']),pid,create_time:created,creation_ticks:ticks,wait_seconds:wait}).strict();
function bounded<T extends z.ZodTypeAny>(schema:T,bytes:number):z.ZodEffects<T>{return schema.refine((value:z.output<T>)=>new TextEncoder().encode(JSON.stringify(value)).byteLength<=bytes,'进程响应超过运输预算') as z.ZodEffects<T>;}
export const processIdentity=z.object({pid,create_time:created,creation_ticks:ticks,name:text(260),executable:text(2048),sha256:hash}).strict();
export const processList=bounded(z.object({processes:z.array(processIdentity).max(50),truncated:z.boolean(),unavailable_reason:text(1000).nullable()}).strict(),49152);
export const processPreview=bounded(z.object({id:z.string().uuid(),operation_id:z.string().uuid(),revision:hash,action:z.enum(['launch','wait','close','terminate']),target:processIdentity.nullable(),launch:z.object({name:text(260),executable:text(2048),args,cwd:text(2048),sha256:hash}).strict().nullable(),wait_seconds:z.number().int().min(1).max(15),purpose:text(200),risk:text(1000)}).strict().refine(value=>value.action==='launch'?value.target===null&&value.launch!==null:value.target!==null&&value.launch===null,'进程预览动作与准确目标类型不对应'),49152);
export const processExecution=bounded(z.object({id:z.string().uuid(),operation_id:z.string().uuid(),revision:hash,action:z.enum(['launch','wait','close','terminate']),status:z.enum(['running','exited','still_running','unknown','failed']),target:processIdentity.nullable(),exit_code:z.number().int().nullable(),started_at:text(100),finished_at:text(100).nullable(),verified:z.boolean(),close_sent:z.boolean(),error:z.object({code:z.string().max(100),message:text(1000)}).strict().nullable()}).strict(),49152);
export const processHistory=bounded(z.object({executions:z.array(processExecution).max(10),truncated:z.boolean()}).strict(),49152);
export type ProcessMethod='list'|'preview_launch'|'preview_action'|'review'|'execute'|'status'|'history';
export type ProcessIdentity=z.infer<typeof processIdentity>;
export type ProcessList=z.infer<typeof processList>;
export type ProcessPreview=z.infer<typeof processPreview>;
export type ProcessExecution=z.infer<typeof processExecution>;
export type ProcessHistory=z.infer<typeof processHistory>;
