import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import path from 'node:path';
import { JsonLines, VERSION, responseSchema, helloSchema, healthSchema } from './protocol';

type Pending = { resolve: (value: unknown) => void; reject: (reason: Error) => void; timer: NodeJS.Timeout };

/** M01 只启动项目内已知 Python；安装包资源路径在 M08 实现。 */
export class BackendClient {
  private child?: ChildProcessWithoutNullStreams;
  private pending = new Map<string, Pending>();
  private ready?: Promise<void>;
  private failed?: Error;
  private closing = false;
  private exited?: Promise<void>;
  constructor(private readonly root: string, private readonly timeoutMs = 5000) {}

  start(): Promise<void> {
    // 退出可能先于首次健康检查；阻止排队 IPC 在退出期间创建孤儿进程。
    if (this.failed || this.closing) return Promise.reject(this.failed ?? new Error('应用正在退出'));
    if (this.ready) return this.ready;
    const executable = path.join(this.root, 'backend', '.venv', 'Scripts', 'python.exe');
    // 不继承开发密钥、PYTHONPATH 或用户 Python 启动配置。
    const env: NodeJS.ProcessEnv = {};
    for (const key of ['SystemRoot', 'WINDIR', 'TEMP', 'TMP']) if (process.env[key]) env[key] = process.env[key];
    this.child = spawn(executable, ['-I', '-u', '-X', 'utf8', '-m', 'orvia_backend'], {
      cwd: path.join(this.root, 'backend'), shell: false, windowsHide: true, env, stdio: 'pipe',
    });
    const lines = new JsonLines();
    this.exited = new Promise((resolve) => {
      this.child!.once('close', () => {
        this.fail(new Error('本地后端连接已关闭'));
        resolve();
      });
    });
    this.child.on('error', () => this.fail(new Error('无法启动本地 Python 3.12 后端，请先按 README 安装环境')));
    this.child.stdin.on('error', () => this.fail(new Error('本地后端输入管道已关闭')));
    this.child.stdout.on('data', (chunk: Buffer) => {
      try {
        for (const value of lines.push(chunk)) {
          const response = responseSchema.parse(value);
          const pending = response.id ? this.pending.get(response.id) : undefined;
          if (!pending) throw new Error('响应 ID 不匹配');
          this.pending.delete(response.id!);
          clearTimeout(pending.timer);
          if (response.ok) pending.resolve(response.result);
          else pending.reject(new Error(`后端拒绝请求：${response.error.code}`));
        }
      } catch { this.fail(new Error('本地后端协议无效或版本不兼容')); }
    });
    // 持续消费 stderr，避免管道堵塞；不把原始后端内容泄漏到 UI 或日志。
    this.child.stderr.on('data', () => {});
    this.ready = this.request('hello').then((value) => {
      try { helloSchema.parse(value); }
      catch { const error = new Error('后端协议或 Python 版本不兼容'); this.fail(error); throw error; }
    });
    return this.ready;
  }

  /** 握手成功后才开放健康检查；连接失败不自动重放请求。 */
  async health() {
    await this.start();
    return healthSchema.parse(await this.request('health'));
  }

  private request(method: 'hello' | 'health'): Promise<unknown> {
    if (this.failed) return Promise.reject(this.failed);
    if (this.closing || !this.child) return Promise.reject(new Error('后端不可用'));
    if (this.pending.size >= 16) return Promise.reject(new Error('健康检查请求过于频繁'));
    const id = randomUUID();
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => this.fail(new Error('本地后端响应超时')), this.timeoutMs);
      this.pending.set(id, { resolve, reject, timer });
      this.child!.stdin.write(JSON.stringify({ v: VERSION, id, method, params: {} }) + '\n');
    });
  }

  private fail(error: Error) {
    this.failed ??= error;
    for (const pending of this.pending.values()) { clearTimeout(pending.timer); pending.reject(this.failed); }
    this.pending.clear();
    if (!this.closing) this.child?.kill();
  }

  /** 退出先发送 EOF，超时才终止本应用拥有的子进程。 */
  async stop() {
    this.closing = true;
    this.fail(new Error('应用正在退出'));
    this.child?.stdin.end();
    const timer = setTimeout(() => this.child?.kill(), 1500);
    await this.exited;
    clearTimeout(timer);
  }
}
