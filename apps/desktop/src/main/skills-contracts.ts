import {z} from 'zod';

const identity=z.string().regex(/^[a-z][a-z0-9-]{1,63}$/),revision=z.string().regex(/^[a-f0-9]{64}$/);
const data=z.record(z.string(),z.unknown());
export const skillToggle=z.object({skill_id:identity,enabled:z.boolean()}).strict();
export const skillRun=z.object({skill_id:identity,inputs:data,conversation_id:z.string().uuid().optional()}).strict();
export const skillSummary=z.object({id:identity,name:z.string().max(100),version:z.string().max(32),revision,
  description:z.string().max(1000),enabled:z.boolean(),builtin:z.boolean(),available:z.boolean(),
  unavailable_reason:z.string().max(300).nullable(),dependencies:z.array(z.string()).max(16),step_count:z.number().int().min(0).max(16)}).strict();
export const skillList=z.object({skills:z.array(skillSummary).max(10),offset:z.number().int().min(0).max(36),total:z.number().int().min(0).max(37)}).strict();
export const skillReview=z.object({review_id:z.string().uuid(),revision,manifest:data,documentation:z.string(),warnings:z.array(z.string())}).strict();
export const skillPlan=z.object({plan_id:z.string().uuid(),revision,skill_id:identity,version:z.string(),mission_id:z.string().uuid(),grant_id:z.string().uuid().nullable(),
  inputs:data,steps:z.array(z.object({id:z.string(),tool:z.string(),arguments:data,output_schema:data}).strict()).max(32),
  bindings:z.array(z.object({id:identity,version:z.string(),revision,generation:z.number().int().positive()}).strict()).max(37),status:z.literal('planned')}).strict();
const error=z.object({code:z.string().max(100),message:z.string().max(300)}).strict().nullable();
export const skillExecution=z.object({plan_id:z.string().uuid(),revision,skill_id:identity,version:z.string(),mission_id:z.string().uuid(),grant_id:z.string().uuid().nullable(),
  status:z.enum(['planned','running','completed','limited','failed','interrupted']),
  steps:z.array(z.object({id:z.string(),tool:z.string(),status:z.enum(['completed','limited','failed','unknown']),result:data.nullable(),error}).strict()).max(32),
  output:data.nullable(),error}).strict();
export type SkillSummary=z.infer<typeof skillSummary>;
export type SkillExecution=z.infer<typeof skillExecution>;
export const skillHistory=z.object({executions:z.array(skillExecution.pick({plan_id:true,skill_id:true,version:true,status:true})).max(20)}).strict();
export type SkillsMethod='list'|'enable'|'preview_import'|'register'|'plan'|'execute'|'execution'|'history'|'cancel';
