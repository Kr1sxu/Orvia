import {z} from 'zod';

const id=z.string().uuid(),evidence=z.string().regex(/^[a-f0-9]{64}$/);
/** M20只接收请求身份、文字和已保存资料身份；原生授权与业务审批仍走既有固定接口。 */
export const naturalInput=z.object({id,request_id:id,text:z.string().trim().min(1).max(2000)}).strict();
export const continuationInput=z.object({id,request_id:id,continuation_id:id,answer:z.string().trim().min(1).max(2000).optional()}).strict();
export const materialRemoveInput=z.object({id,kind:z.enum(['document','browser']),evidence_id:evidence}).strict();
export const revokeInput=z.object({id}).strict();
export const scanPageInput=z.object({id,scan_id:id,offset:z.number().int().min(0).max(5000).default(0)}).strict();
export const streamPullInput=z.object({id,request_id:id,after_seq:z.number().int().min(0).max(100000).default(0),limit:z.literal(40).optional()}).strict();
export const streamAckInput=z.object({id,request_id:id,seq:z.number().int().min(0).max(100000)}).strict();
export const attachmentInput=z.object({id,request_id:id}).strict();
export const workflowSchema=z.object({request_id:id,continuation_id:id,state:z.enum(['waiting_input','waiting_approval','running']),reason:z.string().max(1000),action:z.enum(['directory','materials','clarification','synthesis','stream_fallback','publication','development','cleanup','script','desktop','browser','files','task_decision','none']),question:z.string().max(2000),choices:z.array(z.object({id:z.string().max(128),label:z.string().max(300)}).strict()).max(20).optional(),input:z.record(z.unknown()).optional()}).strict();
export const fallbackConfirmInput=z.object({id,request_id:id,continuation_id:id}).strict();
export type Workflow=z.infer<typeof workflowSchema>;
export const materialSchema=z.object({kind:z.enum(['document','browser']),evidence_id:evidence,title:z.string().max(300),status:z.enum(['ready','failed'])}).strict();
export const streamStateSchema=z.object({request_id:id,stream_id:id,last_seq:z.number().int().min(0),state:z.string().max(30)}).strict();
export const scanEntrySchema=z.object({path:z.string().max(1000),name:z.string().max(300).optional(),kind:z.enum(['file','directory']),size:z.number().int().min(0),modified_at:z.string().max(100).optional(),category:z.string().max(100)}).strict();
export const scanPageSchema=z.object({scan_id:id,entries:z.array(scanEntrySchema).max(100),offset:z.number().int().min(0),next_offset:z.number().int().min(0).nullable(),total:z.number().int().min(0).max(5000),summary:z.record(z.unknown())}).strict();
export type ScanPage=z.infer<typeof scanPageSchema>;
export type ScanEntry=z.infer<typeof scanEntrySchema>;
const streamIdentity={v:z.literal(1),event:z.literal('chat.stream'),id,conversation_id:id,request_id:id,stream_id:id,seq:z.number().int().min(1).max(100000)};
const label=z.object({label:z.string().max(1000)}).strict();
/** 每类payload严格限定；含最终信封及换行不超过12KiB，stdio仍执行64KiB总帧边界。 */
export const streamEventSchema=z.discriminatedUnion('kind',[
  z.object({...streamIdentity,kind:z.literal('started'),payload:label}).strict(),
  z.object({...streamIdentity,kind:z.literal('tool_status'),payload:z.object({stage:z.string().max(100),label:z.string().max(1000)}).strict()}).strict(),
  z.object({...streamIdentity,kind:z.literal('scan_batch'),payload:z.object({scan_id:id,entries:z.array(scanEntrySchema).max(40),discovered:z.number().int().min(0).max(5000),visited:z.number().int().min(0).max(5000)}).strict()}).strict(),
  z.object({...streamIdentity,kind:z.literal('model_delta'),payload:z.object({text:z.string().max(8000),provisional:z.literal(true)}).strict()}).strict(),
  z.object({...streamIdentity,kind:z.literal('paused'),payload:z.object({action:z.string().max(40),question:z.string().max(2000)}).strict()}).strict(),
  z.object({...streamIdentity,kind:z.literal('completed'),payload:label}).strict(),
  z.object({...streamIdentity,kind:z.literal('failed'),payload:z.object({code:z.string().max(100),message:z.string().max(1000)}).strict()}).strict(),
  z.object({...streamIdentity,kind:z.literal('cancelled'),payload:label}).strict(),
]).refine(value=>new TextEncoder().encode(JSON.stringify(value)+'\n').length<=12*1024,'事件超过帧预算');
export type StreamEvent=z.infer<typeof streamEventSchema>;
export const streamPullSchema=z.object({events:z.array(streamEventSchema).max(40),last_seq:z.number().int().min(0),terminal:z.boolean(),gap:z.boolean().optional()}).strict();
export type StreamPull=z.infer<typeof streamPullSchema>;
// 运输适配器使用同一份严格定义，避免stdio与业务IPC各自放宽字段。
export const m20StreamEventSchema=streamEventSchema;
export const m20ScanPageSchema=scanPageSchema;
export type M20StreamEvent=StreamEvent;

/** V3-004目标进度来自后端事实，不授予执行或接续权限。 */
export const taskProgressSchema=z.object({request_id:id,state:z.string(),instruction:z.string().refine(value=>Array.from(value).length<=2000),steps:z.array(z.object({index:z.number().int().min(0),title:z.string().refine(value=>Array.from(value).length<=300),kind:z.string(),status:z.enum(['not_started','running','waiting_authorization','waiting_approval','waiting_input','unsupported','limited','blocked','completed','accepted','failed','cancelled','interrupted']),detail:z.string().refine(value=>Array.from(value).length<=600)}).strict()).max(16)}).strict();
