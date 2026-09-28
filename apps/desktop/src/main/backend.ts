import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { backendLaunch, type PackagedRuntime } from './runtime';
import { JsonLines, VERSION, responseSchema, helloSchema, healthSchema } from './protocol';
import { z } from 'zod';
import { configurationSchema, missionSchema, missionCreateSchema, type MissionCreate } from './contracts';

type Secrets = Partial<Record<'main' | 'computer' | 'browser' | 'tavily', string>>;
type Initialization = { dataDirectory: string; credentials: () => Secrets };

type Pending = { resolve: (value: unknown) => void; reject: (reason: Error) => void; timer: NodeJS.Timeout };

/** 开发使用固定虚拟环境，发布使用 ASAR 外的自带后端；失败不会回退系统 Python。 */
export class BackendClient {
  private child?: ChildProcessWithoutNullStreams;
  private pending = new Map<string, Pending>();
  private ready?: Promise<void>;
  private failed?: Error;
  private closing = false;
  private exited?: Promise<void>;
  constructor(private readonly root: string, private readonly timeoutMs = 5000, private readonly initialization?: Initialization, private readonly packaged?: PackagedRuntime) {}

  start(): Promise<void> {
    // 退出可能先于首次健康检查；阻止排队 IPC 在退出期间创建孤儿进程。
    if (this.failed || this.closing) return Promise.reject(this.failed ?? new Error('应用正在退出'));
    if (this.ready) return this.ready;
    const launch = backendLaunch(this.root, this.packaged);
    this.child = spawn(launch.executable, launch.args, {
      cwd: launch.cwd, shell: false, windowsHide: true, env: launch.env, stdio: 'pipe',
    });
    const lines = new JsonLines();
    this.exited = new Promise((resolve) => {
      this.child!.once('close', () => {
        this.fail(new Error('本地后端连接已关闭'));
        resolve();
      });
    });
    this.child.on('error', () => this.fail(new Error(this.packaged ? '安装包后端无法启动，请检查安装文件完整性' : '无法启动本地 Python 3.12 后端，请先按 README 安装环境')));
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
    this.ready = this.request('hello').then(async (value) => {
      try { helloSchema.parse(value); }
      catch { const error = new Error('后端协议或 Python 版本不兼容'); this.fail(error); throw error; }
      if (this.initialization) {
        // 敏感配置只经私有 stdio 发送，不放进命令行、环境变量或通用日志。
        z.object({ initialized: z.literal(true) }).strict().parse(await this.request('initialize', {
          data_directory: this.initialization.dataDirectory, credentials: this.initialization.credentials(),
        }));
      }
    }).catch(() => {
      // 初始化失败后不留下仍运行但永远不可用的子进程，也不切换空白数据库。
      if (!this.failed) this.fail(new Error('本地后端初始化失败，请检查应用数据版本或重启'));
      throw this.failed!;
    });
    return this.ready;
  }

  /** 握手成功后才开放健康检查；连接失败不自动重放请求。 */
  async health() {
    await this.start();
    return healthSchema.parse(await this.request('health'));
  }

  async configuration() { await this.start(); return configurationSchema.parse(await this.request('configuration.status')); }
  async missions() { await this.start(); return z.object({ missions: z.array(missionSchema) }).strict().parse(await this.request('missions.list')); }
  async createMission(input: MissionCreate) { await this.start(); return missionSchema.parse(await this.request('missions.create', missionCreateSchema.parse(input))); }
  async getMission(id: string) { await this.start(); return missionSchema.parse(await this.request('missions.get', { id: z.string().uuid().parse(id) })); }
  /** 凭据变更不改变已保存 Mission 的模型快照。 */
  async replaceCredentials(credentials: Secrets) { await this.start(); return z.object({ updated: z.literal(true) }).strict().parse(await this.request('credentials.replace', { credentials })); }

  private request(method: 'hello' | 'health' | 'initialize' | 'configuration.status' | 'missions.list' | 'missions.create' | 'missions.get' | 'credentials.replace', params: object = {}): Promise<unknown> {
    if (this.failed) return Promise.reject(this.failed);
    if (this.closing || !this.child) return Promise.reject(new Error('后端不可用'));
    if (this.pending.size >= 16) return Promise.reject(new Error('健康检查请求过于频繁'));
    const id = randomUUID();
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => this.fail(new Error('本地后端响应超时')), this.timeoutMs);
      this.pending.set(id, { resolve, reject, timer });
      this.child!.stdin.write(JSON.stringify({ v: VERSION, id, method, params }) + '\n');
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
