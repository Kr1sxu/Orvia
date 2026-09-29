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
export const chatMessageSchema = z.object({ id: z.string(), role: z.enum(['user','assistant','system']), text: z.string(), kind: z.enum(['text','scan','source','source_request','plan','result','error']), data: z.record(z.unknown()).nullable(), created_at: z.string() }).superRefine((message,ctx)=>{
  if(message.kind==='source'&&!browserMessageSchema.safeParse(message.data).success)ctx.addIssue({code:z.ZodIssueCode.custom,message:'来源消息不符合契约'});
});
export const chatSnapshotSchema = z.object({ id: z.string().uuid(), title: z.string(), mission_id: z.string().uuid(), messages: z.array(chatMessageSchema),
  grant: z.object({ root_label: z.string().nullable(), grant_id: z.string().uuid(), calls_remaining: z.number() }).nullable(), operation: operationSchema.nullable(),
  messages_truncated: z.boolean().optional(),
  sources: z.array(browserEvidenceSchema).max(20).optional(), sources_truncated:z.boolean().optional(),
  status: taskStatusSchema.optional(), operations: z.array(operationHistorySchema).max(10).optional(), operations_truncated: z.boolean().optional(),
});
export const chatListSchema = z.object({ conversations: z.array(z.object({ id: z.string().uuid(), title: z.string(), status: taskStatusSchema.optional() })) });
export type ConversationSummary = z.infer<typeof chatListSchema>['conversations'][number];
export type Conversation = z.infer<typeof chatSnapshotSchema>;
export type ChatMessage = z.infer<typeof chatMessageSchema>;
export type ReadCall = z.infer<typeof readCallSchema>;
export type ChatApproval = z.infer<typeof chatApprovalSchema>;
