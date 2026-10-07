import {z} from 'zod';

/** 只接受准确回环地址，禁止 URL、DNS、凭据或 Redis 命令从 renderer 透传。 */
export const auxiliaryConfig = z.object({
  enabled:z.boolean(), host:z.enum(['127.0.0.1','::1']),
  port:z.number().int().min(1).max(65535), db:z.number().int().min(0).max(15),
}).strict();
export type AuxiliaryConfig=z.infer<typeof auxiliaryConfig>;
const count=z.number().int().nonnegative();
export const auxiliaryStatus=auxiliaryConfig.extend({
  state:z.enum(['disabled','connected','degraded']),
  reason:z.enum(['unavailable','authentication_required','authentication_failed','unsupported','timeout','storage_unavailable']).nullable(),
  password_configured:z.boolean(), cache_hits:count, cache_misses:count,
  notifications_published:count, notifications_processed:count, notifications_discarded:count, metadata_count:count,
  local_notifications_processed:count,
  recent_tasks:z.array(z.object({task_id:z.string().uuid(),version:z.number().int().positive(),status:z.enum(['pending','waiting_input','waiting_approval','completed','cancelled','failed','interrupted'])}).strict()).max(20),
}).strict();
export type AuxiliaryStatus=z.infer<typeof auxiliaryStatus>;
