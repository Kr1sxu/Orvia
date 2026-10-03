import { z } from 'zod';

export const VERSION = 1;
export const MAX_LINE_BYTES = 64 * 1024;
export const responseSchema = z.discriminatedUnion('ok', [
  z.object({ v: z.literal(VERSION), id: z.string().min(1), ok: z.literal(true), result: z.unknown() }).strict(),
  z.object({ v: z.literal(VERSION), id: z.string().nullable(), ok: z.literal(false),
    error: z.object({ code: z.string(), message: z.string() }).strict() }).strict(),
]);
export const helloSchema = z.object({ protocol: z.literal(VERSION), service: z.literal('orvia-backend'), python: z.string().regex(/^3\.12\./) }).strict();
export const healthSchema = z.object({ status: z.literal('ok'), service: z.literal('orvia-backend') }).strict();

/** 按字节缓存分片，完整换行后解码，避免中文 UTF-8 被切断。 */
export class JsonLines {
  private buffer = Buffer.alloc(0);
  push(chunk: Buffer): unknown[] {
    // Node管道按至多64KiB读取；拒绝异常合并块，避免完整小帧洪泛形成无界messages数组。
    if(chunk.length>MAX_LINE_BYTES)throw new Error('协议输入块超过限制');
    this.buffer = Buffer.concat([this.buffer, chunk]);
    const messages: unknown[] = [];
    let end: number;
    while ((end = this.buffer.indexOf(10)) >= 0) {
      if (end + 1 > MAX_LINE_BYTES) throw new Error('协议行超过限制');
      const line = this.buffer.subarray(0, end);
      this.buffer = this.buffer.subarray(end + 1);
      messages.push(JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(line)));
    }
    if (this.buffer.length > MAX_LINE_BYTES) throw new Error('协议行超过限制');
    return messages;
  }
}
