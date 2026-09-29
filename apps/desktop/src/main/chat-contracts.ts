import { z } from 'zod';

/** 会话业务契约不包含根路径、命令或模型覆盖字段，跨进程边界拒绝额外参数。 */
export const chatIdSchema = z.object({ id: z.string().uuid() }).strict();
export const chatCancelSchema = chatIdSchema.extend({ request_id: z.string().uuid() }).strict();
export const chatCreateSchema = z.object({ client_request_id: z.string().uuid(), title: z.string().trim().min(1).max(100) }).strict();
export const chatSendSchema = chatIdSchema.extend({ request_id: z.string().uuid(), text: z.string().trim().min(1).max(2000) }).strict();
export const chatBrowserSearchSchema = chatCancelSchema.extend({ query: z.string().trim().min(1).max(500), max_results: z.number().int().min(1).max(5).default(5) }).strict();
export const chatBrowserReadSchema = chatCancelSchema.extend({ url: z.string().trim().min(1).max(2048), mode: z.enum(['auto','http','playwright']).default('auto') }).strict();
export const chatBrowserAskSchema = chatCancelSchema.extend({ query: z.string().trim().min(1).max(200) }).strict();
export const chatBrowserSourceSchema = chatIdSchema.extend({ evidence_id: z.string().regex(/^[a-f0-9]{64}$/) }).strict();
export const browserEvidenceSchema = z.object({
  evidence_id: z.string().regex(/^[a-f0-9]{64}$/), content_hash: z.string().regex(/^[a-f0-9]{64}$/),
  source_url: z.string().max(2048).nullable(), accessed_at: z.string(), mode: z.string().nullable(),
  // Python 按 Unicode 码点截断；不能按 JS UTF-16 单元拒绝含 emoji 的合法证据。
  title: z.string().refine(value=>Array.from(value).length<=200).default(''), content: z.string().refine(value=>Array.from(value).length<=8000), truncated: z.boolean().default(false),
  preview_truncated: z.boolean().optional(), chunk_index: z.number().optional(),
  error: z.object({code:z.string(),message:z.string()}).nullable().optional(),
});
export type BrowserEvidence = z.infer<typeof browserEvidenceSchema>;
export const browserMessageSchema = z.object({ items: z.array(browserEvidenceSchema).max(5), operation:z.enum(['search','read','ask']),
  error:z.object({code:z.string(),message:z.string()}).nullable(), accessed_at:z.string().optional() });
