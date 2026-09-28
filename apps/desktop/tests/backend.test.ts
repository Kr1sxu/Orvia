import { EventEmitter } from 'node:events';
import { PassThrough } from 'node:stream';
import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { BackendClient } from '../src/main/backend';

vi.mock('node:child_process', () => ({ spawn: vi.fn() }));

type Request = { v: number; id: string; method: string; params: Record<string, unknown> };

/** 仅模拟进程和管道，保留真实 BackendClient 的握手、请求和超时逻辑。 */
function fakeChild() {
  const child = Object.assign(new EventEmitter(), {
    stdin: new PassThrough(), stdout: new PassThrough(), stderr: new PassThrough(),
    kill: vi.fn(() => true),
  });
  const requests: Request[] = [];
  child.stdin.on('data', (chunk: Buffer) => requests.push(JSON.parse(chunk.toString('utf8'))));
  vi.mocked(spawn).mockReturnValue(child as unknown as ChildProcessWithoutNullStreams);
  const reply = (request: Request, result: unknown) => {
    child.stdout.write(Buffer.from(JSON.stringify({ v: 1, id: request.id, ok: true, result }) + '\n'));
  };
  return { child, requests, reply };
}

async function connected() {
  const fixture = fakeChild();
  const client = new BackendClient('C:/synthetic-orvia', 100);
  const started = client.start();
  fixture.reply(fixture.requests[0], { protocol: 1, service: 'orvia-backend', python: '3.12.10' });
  await started;
  return { ...fixture, client };
}

