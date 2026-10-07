import {z} from 'zod';
import {memorySource} from './memory-contracts';
import {retrievalResult} from './retrieval-contracts';

const hash=z.string().regex(/^[a-f0-9]{64}$/);
const text=(count:number)=>z.string().max(count*2).refine(value=>Array.from(value).length<=count);
const query=text(200).refine(value=>value.trim().length>0);
const utf8=(bytes:number)=>z.string().max(bytes).refine(value=>new TextEncoder().encode(value).byteLength<=bytes);
/** 查询入口只允许身份、原问题与明确选中的记忆；不能提交路径、来源正文或模型批准。 */
export const rewriteId=z.object({id:z.string().uuid()}).strict();
export const rewritePreviewInput=rewriteId.extend({query,memory_ids:z.array(hash).max(3).refine(value=>new Set(value).size===value.length).optional()}).strict();
export const rewriteGenerateInput=rewriteId.extend({revision:hash}).strict();
export const rewriteSearchInput=rewritePreviewInput.extend({revision:hash.optional()}).strict();
export type RewriteMethod='preview'|'generate'|'search'|'history';

/** UTF-8预算同时检查正文和JSON结构，防止合法单项组合后突破运输预算。 */
function bounded<T extends z.ZodTypeAny>(schema:T,bytes:number):z.ZodEffects<T>{return schema.refine((value:z.output<T>)=>new TextEncoder().encode(JSON.stringify(value)).byteLength<=bytes,'改写响应超过运输预算') as z.ZodEffects<T>;}
const evidence= retrievalResult.shape.evidence.element;
const identity='(?:[a-f0-9]{64}|[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})';
const scope=z.string().max(150).regex(new RegExp(`^(?:document|browser):${identity}(?::\\d+)?$`));
const basis=z.string().max(100).regex(/^(?:memory:[a-f0-9]{64}|fragment:\d+)$/);
const candidate=z.object({query,source_ids:z.array(basis).max(8)}).strict();
const memory=z.object({id:hash,conversation_id:z.string().uuid(),kind:z.enum(['preference','person','project']),key:text(40),value:text(300),sources:z.array(memorySource).min(1).max(8)}).strict();
export const rewritePreview=bounded(z.object({id:z.string().uuid(),revision:hash,supplier:z.literal('Main · deepseek-flash · https://api.deepseek.com'),purpose:z.literal('检索查询改写'),instructions:utf8(4096),
  input:bounded(z.object({original:query,memories:z.array(memory).max(3),fragments:z.array(evidence).max(5),scope:z.array(scope).max(150),scope_revision:hash,allowed_candidates:z.array(candidate).max(3)}).strict(),24576),bytes:z.number().int().nonnegative().max(24576),status:z.enum(['ready','clarification']),reason:text(200).nullable()
}).strict().refine(value=>value.bytes===new TextEncoder().encode(value.instructions).byteLength+new TextEncoder().encode(JSON.stringify(value.input)).byteLength,'准确发送正文与字节数不一致'),32768);
export const rewriteResult=bounded(z.object({id:z.string().uuid(),original:query,candidates:z.array(candidate).max(3),status:z.enum(['rewritten','original','clarification']),reason:text(200).nullable(),revision:hash.nullable()}).strict().refine(value=>value.status==='rewritten'?value.candidates.length>0:value.candidates.length===0,'未改写或未消歧结果不能附带候选查询'),8192);
export const rewriteHistory=bounded(z.object({records:z.array(rewriteResult).max(20)}).strict(),32768);
export const rewriteSearch=bounded(z.object({id:z.string().uuid(),original:query,queries:z.array(query).min(1).max(4),rewrite:rewriteResult,evidence:z.array(evidence).max(5),truncated:z.boolean()}).strict().refine(value=>value.rewrite.id===value.id&&value.rewrite.original===value.original&&value.queries[0]===value.original&&value.queries.every((item,index)=>index===0||value.rewrite.candidates.some(candidate=>candidate.query===item))&&new Set(value.queries).size===value.queries.length,'检索必须保留同会话原问题且仅使用已记录候选'),32768);
export type RewritePreview=z.infer<typeof rewritePreview>;
export type RewriteResult=z.infer<typeof rewriteResult>;
export type RewriteSearch=z.infer<typeof rewriteSearch>;
export type RewriteHistory=z.infer<typeof rewriteHistory>;
