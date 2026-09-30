import {z} from 'zod';

/** 固定 strict 参数；路径/解释器/批准状态不接受 renderer 输入。 */
export const automationId=z.object({id:z.string().uuid()}).strict();
export const automationOperation=automationId.extend({operation_id:z.string().uuid()}).strict();
export const automationApproval=automationOperation.extend({revision:z.string().regex(/^[a-f0-9]{64}$/)}).strict();
export const scriptPreviewInput=automationId.extend({source:z.string().min(1).refine(x=>new TextEncoder().encode(x).length<=32768&&!x.includes('\0')),inputs:z.array(z.string().min(1).max(240)).max(8)}).strict();
export const scriptFileInput=automationId.extend({inputs:z.array(z.string().min(1).max(240)).max(8)}).strict();
export const scriptModelInput=automationId.extend({requirement:z.string().trim().min(1).max(1000)}).strict();
export const scriptModelGenerateInput=scriptModelInput.extend({revision:z.string().regex(/^[a-f0-9]{64}$/),request_id:z.string().uuid()}).strict();
export const scriptExportInput=automationApproval.extend({index:z.number().int().min(0).max(11)}).strict();
export const desktopObserveInput=automationId.extend({grant_id:z.string().min(1).max(160)}).strict();
export const desktopPreviewInput=desktopObserveInput.extend({control_id:z.string().min(1).max(160),action:z.enum(['invoke','set_value','select','toggle','focus','save_new']),value:z.string().max(2048),state_hash:z.string().regex(/^[a-f0-9]{64}$/),category:z.enum(['local','form','message','upload','delete','transaction']),expectation:z.string().min(1).max(300)}).strict();
export const browserOpenInput=automationId.extend({url:z.string().min(1).max(2048),allowed_actions:z.array(z.enum(['form','message','upload','delete','transaction'])).min(1).max(5),get_write_paths:z.array(z.string().min(1).max(500)).max(10)}).strict();
export const browserSessionInput=automationId.extend({session_id:z.string().min(1).max(160)}).strict();
export const browserPreviewInput=browserSessionInput.extend({control_id:z.string().min(1).max(160),action:z.enum(['fill','select','check','click','upload']),value:z.string().max(4000),state_hash:z.string().regex(/^[a-f0-9]{64}$/),category:z.enum(['form','message','upload','delete','transaction']),expectation:z.string().min(1).max(300)}).strict();
export const browserRequestInput=browserSessionInput.extend({request_id:z.string().min(1).max(160),revision:z.string().regex(/^[a-f0-9]{64}$/)}).strict();
export const browserOriginInput=browserSessionInput.extend({url:z.string().min(1).max(2048)}).strict();
const controlSchema=z.object({control_id:z.string().max(160),name:z.string().max(500).default(''),control_type:z.string().optional(),role:z.string().optional(),patterns:z.array(z.string()).optional(),actions:z.array(z.string()).optional(),value:z.string().max(4000).optional(),checked:z.boolean().optional(),disabled:z.boolean().optional()}).passthrough();
export const automationObservation=z.object({grant_id:z.string().optional(),session_id:z.string().optional(),label:z.string().optional(),title:z.string().optional(),url:z.string().optional(),controls:z.array(controlSchema).max(160),state_hash:z.string().regex(/^[a-f0-9]{64}$/),status:z.string().optional(),notice:z.string().optional(),page_text:z.string().max(4000).optional(),file_dialog:z.boolean().optional()}).strict();
export const automationPlan=z.object({operation_id:z.string().uuid(),revision:z.string().regex(/^[a-f0-9]{64}$/),status:z.literal('awaiting_approval'),plan:z.record(z.unknown())}).strict();
export const automationFact=z.object({operation_id:z.string().uuid(),revision:z.string().regex(/^[a-f0-9]{64}$/),kind:z.string(),status:z.string(),audit:z.record(z.unknown()),created_at:z.string(),updated_at:z.string(),result:z.record(z.unknown()).nullable().optional(),outputs:z.array(z.object({index:z.number().int(),path:z.string(),bytes:z.number().int(),sha256:z.string(),exported:z.boolean()})).max(12).optional(),live:z.boolean().optional()}).strict();
export const automationHistory=z.object({operations:z.array(automationFact).max(20)}).strict();
export const browserPending=z.object({status:z.string(),pending_request:z.object({request_id:z.string(),revision:z.string().regex(/^[a-f0-9]{64}$/),url:z.string(),method:z.string(),fields:z.array(z.object({name:z.string(),value:z.string()})).max(30),bytes:z.number().int(),sha256:z.string(),sensitive_redacted:z.boolean(),category:z.string().optional()}).passthrough().nullable(),result:z.record(z.unknown()).nullable().optional(),observation:automationObservation.nullable().optional()}).passthrough();
export type AutomationObservation=z.infer<typeof automationObservation>;
export type AutomationPlan=z.infer<typeof automationPlan>;
export type AutomationFact=z.infer<typeof automationFact>;
export type BrowserPending=z.infer<typeof browserPending>;
export type AutomationCategory='form'|'message'|'upload'|'delete'|'transaction';
