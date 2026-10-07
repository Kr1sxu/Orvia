import {z} from 'zod';

/** 记忆入口只有本地身份与正文；来源、模型、路径、权限和批准均不能由 renderer 指定。 */
export const memoryId=z.object({id:z.string().uuid()}).strict();
export const memoryContextInput=memoryId.extend({query:z.string().max(400).refine(value=>Array.from(value).length<=200).optional()}).strict();
export const memoryGenerateInput=memoryId.extend({revision:z.string().regex(/^[a-f0-9]{64}$/)}).strict();
export const memorySearchInput=z.object({query:z.string().min(1).max(400).refine(value=>Array.from(value).length<=200)}).strict();
export const memoryForgetInput=memoryId.extend({memory_id:z.string().regex(/^[a-f0-9]{64}$/)}).strict();
export const memoryCorrectInput=memoryForgetInput.extend({value:z.string().min(1).max(600).refine(value=>Array.from(value).length<=300)}).strict();
export type MemoryMethod='list'|'context'|'preview'|'generate'|'search'|'correct'|'forget';

/** 运输预算按UTF-8实际字节检查，避免结构字段与多字节正文叠加越界。 */
function bounded<T extends z.ZodTypeAny>(schema:T,bytes:number):z.ZodEffects<T>{return schema.refine((value:z.output<T>)=>new TextEncoder().encode(JSON.stringify(value)).byteLength<=bytes,'记忆响应超过运输预算') as z.ZodEffects<T>;}

const hash=z.string().regex(/^[a-f0-9]{64}$/);
const text=(codepoints:number)=>z.string().max(codepoints*2).refine(value=>Array.from(value).length<=codepoints);
const utf8=(bytes:number)=>z.string().max(bytes).refine(value=>new TextEncoder().encode(value).byteLength<=bytes);
const sourceId=z.string().max(160).regex(/^(?:message:[a-f0-9-]{36}|document:[a-f0-9]{64}:\d{1,3}|browser:[a-f0-9]{64}:0)$/);
const sourceOrigin=z.string().max(160).regex(/^(?:message:[a-f0-9-]{36}|(?:document|browser):[a-f0-9]{64})$/);
export const memorySource=z.object({source_id:sourceId,quote:utf8(2048),status:z.enum(['user_statement','message','source_excerpt']),origin:sourceOrigin}).strict().refine(value=>value.source_id===value.origin||value.source_id.startsWith(value.origin+':'),'记忆原文定位与来源身份不一致');
const fact={id:hash,conversation_id:z.string().uuid(),kind:z.enum(['preference','person','project']),key:text(40),value:text(300),sources:z.array(memorySource).min(1).max(8)};
export const memoryCandidate=z.object({...fact,status:z.literal('candidate')}).strict();
export const memoryRecord=z.object({...fact,status:z.enum(['verified','conflict','revoked'])}).strict();
export const memoryRound=bounded(z.object({request_id:z.string().uuid(),status:z.string().max(64),messages:z.array(z.object({role:z.enum(['user','assistant','tool','system']),text:utf8(2048),kind:z.string().max(128),source_id:sourceId,truncated:z.boolean()}).strict()).max(100),truncated:z.boolean()}).strict(),4096);
export const memorySummary=bounded(z.object({revision:hash,items:z.array(z.object({text:text(600),source_ids:z.array(sourceId).min(1).max(4)}).strict()).max(12),sources:z.array(memorySource).max(150),statuses:z.array(z.object({request_id:z.string().uuid(),status:z.string().max(64)}).strict()).max(100)}).strict(),12288);
export const memoryList=bounded(z.object({candidates:z.array(memoryCandidate).max(20),memories:z.array(memoryRecord).max(20),summary_pending:z.boolean(),truncated:z.boolean()}).strict(),32768);
export const memoryContext=bounded(z.object({rounds:z.array(memoryRound).max(5),current:memoryRound.nullable(),summary:memorySummary.nullable(),memories:z.array(memoryRecord).max(10),truncated:z.boolean()}).strict(),24576);
export const memorySearch=bounded(z.object({memories:z.array(memoryRecord).max(10)}).strict(),16384);
export const memoryPreview=bounded(z.object({id:z.string().uuid(),revision:hash,supplier:z.literal('Main · deepseek-flash · https://api.deepseek.com'),purpose:z.literal('滚动摘要与长期记忆整理'),instructions:utf8(4096),rounds:z.array(memoryRound).max(10),candidates:z.array(memoryCandidate).max(16),input:bounded(z.object({rounds:z.array(memoryRound).max(10),candidates:z.array(memoryCandidate).max(16),previous_summary:memorySummary.nullable(),sources:z.array(memorySource).max(150)}).strict(),24576),bytes:z.number().int().nonnegative().max(24576)}).strict().refine(value=>value.bytes===new TextEncoder().encode(value.instructions).byteLength+new TextEncoder().encode(JSON.stringify(value.input)).byteLength,'实际发送正文与预览字节不一致'),32768);
export const memoryGenerated=memoryList;
export const memoryCorrected=memoryList;
export const memoryForgotten=memoryList;
export type MemorySource=z.infer<typeof memorySource>;
export type MemoryRecord=z.infer<typeof memoryRecord>;
export type MemoryCandidate=z.infer<typeof memoryCandidate>;
export type MemoryList=z.infer<typeof memoryList>;
export type MemoryContext=z.infer<typeof memoryContext>;
export type MemoryPreview=z.infer<typeof memoryPreview>;
export type MemorySearch=z.infer<typeof memorySearch>;
export type MemoryGenerated=z.infer<typeof memoryGenerated>;
export type MemoryCorrected=z.infer<typeof memoryCorrected>;
export type MemoryForgotten=z.infer<typeof memoryForgotten>;
