import { z } from 'zod';

export const roleSchema = z.enum(['main', 'computer', 'browser']);
export const profiles = [
  { role: 'main', provider: 'deepseek', model: 'deepseek-flash', base_url: 'https://api.deepseek.com', credential_ref: 'DEEPSEEK_API_KEY', revision: 1 },
  { role: 'computer', provider: 'zhipu', model: 'glm-5.3-flashx', base_url: 'https://open.bigmodel.cn/api/paas/v4', credential_ref: 'ZHIPU_API_KEY', revision: 1 },
  { role: 'browser', provider: 'mimo', model: 'mimo-v2.6-flash', base_url: 'https://api.xiaomimimo.com/v1', credential_ref: 'MIMO_API_KEY', revision: 1 },
] as const;
const profileShape = z.object({ role: roleSchema, provider: z.string(), model: z.string(), base_url: z.string(), credential_ref: z.string(), revision: z.literal(1).default(1) }).strict();
/** 与后端导出 Schema 交叉验证，拒绝服务器返回静默替换的模型配置。 */
export const profileSchema = profileShape.refine(value => {
  const expected = profiles.find(item => item.role === value.role)!;
  return Object.entries(expected).every(([key, wanted]) => value[key as keyof typeof value] === wanted);
}, '固定模型配置不匹配');
// Python / JSON Schema 按 Unicode 字符计数，不能用 JS UTF-16 长度误拒绝 emoji。
export const missionCreateSchema = z.object({ client_request_id: z.string().uuid(), title: z.string().trim().min(1).refine(value => Array.from(value).length <= 200) }).strict();
export const missionSchema = missionCreateSchema.extend({ id: z.string().uuid(), status: z.literal('draft'), created_at: z.string().datetime({ offset: true }),
  models: z.array(profileSchema).length(3).refine(items => new Set(items.map(item => item.role)).size === 3, '角色配置必须唯一'),
}).strict();
export const configurationSchema = z.object({ profiles: z.array(z.object({ ...profileShape.shape, configured: z.boolean() }).strict()
  .refine(value => profileSchema.safeParse(Object.fromEntries(Object.entries(value).filter(([key]) => key !== 'configured'))).success)).length(3)
  .refine(items => new Set(items.map(item => item.role)).size === 3), search_available: z.boolean() }).strict();
export const credentialRoleSchema = z.enum(['main', 'computer', 'browser', 'tavily', 'redis']);
export const credentialInputSchema = z.object({ role: credentialRoleSchema, key: z.string().min(1).max(4096).refine(value => !!value.trim() && !/[\r\n]/.test(value)) }).strict();
export type Mission = z.infer<typeof missionSchema>;
export type MissionCreate = z.infer<typeof missionCreateSchema>;
export type Configuration = z.infer<typeof configurationSchema>;

export const grantStatusSchema = z.object({
  mission_id: z.string().uuid(), grant_id: z.string().uuid().nullable(), root_label: z.string().nullable(),
  allow_files: z.boolean(), allow_text: z.boolean(), allow_system: z.boolean(), calls_remaining: z.number().int().min(0),
}).strict();
export const directoryEntrySchema = z.object({ path: z.string(), name: z.string(), kind: z.enum(['file', 'directory']), size: z.number(), modified_at: z.string() }).strict();
export const scanEnvelopeSchema = z.object({
  data: z.record(z.unknown()), complete: z.boolean(), truncated: z.boolean(), errors: z.array(z.object({ code: z.string() }).strict()),
  scanned_at: z.string(), scanned_entries: z.number().int().min(0), tool: z.string(), mission_id: z.string().uuid(), grant_id: z.string().uuid(), calls_remaining: z.number().int().min(0),
}).strict();
export const grantRequestSchema = z.object({ mission_id: z.string().uuid(), root: z.string().min(1), allow_text: z.literal(false), allow_system: z.literal(false) }).strict();
export const computerCallSchema = z.object({
  mission_id: z.string().uuid(), grant_id: z.string().uuid(),
  call: z.object({
    tool: z.enum(['list_directory', 'search_files', 'get_file_metadata', 'analyze_directory_space']),
    arguments: z.record(z.unknown()),
  }).strict(),
}).strict();
export type GrantStatus = z.infer<typeof grantStatusSchema>;
export type ScanEnvelope = z.infer<typeof scanEnvelopeSchema>;
