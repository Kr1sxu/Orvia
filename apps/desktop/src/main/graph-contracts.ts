import {z} from 'zod';

/** Renderer 只指定本地身份和有界问题，不能注入来源、SQL、权限或模型配置。 */
export const graphId=z.object({id:z.string().uuid()}).strict();
const hash=z.string().regex(/^[a-f0-9]{64}$/);
const text=(codepoints:number)=>z.string().max(codepoints*2).refine(value=>Array.from(value).length<=codepoints);
const utf8=(bytes:number)=>z.string().max(bytes).refine(value=>new TextEncoder().encode(value).byteLength<=bytes);
export const graphGenerateInput=graphId.extend({revision:hash}).strict();
export const graphQueryInput=z.object({query:text(200).refine(value=>value.length>0),entity_id:hash.optional(),hops:z.union([z.literal(1),z.literal(2)]).optional()}).strict();
export type GraphMethod='list'|'preview'|'generate'|'query';

/** 实际 JSON 字节预算同时约束正文与结构，不以记录条数代替运输上限。 */
function bounded<T extends z.ZodTypeAny>(schema:T,bytes:number):z.ZodEffects<T>{return schema.refine((value:z.output<T>)=>new TextEncoder().encode(JSON.stringify(value)).byteLength<=bytes,'图谱响应超过运输预算') as z.ZodEffects<T>;}
const evidenceIdentity='(?:[a-f0-9]{64}|[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})';
const origin=z.string().max(150).regex(new RegExp(`^(?:message:[a-f0-9-]{36}|(?:document|browser):${evidenceIdentity})$`));
const sourceId=z.string().max(160).regex(new RegExp(`^(?:message:[a-f0-9-]{36}|document:${evidenceIdentity}:\\d{1,6}|browser:${evidenceIdentity}:0)$`));
export const graphSource=z.object({source_id:sourceId,origin,quote:utf8(2048),version:hash,status:z.enum(['user_statement','source_excerpt'])}).strict().refine(value=>value.source_id===value.origin||value.source_id.startsWith(value.origin+':'),'图谱原文定位与来源身份不对应');
export const graphEntity=z.object({id:hash,conversation_id:z.string().uuid(),scope:origin,kind:z.enum(['person','project','file']),name:text(100).refine(value=>value.length>0),status:z.enum(['verified','revoked']),sources:z.array(graphSource).min(1).max(8)}).strict().refine(value=>value.sources.every(source=>source.origin===value.scope&&source.version===value.sources[0]!.version),'实体身份与支持来源范围或版本不对应');
export const graphRelation=z.object({id:hash,conversation_id:z.string().uuid(),from_id:hash,to_id:hash,kind:z.enum(['responsible_for','member_of','documents','depends_on']),status:z.enum(['verified','conflict','revoked']),sources:z.array(graphSource).min(1).max(8)}).strict();
export const graphList=bounded(z.object({entities:z.array(graphEntity).max(20),relations:z.array(graphRelation).max(20),truncated:z.boolean()}).strict(),32768);
export const graphPreview=bounded(z.object({id:z.string().uuid(),revision:hash,supplier:z.literal('deepseek-flash @ https://api.deepseek.com'),purpose:z.literal('实体关系抽取'),instructions:utf8(4096),input:bounded(z.object({sources:z.array(graphSource).max(16)}).strict(),24576),bytes:z.number().int().nonnegative().max(24576),truncated:z.boolean()}).strict().refine(value=>value.bytes===new TextEncoder().encode(value.instructions).byteLength+new TextEncoder().encode(JSON.stringify(value.input)).byteLength,'实际发送正文与预览字节不一致'),32768);
export const graphPath=z.object({entities:z.array(graphEntity).min(2).max(3),relations:z.array(graphRelation).min(1).max(2)}).strict().refine(value=>value.entities.length===value.relations.length+1&&value.relations.every((relation,index)=>{
  const a=value.entities[index]!,b=value.entities[index+1]!;
  return relation.status==='verified'&&a.status==='verified'&&b.status==='verified'&&relation.from_id===a.id&&relation.to_id===b.id;
}),'图谱路径长度、有效支持或相邻实体不对应');
export const graphQuery=bounded(z.object({entities:z.array(graphEntity).max(20),paths:z.array(graphPath).max(20),ambiguous:z.boolean(),truncated:z.boolean()}).strict().refine(value=>!value.ambiguous||value.paths.length===0,'同名实体未消歧时不能生成查询路径'),32768);
export type GraphSource=z.infer<typeof graphSource>;
export type GraphEntity=z.infer<typeof graphEntity>;
export type GraphRelation=z.infer<typeof graphRelation>;
export type GraphList=z.infer<typeof graphList>;
export type GraphPreview=z.infer<typeof graphPreview>;
export type GraphQuery=z.infer<typeof graphQuery>;
