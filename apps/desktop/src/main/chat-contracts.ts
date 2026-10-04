import { z } from 'zod';
import {workflowSchema,materialSchema,streamStateSchema} from './m20-contracts';

/** 会话业务契约不包含根路径、命令或模型覆盖字段，跨进程边界拒绝额外参数。 */
export const chatIdSchema = z.object({ id: z.string().uuid() }).strict();
export const chatRenameSchema=chatIdSchema.extend({title:z.string().trim().min(1).max(100).refine(value=>!/[\x00-\x1f]/.test(value))}).strict();
export const chatPinSchema=chatIdSchema.extend({pinned:z.boolean()}).strict();
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
export const chatSynthesisGenerateSchema=chatSynthesisPreviewSchema.extend({request_id:z.string().uuid(),revision:z.string().regex(/^[a-f0-9]{64}$/),stream_mode:z.enum(['stream','confirmed_nonstream']).optional()}).strict();
export const synthesisFragmentSchema=z.object({citation:z.string(),kind:z.enum(['document','browser']),evidence_id:z.string(),locator:z.string(),unit:z.number().optional(),chunk:z.number(),text:z.string().max(600),method:z.string().optional(),confidence:z.number().nullable().optional()});
export const synthesisCoverageSchema=z.object({kind:z.enum(['document','browser']),evidence_id:z.string(),title:z.string(),accessed_at:z.string().nullable(),selected_chunks:z.number(),available_chunks:z.number(),source_truncated:z.boolean(),missing_units:z.array(z.number()),ocr_available:z.boolean(),ocr_selected:z.boolean()});
export const synthesisPreviewSchema=z.object({mode:z.enum(['summary','answer']),question:z.string(),supplier:z.string(),fragments:z.array(synthesisFragmentSchema).max(9),coverage:z.array(synthesisCoverageSchema).max(3),revision:z.string().regex(/^[a-f0-9]{64}$/)});
export type SynthesisPreview=z.infer<typeof synthesisPreviewSchema>;
export type SynthesisSource=z.infer<typeof synthesisSourceSchema>;
export const synthesisMessageSchema=z.object({answer:z.string().max(2200),claims:z.array(z.object({text:z.string().max(600),kind:z.enum(['fact','inference','conflict','unknown']),citations:z.array(z.string()).max(3)})).max(8),citations:z.array(synthesisFragmentSchema.omit({text:true})).max(9),coverage:z.array(synthesisCoverageSchema).max(3),revision:z.string().regex(/^[a-f0-9]{64}$/),model:z.literal('deepseek-flash'),usage:z.record(z.number().int())});
/** M16 只编辑 M15 结果的纯文本；来源和引用映射由后端从原消息读取。 */
export const chatPublicationPreviewSchema=chatIdSchema.extend({message_id:z.string().uuid(),format:z.enum(['docx','pptx','pdf']),title:z.string().trim().min(1).max(40),answer:z.string().trim().min(1).max(2200),claim_texts:z.array(z.string().trim().min(1).max(600)).min(1).max(8)}).strict();
export const chatPublicationSaveSchema=chatPublicationPreviewSchema.extend({request_id:z.string().uuid(),revision:z.string().regex(/^[a-f0-9]{64}$/)}).strict();
const publicationReferenceSchema=z.object({number:z.number().int().min(1),citation:z.string(),title:z.string(),locator:z.string(),kind:z.enum(['document','browser']),evidence_id:z.string().regex(/^[a-f0-9]{64}$/)});
export const publicationPreviewSchema=z.object({schema:z.literal('orvia.publication.v1'),format:z.enum(['docx','pptx','pdf']),message_id:z.string().uuid(),title:z.string(),answer:z.string(),claims:z.array(z.object({kind:z.enum(['fact','inference','conflict','unknown']),label:z.string(),text:z.string(),numbers:z.array(z.number().int())})).max(8),references:z.array(publicationReferenceSchema).max(9),pages:z.array(z.object({heading:z.string(),body:z.string(),label:z.string(),numbers:z.array(z.number().int()),references:z.array(publicationReferenceSchema).optional()})).max(60),notice:z.string(),source_revision:z.string().regex(/^[a-f0-9]{64}$/),revision:z.string().regex(/^[a-f0-9]{64}$/),filename:z.string()});
export type PublicationPreview=z.infer<typeof publicationPreviewSchema>;
export const publicationMessageSchema=z.object({filename:z.string().max(255),format:z.enum(['docx','pptx','pdf']),revision:z.string().regex(/^[a-f0-9]{64}$/),message_id:z.string().uuid(),source_revision:z.string().regex(/^[a-f0-9]{64}$/),pages:z.number().int().min(1)});
/** M17 仅让 renderer 提交相对文件名及选择；绝对根仍来自原生目录授权。 */
export const developmentContextRequestSchema=chatIdSchema.extend({requirement:z.string().trim().min(1).max(1200),paths:z.array(z.string().min(1).max(240)).max(3),sources:z.array(synthesisSourceSchema).max(2),result_message_id:z.string().uuid().nullable()}).strict();
export const developmentGenerateRequestSchema=developmentContextRequestSchema.extend({kind:z.enum(['code','prototype']),stack:z.enum(['react-vite','web-native']),context_revision:z.string().regex(/^[a-f0-9]{64}$/),request_id:z.string().uuid()}).strict().refine(value=>value.kind!=='prototype'||value.stack==='web-native');
export const developmentDraftRequestSchema=chatIdSchema.extend({draft_id:z.string().uuid()}).strict();
export const developmentApplyRequestSchema=developmentDraftRequestSchema.extend({revision:z.string().regex(/^[a-f0-9]{64}$/),index:z.number().int().min(0).max(11)}).strict();
export const developmentContextSchema=z.object({files:z.array(z.object({path:z.string(),content:z.string(),sha256:z.string()})).max(3),fragments:z.array(z.object({kind:z.enum(['document','browser']),evidence_id:z.string(),locator:z.string(),citation:z.string(),text:z.string()})).max(6),saved_result:z.object({answer:z.string(),claims:z.array(z.object({text:z.string(),kind:z.string(),citations:z.array(z.string())})),citations:z.array(z.unknown()),note:z.string()}).nullable(),revision:z.string().regex(/^[a-f0-9]{64}$/)});
const prototypePageSchema=z.object({id:z.string(),title:z.string(),body:z.string(),buttons:z.array(z.object({label:z.string(),target:z.string()})),form:z.object({label:z.string(),success:z.string()}).nullable()});
export const developmentDraftSchema=z.object({draft_id:z.string().uuid(),kind:z.enum(['code','prototype']),stack:z.enum(['react-vite','web-native']),revision:z.string().regex(/^[a-f0-9]{64}$/),files:z.array(z.object({index:z.number().int(),path:z.string(),content:z.string(),diff:z.string(),status:z.string(),operation:z.enum(['create','modify'])})).min(1).max(12),prototype:z.object({title:z.string(),pages:z.array(prototypePageSchema)}).nullable()});
export type DevelopmentContext=z.infer<typeof developmentContextSchema>;
export type DevelopmentDraft=z.infer<typeof developmentDraftSchema>;
export const cleanupPlanRequestSchema=chatIdSchema.extend({plan_id:z.string().uuid()}).strict();
export const cleanupExecuteRequestSchema=cleanupPlanRequestSchema.extend({revision:z.string().regex(/^[a-f0-9]{64}$/),indices:z.array(z.number().int().min(0).max(49)).min(1).max(50)}).strict();
export const cleanupRestoreRequestSchema=cleanupPlanRequestSchema.extend({index:z.number().int().min(0).max(49)}).strict();
export const cleanupPlanSchema=z.object({plan_id:z.string().uuid(),revision:z.string().regex(/^[a-f0-9]{64}$/),status:z.string(),entries:z.array(z.object({index:z.number().int(),name:z.string(),size:z.number().int().min(0),mtime:z.string(),risk:z.enum(['low','medium']),status:z.string(),error:z.string().nullable()})).max(50),truncated:z.boolean(),logical_bytes:z.number().int(),quarantined_bytes:z.number().int(),released_bytes:z.literal(0),restore_until:z.string()});
export type CleanupPlan=z.infer<typeof cleanupPlanSchema>;
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
export const taskStatusSchema = z.enum(['draft','running','waiting_input','waiting_approval','awaiting_approval','completed','failed','interrupted','cancelled','undone','partially_undone']);
export const operationHistorySchema = z.object({operation_id:z.string().uuid(),revision:z.string(),status:z.string(),created_at:z.string(),updated_at:z.string(),can_undo:z.boolean()});
/** 中断前缀仍是未核验数据；strict身份和编码预算不能让其成为M15成功结果。 */
export const modelPartialSchema=z.object({request_id:z.string().uuid(),stream_id:z.string().uuid(),last_seq:z.number().int().min(0),state:z.enum(['running','paused','completed','failed','cancelled','interrupted']),text:codepoints(16000).refine(value=>new TextEncoder().encode(JSON.stringify(value)).length<=24*1024),provisional:z.literal(true)}).strict();
export const chatMessageSchema = z.object({ id: z.string(), role: z.enum(['user','assistant','system']), text: z.string(), kind: z.enum(['text','scan','directory_result','natural_request','natural_answer','model_partial','clarification','material_removed','source','source_request','document_request','document','export','synthesis_request','synthesis','publication_request','publication','development','cleanup','automation','workflow','plan','result','error']), data: z.record(z.unknown()).nullable(), created_at: z.string() }).superRefine((message,ctx)=>{
  if(message.kind==='document'&&!documentMessageSchema.safeParse(message.data).success)ctx.addIssue({code:z.ZodIssueCode.custom,message:'文档消息不符合契约'});
  if(message.kind==='export'&&!documentExportMessageSchema.safeParse(message.data).success)ctx.addIssue({code:z.ZodIssueCode.custom,message:'导出消息不符合契约'});
  if(message.kind==='source'&&!browserMessageSchema.safeParse(message.data).success)ctx.addIssue({code:z.ZodIssueCode.custom,message:'来源消息不符合契约'});
  if(message.kind==='synthesis'&&!synthesisMessageSchema.safeParse(message.data).success)ctx.addIssue({code:z.ZodIssueCode.custom,message:'生成回答不符合契约'});
  if(message.kind==='publication'&&!publicationMessageSchema.safeParse(message.data).success)ctx.addIssue({code:z.ZodIssueCode.custom,message:'成品核验消息不符合契约'});
  if(message.kind==='model_partial'&&!modelPartialSchema.safeParse(message.data).success)ctx.addIssue({code:z.ZodIssueCode.custom,message:'部分模型文字不符合身份或预算契约'});
});
/** 历史入口仅含有界身份，不含路径、源码或权限；旧快照可缺省。 */
export const workspaceHistorySchema=z.object({development:z.object({draft_id:z.string().uuid(),kind:z.enum(['code','prototype'])}).strict().nullable(),cleanup:z.object({plan_id:z.string().uuid()}).strict().nullable(),automation:z.array(z.enum(['script','desktop','browser'])).max(3)}).strict();
export const chatSnapshotSchema = z.object({ id: z.string().uuid(), title: z.string(), mission_id: z.string().uuid(), messages: z.array(chatMessageSchema),
  grant: z.object({ root_label: z.string().nullable(), grant_id: z.string().uuid(), calls_remaining: z.number() }).nullable(), operation: operationSchema.nullable(),
  messages_truncated: z.boolean().optional(),
  documents:z.array(documentEvidenceSchema).max(20).optional(),documents_truncated:z.boolean().optional(),
  sources: z.array(browserEvidenceSchema).max(20).optional(), sources_truncated:z.boolean().optional(),
  status: taskStatusSchema.optional(), operations: z.array(operationHistorySchema).max(10).optional(), operations_truncated: z.boolean().optional(),
  workflow:workflowSchema.nullable().optional(),materials:z.array(materialSchema).max(3).optional(),stream:streamStateSchema.nullable().optional(),
  workspace_history:workspaceHistorySchema.optional(),
});
export const chatListSchema = z.object({ conversations: z.array(z.object({ id: z.string().uuid(), title: z.string(), pinned:z.boolean().optional(), updated_at:z.string().optional(), status: taskStatusSchema.optional() })) });
export type ConversationSummary = z.infer<typeof chatListSchema>['conversations'][number];
export type Conversation = z.infer<typeof chatSnapshotSchema>;
export type ChatMessage = z.infer<typeof chatMessageSchema>;
export type ReadCall = z.infer<typeof readCallSchema>;
export type ChatApproval = z.infer<typeof chatApprovalSchema>;
