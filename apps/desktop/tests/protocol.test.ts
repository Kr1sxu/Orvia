import { describe, expect, it } from 'vitest';
import { JsonLines, MAX_LINE_BYTES, responseSchema, helloSchema } from '../src/main/protocol';
import { mayCheckHealth } from '../src/main/ipc-policy';

describe('跨语言帧边界', () => {
  it('中文任意分片与多行合并', () => {
    const frame = { v: 1, id: '序航健康', ok: true, result: {} };
    const data = Buffer.from(JSON.stringify(frame) + '\n' + JSON.stringify(frame) + '\r\n');
    for (let split = 1; split < data.length; split++) {
      const parser = new JsonLines();
      expect([...parser.push(data.subarray(0, split)), ...parser.push(data.subarray(split))]).toEqual([frame, frame]);
    }
  });
  it('拒绝过长行、非法 JSON 和非法 UTF-8', () => {
    expect(() => new JsonLines().push(Buffer.alloc(MAX_LINE_BYTES + 1, 120))).toThrow();
    expect(() => new JsonLines().push(Buffer.from('{\n'))).toThrow();
    expect(() => new JsonLines().push(Buffer.from([255, 10]))).toThrow();
    expect(() => new JsonLines().push(Buffer.concat([Buffer.alloc(MAX_LINE_BYTES, 32), Buffer.from('\n')]))).toThrow();
  });
  it('拒绝不兼容响应和 Python 版本', () => {
    expect(responseSchema.safeParse({ v: 2, id: 'x', ok: true, result: {} }).success).toBe(false);
    expect(helloSchema.safeParse({ protocol: 1, service: 'orvia-backend', python: '3.11.7' }).success).toBe(false);
  });
});

it('仅受信任主 frame 的无参数健康检查通过', () => {
  const url = 'file:///app/index.html';
  expect(mayCheckHealth(true, true, url, url, [])).toBe(true);
  expect(mayCheckHealth(false, true, url, url, [])).toBe(false);
  expect(mayCheckHealth(true, false, url, url, [])).toBe(false);
  expect(mayCheckHealth(true, true, 'https://evil.test', url, [])).toBe(false);
  expect(mayCheckHealth(true, true, url, url, ['command'])).toBe(false);
});
