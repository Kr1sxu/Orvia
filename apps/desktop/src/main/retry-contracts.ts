import {z} from 'zod';

/** 重试分类和调度由程序固定，界面只给所属会话；不接受工具声明、正文、URL或许可。 */
export const retryId=z.object({id:z.string().uuid()}).strict();
const timestamp=z.string().max(40).datetime({offset:true});
const state=z.enum(['running','succeeded','failed','unknown','cancelled','timed_out','interrupted']);
const reason=z.enum(['initial','connect_before_send','http_429','http_503','sqlite_busy','sqlite_locked','not_retryable','budget_exhausted','cancelled','interrupted','success']);
export const retryAttempt=z.object({sequence:z.number().int().min(1).max(3),state,started_at:timestamp,finished_at:timestamp.nullable(),reason:reason.nullable(),delay_seconds:z.number().finite().min(0).max(0.5),error_code:z.string().max(64).regex(/^[A-Z][A-Z0-9_]*$/).nullable()}).strict();
export const retryRun=z.object({business_id:z.string().regex(/^[A-Za-z0-9_.:-]{1,128}$/),tool:z.enum(['browser.static_read','context.sqlite_read']),parameter_digest:z.string().regex(/^[a-f0-9]{64}$/),state,started_at:timestamp,finished_at:timestamp.nullable(),attempts:z.array(retryAttempt).max(3).refine(items=>items.every((item,index)=>item.sequence===index+1),'尝试须属于同一业务身份且序号连续，不重复或越过三次上限')}).strict();
/** 条数不能替代实际UTF-8运输预算；这里只验证重试账本，不声称业务目标完成。 */
export const retryHistory=z.object({id:z.string().uuid(),runs:z.array(retryRun).max(32),truncated:z.boolean()}).strict().refine(value=>new TextEncoder().encode(JSON.stringify(value)).byteLength<=32768,'重试事实超过32KiB展示预算');
export type RetryAttempt=z.infer<typeof retryAttempt>;
export type RetryRun=z.infer<typeof retryRun>;
export type RetryHistory=z.infer<typeof retryHistory>;