/** 文档附件与导出入口只接收证据身份；路径只能来自主进程原生选择器。 */
export const chatDocumentAttachSchema = chatCancelSchema;
export const chatDocumentSourceSchema = chatBrowserSourceSchema;
export const chatDocumentAskSchema = chatBrowserAskSchema;
export const chatDocumentPreviewSchema = chatDocumentSourceSchema.extend({format:z.enum(['md','json'])}).strict();
export const chatDocumentExportSchema = chatDocumentPreviewSchema.extend({revision:z.string().regex(/^[a-f0-9]{64}$/),request_id:z.string().uuid()}).strict();
/** 生成只能引用当前会话证据 ID；正文范围由后端计算并经主进程预览确认。 */
export const synthesisSourceSchema=z.object({kind:z.enum(['document','browser']),evidence_id:z.string().regex(/^[a-f0-9]{64}$/)}).strict();
export const chatSynthesisPreviewSchema=chatIdSchema.extend({mode:z.enum(['summary','answer']),question:z.string().trim().min(1).max(300),sources:z.array(synthesisSourceSchema).min(1).max(3)}).strict();
export const chatSynthesisGenerateSchema=chatSynthesisPreviewSchema.extend({request_id:z.string().uuid(),revision:z.string().regex(/^[a-f0-9]{64}$/)}).strict();
export const synthesisFragmentSchema=z.object({citation:z.string(),kind:z.enum(['document','browser']),evidence_id:z.string(),locator:z.string(),unit:z.number().optional(),chunk:z.number(),text:z.string().max(600),method:z.string().optional(),confidence:z.number().nullable().optional()});
export const synthesisCoverageSchema=z.object({kind:z.enum(['document','browser']),evidence_id:z.string(),title:z.string(),accessed_at:z.string().nullable(),selected_chunks:z.number(),available_chunks:z.number(),source_truncated:z.boolean(),missing_units:z.array(z.number()),ocr_available:z.boolean(),ocr_selected:z.boolean()});
export const synthesisPreviewSchema=z.object({mode:z.enum(['summary','answer']),question:z.string(),supplier:z.string(),fragments:z.array(synthesisFragmentSchema).max(9),coverage:z.array(synthesisCoverageSchema).max(3),revision:z.string().regex(/^[a-f0-9]{64}$/)});
export type SynthesisPreview=z.infer<typeof synthesisPreviewSchema>;
export type SynthesisSource=z.infer<typeof synthesisSourceSchema>;
export const synthesisMessageSchema=z.object({answer:z.string().max(2200),claims:z.array(z.object({text:z.string().max(600),kind:z.enum(['fact','inference','conflict','unknown']),citations:z.array(z.string()).max(3)})).max(8),citations:z.array(synthesisFragmentSchema.omit({text:true})).max(9),coverage:z.array(synthesisCoverageSchema).max(3),revision:z.string().regex(/^[a-f0-9]{64}$/),model:z.literal('deepseek-flash'),usage:z.record(z.number().int())});
const documentErrorSchema=z.object({code:z.string(),message:z.string()}).nullable();
const codepoints=(limit:number)=>z.string().refine(value=>Array.from(value).length<=limit);
export const documentUnitSchema=z.object({number:z.number().int().min(1),locator:codepoints(200),text:codepoints(8000),method:z.enum(['text','ocr']),confidence:z.number().min(0).max(1).nullable(),error:documentErrorSchema});
export const documentEvidenceSchema=z.object({
  evidence_id:z.string().regex(/^[a-f0-9]{64}$/),content_hash:z.string().regex(/^[a-f0-9]{64}$/),file_hash:z.string().regex(/^[a-f0-9]{64}$/),
  preview_truncated:z.boolean().optional(),title:codepoints(200),format:z.string(),accessed_at:z.string(),truncated:z.boolean(),total_units:z.number().int().min(0),
  missing_units:z.array(z.number().int().min(1)),error:documentErrorSchema,units:z.array(documentUnitSchema).max(50),
}).refine(value=>value.units.reduce((total,unit)=>total+Array.from(unit.text).length,0)<=8000);
export const documentMessageSchema=z.object({items:z.array(documentEvidenceSchema).max(5),operation:z.enum(['attach','ask']),error:documentErrorSchema});
export const documentPreviewSchema=z.object({evidence_id:z.string().regex(/^[a-f0-9]{64}$/),format:z.enum(['md','json']),revision:z.string().regex(/^[a-f0-9]{64}$/),filename:z.string().max(250).refine(value=>!/[\\/:]/.test(value)),content:codepoints(60000),coverage:z.object({cited:z.number().int().min(0),total:z.number().int().min(0)}),truncated:z.boolean(),missing_units:z.array(z.number().int().min(1))});
export type DocumentEvidence=z.infer<typeof documentEvidenceSchema>;
export type DocumentPreview=z.infer<typeof documentPreviewSchema>;
export const documentExportMessageSchema=z.object({filename:z.string().max(255),evidence_id:z.string().regex(/^[a-f0-9]{64}$/),revision:z.string().regex(/^[a-f0-9]{64}$/),format:z.enum(['md','json']),coverage:z.object({cited:z.number().int().min(0),total:z.number().int().min(0)}),truncated:z.boolean(),missing_units:z.array(z.number().int().min(1))});
export const chatApprovalSchema = chatIdSchema.extend({ operation_id: z.string().uuid(), revision: z.string().regex(/^[a-f0-9]{64}$/) }).strict();
const relative = z.string().min(1).max(1000);
export const readCallSchema = z.discriminatedUnion('tool', [
  z.object({ tool: z.literal('list_directory'), arguments: z.object({ path: relative.default('.'), limit: z.number().int().min(1).max(100).default(100) }).strict() }).strict(),
  z.object({ tool: z.literal('search_files'), arguments: z.object({ path: relative.default('.'), query: z.string().min(1).max(100), recursive: z.boolean().default(true), limit: z.number().int().min(1).max(100).default(100) }).strict() }).strict(),
  z.object({ tool: z.literal('get_file_metadata'), arguments: z.object({ path: relative }).strict() }).strict(),
  z.object({ tool: z.literal('analyze_directory_space'), arguments: z.object({ path: relative.default('.'), top_n: z.number().int().min(1).max(30).default(10), min_size: z.number().int().min(0).max(Number.MAX_SAFE_INTEGER).default(0) }).strict() }).strict(),
]);
// 使用独立校验函数让联合工具参数保持 strict，同时接收会话标识。
export function parseInspect(input: unknown) {
  const envelope = z.object({ id: z.string().uuid(), tool: z.string(), arguments: z.unknown() }).strict().parse(input);
  return { id: envelope.id, ...readCallSchema.parse({ tool: envelope.tool, arguments: envelope.arguments }) };
}
export const actionSchema = z.object({ kind: z.enum(['mkdir', 'move', 'rename']), source: z.string().nullable().optional(), destination: z.string(), sequence: z.number().optional() });
export const operationSchema = z.object({ operation_id: z.string().uuid(), revision: z.string(), status: z.string(), actions: z.array(actionSchema), error: z.string().nullable().optional(), can_undo: z.boolean().optional() });
export const taskStatusSchema = z.enum(['draft','running','awaiting_approval','completed','failed','interrupted','cancelled','undone','partially_undone']);
export const operationHistorySchema = z.object({operation_id:z.string().uuid(),revision:z.string(),status:z.string(),created_at:z.string(),updated_at:z.string(),can_undo:z.boolean()});
export const chatMessageSchema = z.object({ id: z.string(), role: z.enum(['user','assistant','system']), text: z.string(), kind: z.enum(['text','scan','source','source_request','document_request','document','export','synthesis_request','synthesis','plan','result','error']), data: z.record(z.unknown()).nullable(), created_at: z.string() }).superRefine((message,ctx)=>{
  if(message.kind==='document'&&!documentMessageSchema.safeParse(message.data).success)ctx.addIssue({code:z.ZodIssueCode.custom,message:'文档消息不符合契约'});
  if(message.kind==='export'&&!documentExportMessageSchema.safeParse(message.data).success)ctx.addIssue({code:z.ZodIssueCode.custom,message:'导出消息不符合契约'});
  if(message.kind==='source'&&!browserMessageSchema.safeParse(message.data).success)ctx.addIssue({code:z.ZodIssueCode.custom,message:'来源消息不符合契约'});
  if(message.kind==='synthesis'&&!synthesisMessageSchema.safeParse(message.data).success)ctx.addIssue({code:z.ZodIssueCode.custom,message:'生成回答不符合契约'});
});
export const chatSnapshotSchema = z.object({ id: z.string().uuid(), title: z.string(), mission_id: z.string().uuid(), messages: z.array(chatMessageSchema),
  grant: z.object({ root_label: z.string().nullable(), grant_id: z.string().uuid(), calls_remaining: z.number() }).nullable(), operation: operationSchema.nullable(),
  messages_truncated: z.boolean().optional(),
  documents:z.array(documentEvidenceSchema).max(20).optional(),documents_truncated:z.boolean().optional(),
  sources: z.array(browserEvidenceSchema).max(20).optional(), sources_truncated:z.boolean().optional(),
  status: taskStatusSchema.optional(), operations: z.array(operationHistorySchema).max(10).optional(), operations_truncated: z.boolean().optional(),
});
export const chatListSchema = z.object({ conversations: z.array(z.object({ id: z.string().uuid(), title: z.string(), status: taskStatusSchema.optional() })) });
export type ConversationSummary = z.infer<typeof chatListSchema>['conversations'][number];
export type Conversation = z.infer<typeof chatSnapshotSchema>;
export type ChatMessage = z.infer<typeof chatMessageSchema>;
export type ReadCall = z.infer<typeof readCallSchema>;
export type ChatApproval = z.infer<typeof chatApprovalSchema>;
