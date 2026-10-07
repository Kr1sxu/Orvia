import {z} from 'zod';
import {synthesisFragmentSchema,synthesisCoverageSchema} from './chat-contracts';
const hash=z.string().regex(/^[a-f0-9]{64}$/);
const unicode=(value:string)=>!/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/u.test(value);
const text=(count:number)=>z.string().max(count*2).refine(value=>Array.from(value).length<=count&&unicode(value));
const nonempty=(count:number)=>text(count).refine(value=>value.trim().length>0&&!value.includes('\0'));
const utf8=(bytes:number)=>z.string().max(bytes).refine(value=>unicode(value)&&new TextEncoder().encode(value).byteLength<=bytes);
const url=text(2048).refine(value=>{try{const parsed=new URL(value);return['https:','http:'].includes(parsed.protocol)&&!parsed.username&&!parsed.password&&!/[\x00-\x20]/.test(value);}catch{return false;}},'只支持无用户凭据的准确HTTP/HTTPS地址');
const site=z.string().min(1).max(253).regex(/^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$/);
const source=z.object({kind:z.enum(['document','browser']),evidence_id:hash}).strict();
const sources=(count:number)=>z.array(source).max(count).refine(items=>new Set(items.map(item=>item.kind+':'+item.evidence_id)).size===items.length);
/** 用户只能给有界调研问题和范围；权限、路径、模型、请求方法与批准不接收renderer注入。 */
export const researchId=z.object({id:z.string().uuid()}).strict();
export const researchOperation=researchId.extend({operation_id:z.string().uuid()}).strict();
export const researchCreateInput=researchId.extend({question:nonempty(500),urls:z.array(url).max(10),queries:z.array(nonempty(200)).max(2),sites:z.array(site).max(5),sources:sources(3)}).strict();
export const researchPreviewInput=researchOperation.extend({stage:z.enum(['batch','final']),sources:sources(10).optional()}).strict();
export const researchGenerateInput=researchOperation.extend({stage:z.enum(['batch','final']),revision:hash}).strict();
function bounded<T extends z.ZodTypeAny>(schema:T,bytes:number):z.ZodEffects<T>{return schema.refine((value:z.output<T>)=>new TextEncoder().encode(JSON.stringify(value)).byteLength<=bytes,'调研响应超过运输预算') as z.ZodEffects<T>;}
const error=z.object({code:z.string().max(100),message:text(1000)}).strict().nullable();
const publication=z.object({message_id:z.string().uuid(),filename:text(255),format:z.enum(['docx','pptx','pdf']),revision:hash,source_revision:hash,pages:z.number().int().min(1),verified:z.literal(true)}).strict();
export const researchTask=bounded(z.object({id:z.string().uuid(),operation_id:z.string().uuid(),revision:hash,question:nonempty(500),urls:z.array(url).max(10),queries:z.array(nonempty(200)).max(2),sites:z.array(site).max(5),sources:sources(3),state:z.enum(['planned','collecting','collected','limited','generating','ready','cancelled','interrupted','failed']),pages:z.array(z.object({url,final_url:url.nullable(),state:z.enum(['running','ready','failed','duplicate','blocked']),evidence_id:hash.nullable(),error}).strict()).max(10),searches:z.array(z.object({query:nonempty(200),state:z.enum(['running','completed','failed','unavailable']),results:z.array(z.object({url,title:text(200)}).strict()).max(5),error}).strict()).max(2),batches:z.array(z.object({revision:hash,state:z.enum(['running','saved','failed','cancelled','interrupted']),answer:text(2200).nullable()}).strict()).max(4),final:z.object({revision:hash.nullable(),state:z.enum(['not_requested','running','saved','failed','cancelled','interrupted']),message_id:z.string().uuid().nullable()}).strict(),coverage:z.object({attempted_pages:z.number().int().min(0).max(10),ready_pages:z.number().int().min(0).max(10),search_rounds:z.number().int().min(0).max(2),search_unavailable:z.boolean(),distinct_final_pages:z.number().int().min(0).max(10),limitations:z.array(text(1000)).max(12)}).strict(),publications:z.array(publication).max(3),error}).strict(),49152);
export const researchHistory=bounded(z.object({tasks:z.array(researchTask).max(10),truncated:z.boolean()}).strict(),49152);
export const researchPacket=bounded(z.object({id:z.string().uuid(),operation_id:z.string().uuid(),stage:z.enum(['batch','final']),revision:hash,supplier:z.literal('Main · deepseek-flash · https://api.deepseek.com'),purpose:z.enum(['调研批次摘要','调研最终综合']),system:utf8(43008),input:utf8(43008),bytes:z.number().int().min(0).max(43008),fragments:z.array(synthesisFragmentSchema.extend({text:text(600)}).strict()).max(30),coverage:z.array(synthesisCoverageSchema.strict()).max(10),source_ids:sources(10),limits:z.object({input_bytes:z.literal(43008),timeout_seconds:z.literal(30),max_tokens:z.literal(4096)}).strict()}).strict().refine(value=>value.bytes===new TextEncoder().encode(value.system).byteLength+new TextEncoder().encode(value.input).byteLength,'准确系统说明/输入与发送字节不一致').refine(value=>value.purpose===(value.stage==='batch'?'调研批次摘要':'调研最终综合'),'批次与最终综合用途不对应'),49152);
export type ResearchMethod='create'|'collect'|'status'|'history'|'preview'|'generate'|'cancel';
export type ResearchTask=z.infer<typeof researchTask>;
export type ResearchHistory=z.infer<typeof researchHistory>;
export type ResearchPacket=z.infer<typeof researchPacket>;

export type ResearchResults={create:ResearchTask;collect:ResearchTask;status:ResearchTask;cancel:ResearchTask;generate:ResearchTask;history:ResearchHistory;preview:ResearchPacket};