describe('后端连接生命周期（模拟子进程，无模型）', () => {
  beforeEach(() => { vi.useFakeTimers(); vi.mocked(spawn).mockReset(); });
  afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); });

  it('数据库初始化失败即终止子进程，不留不可用的常驻后端', async () => {
    const { child, requests, reply } = fakeChild();
    const client = new BackendClient('C:/synthetic-orvia', 100, { dataDirectory: 'C:/synthetic-data', credentials: () => ({ main: 'synthetic-private-key' }) });
    const started = client.start();
    const rejected = expect(started).rejects.toThrow('初始化失败');
    reply(requests[0], { protocol: 1, service: 'orvia-backend', python: '3.12.10' });
    await vi.advanceTimersByTimeAsync(0);
    expect(requests[1].method).toBe('initialize');
    child.stdout.write(Buffer.from(JSON.stringify({ v: 1, id: requests[1].id, ok: false, error: { code: 'STORAGE_UNAVAILABLE', message: 'synthetic-private-key' } }) + '\n'));
    await rejected;
    expect(child.kill).toHaveBeenCalledOnce();
    await expect(client.health()).rejects.toThrow('初始化失败');
    expect(spawn).toHaveBeenCalledOnce();
  });

  it('首次启动前已经停止时拒绝后续请求，不生成孤儿进程', async () => {
    fakeChild();
    const client = new BackendClient('C:/synthetic-orvia', 100);
    await client.stop();
    await expect(client.health()).rejects.toThrow('应用正在退出');
    await expect(client.start()).rejects.toThrow('应用正在退出');
    expect(spawn).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('握手不兼容时终止连接，后续健康检查不重启或重放', async () => {
    const { child, requests, reply } = fakeChild();
    const client = new BackendClient('C:/synthetic-orvia', 100);
    const started = client.start();
    const rejected = expect(started).rejects.toThrow('不兼容');
    reply(requests[0], { protocol: 1, service: 'orvia-backend', python: '3.11.9' });
    await rejected;
    await expect(client.health()).rejects.toThrow('不兼容');
    expect(child.kill).toHaveBeenCalledOnce();
    expect(spawn).toHaveBeenCalledOnce();
    expect(requests.map((request) => request.method)).toEqual(['hello']);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('响应超时同时拒绝全部等待请求并清理计时器，不自动重放', async () => {
    const { client, child, requests } = await connected();
    const first = client.health();
    const second = client.health();
    const firstRejected = expect(first).rejects.toThrow('超时');
    const secondRejected = expect(second).rejects.toThrow('超时');
    await vi.advanceTimersByTimeAsync(0);
    expect(requests.map((request) => request.method)).toEqual(['hello', 'health', 'health']);
    await vi.advanceTimersByTimeAsync(100);
    await Promise.all([firstRejected, secondRejected]);
    expect(vi.getTimerCount()).toBe(0);
    expect(child.kill).toHaveBeenCalledOnce();
    await expect(client.health()).rejects.toThrow('超时');
    expect(requests).toHaveLength(3);
    expect(spawn).toHaveBeenCalledOnce();
  });

  it('异常关闭拒绝正在等待的请求且保留失败状态', async () => {
    const { client, child, requests } = await connected();
    const pending = client.health();
    const rejected = expect(pending).rejects.toThrow('连接已关闭');
    await vi.advanceTimersByTimeAsync(0);
    child.emit('close', 1, null);
    await rejected;
    await expect(client.health()).rejects.toThrow('连接已关闭');
    expect(requests.map((request) => request.method)).toEqual(['hello', 'health']);
    expect(spawn).toHaveBeenCalledOnce();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('正常停止先发送 EOF，等待退出并取消强制终止计时器', async () => {
    const { client, child } = await connected();
    const stopped = client.stop();
    expect(child.stdin.writableEnded).toBe(true);
    expect(child.kill).not.toHaveBeenCalled();
    child.emit('close', 0, null);
    await stopped;
    await vi.advanceTimersByTimeAsync(1500);
    expect(child.kill).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
    await expect(client.health()).rejects.toThrow('应用正在退出');
  });

  it('EOF 后仍不退出的自有后端在 1500ms 后被终止', async () => {
    const { client, child } = await connected();
    // 模拟操作系统在 kill 后通知 close；验证 stop 确实等待进程关闭。
    child.kill.mockImplementation(() => { child.emit('close', null, 'SIGTERM'); return true; });
    const stopped = client.stop();
    expect(child.stdin.writableEnded).toBe(true);
    await vi.advanceTimersByTimeAsync(1499);
    expect(child.kill).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    await stopped;
    expect(child.kill).toHaveBeenCalledOnce();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('关闭收尾幂等；无法确认旧后端退出时有界拒绝而非挂起重连', async () => {
    const {client,child}=await connected();
    expect(client.connectionState).toBe('ready');
    const stopped=client.stop();
    expect(client.stop()).toBe(stopped);
    const rejected=expect(stopped).rejects.toThrow('拒绝启动第二个后端');
    await vi.advanceTimersByTimeAsync(4000);
    await rejected;
    expect(child.kill).toHaveBeenCalledOnce();
    expect(client.connectionState).toBe('disconnected');
    expect(vi.getTimerCount()).toBe(0);
  });

  it('取消只发送固定方法和请求标识，允许与等待中的规划并行', async () => {
    const {client,requests,reply,child}=await connected();
    const input={id:'6f1b7524-1eac-4567-a6b5-c3c9f563052c',request_id:'6f1b7524-1eac-4567-a6b5-c3c9f563052c'};
    const pending=client.chat('chat.send',{...input,text:'synthetic'});
    const rejected=expect(pending).rejects.toThrow('连接已关闭');
    await vi.advanceTimersByTimeAsync(0);
    const cancel=client.chatCancel(input);
    await vi.advanceTimersByTimeAsync(0);
    expect(requests.at(-1)?.method).toBe('chat.cancel');
    expect(requests.at(-1)?.params).toEqual(input);
    reply(requests.at(-1)!,{cancelled:true});
    expect(await cancel).toEqual({cancelled:true});
    child.emit('close',1,null);await rejected;
    expect(client.connectionState).toBe('disconnected');
  });
});
