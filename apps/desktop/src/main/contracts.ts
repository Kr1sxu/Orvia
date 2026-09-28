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
  .refine(items => new Set(items.map(item => item.role)).size === 3), search_available: z.literal(false) }).strict();
export const credentialInputSchema = z.object({ role: roleSchema, key: z.string().min(1).max(4096).refine(value => !!value.trim() && !/[\r\n]/.test(value)) }).strict();
export type Mission = z.infer<typeof missionSchema>;
export type MissionCreate = z.infer<typeof missionCreateSchema>;
export type Configuration = z.infer<typeof configurationSchema>;
