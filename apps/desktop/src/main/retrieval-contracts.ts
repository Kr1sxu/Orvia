import {z} from 'zod';
export const retrievalStatus=z.object({ready:z.boolean(),reason:z.string().nullable(),signature:z.string(),peak_bytes:z.number().nonnegative(),memory_limit_bytes:z.number().positive(),threads:z.literal(4),batch:z.literal(4),max_tokens:z.literal(1024)}).strict();
export const retrievalModel=z.object({model:z.literal('Qwen/Qwen3-Embedding-0.6B'),revision:z.literal('97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3'),license:z.literal('Apache-2.0'),source:z.string().url(),bytes:z.number().positive(),files:z.array(z.object({name:z.string(),bytes:z.number(),algorithm:z.enum(['git-sha1','sha256']),digest:z.string()}).strict()).length(6)}).strict();
export const retrievalId=z.object({id:z.string().uuid()}).strict();
export const retrievalQuery=retrievalId.extend({query:z.string().min(1).max(200)}).strict();
export type RetrievalStatus=z.infer<typeof retrievalStatus>;
export type RetrievalMethod='status'|'model'|'prepare'|'activate'|'download'|'rebuild'|'search'|'clear';
const provenance=z.object({source:z.string().max(1000),chunk_index:z.number().int().nonnegative(),chunk_id:z.number().int().nonnegative()}).strict();
export const retrievalResult=z.object({mission_id:z.string(),query:z.string(),status:z.enum(['hybrid','keyword_only']),reason:z.string().nullable(),
  evidence:z.array(provenance.extend({text:z.string().max(1200).refine(value=>Array.from(value).length<=600),content_hash:z.string().length(64),model_revision:z.string().nullable(),channels:z.array(z.enum(['keyword','vector'])).max(2),score:z.number().finite(),provenance_count:z.number().int().positive(),supporting_sources:z.array(provenance).max(8),provenance_truncated:z.boolean()}).strict()).max(20),
  coverage:z.object({indexed_chunks:z.number().int().nonnegative(),candidate_chunks:z.number().int().nonnegative(),scope_sources:z.number().int().nonnegative(),output_limited:z.boolean()}).strict()}).strict();
export const retrievalRebuild=z.object({mission_id:z.string(),status:z.enum(['completed','keyword_only','failed']),reason:z.string().nullable(),indexed_chunks:z.number().int().nonnegative(),unique_texts:z.number().int().nonnegative(),signature:z.string()}).strict();
export const retrievalClear=z.object({mission_id:z.string(),removed_vectors:z.number().int().nonnegative()}).strict();
export type RetrievalResult=z.infer<typeof retrievalResult>;
export type RetrievalRebuild=z.infer<typeof retrievalRebuild>;
