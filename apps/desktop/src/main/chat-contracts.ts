import { z } from 'zod';

/** 会话业务契约不包含根路径、命令或模型覆盖字段，跨进程边界拒绝额外参数。 */
export const chatIdSchema = z.object({ id: z.string().uuid() }).strict();
export const chatCreateSchema = z.object({ client_request_id: z.string().uuid(), title: z.string().trim().min(1).max(100) }).strict();
export const chatSendSchema = chatIdSchema.extend({ request_id: z.string().uuid(), text: z.string().trim().min(1).max(2000) }).strict();
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
export const operationSchema = z.object({ operation_id: z.string().uuid(), revision: z.string(), status: z.string(), actions: z.array(actionSchema), error: z.string().nullable().optional() });
export const chatMessageSchema = z.object({ id: z.string(), role: z.enum(['user','assistant','system']), text: z.string(), kind: z.enum(['text','scan','plan','result','error']), data: z.record(z.unknown()).nullable(), created_at: z.string() });
export const chatSnapshotSchema = z.object({ id: z.string().uuid(), title: z.string(), mission_id: z.string().uuid(), messages: z.array(chatMessageSchema),
  grant: z.object({ root_label: z.string().nullable(), grant_id: z.string().uuid(), calls_remaining: z.number() }).nullable(), operation: operationSchema.nullable(),
  messages_truncated: z.boolean().optional(),
});
export const chatListSchema = z.object({ conversations: z.array(z.object({ id: z.string().uuid(), title: z.string() })) });
export type Conversation = z.infer<typeof chatSnapshotSchema>;
export type ChatMessage = z.infer<typeof chatMessageSchema>;
export type ReadCall = z.infer<typeof readCallSchema>;
export type ChatApproval = z.infer<typeof chatApprovalSchema>;
