import { promises as fs } from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';

export const roles = ['main', 'computer', 'browser', 'tavily', 'redis'] as const;
export type CredentialRole = typeof roles[number];
type Secrets = Partial<Record<CredentialRole, string>>;
export interface SafeStorageAdapter {
  isEncryptionAvailable(): boolean;
  encryptString(value: string): Buffer;
  decryptString(value: Buffer): string;
}
interface Options {
  development: boolean;
  root: string;
  userData: string;
  safeStorage: SafeStorageAdapter;
}
const variables = { main: 'DEEPSEEK_API_KEY', computer: 'ZHIPU_API_KEY', browser: 'MIMO_API_KEY', tavily: 'TAVILY_API_KEY', redis: 'REDIS_PASSWORD' };
const invalid = () => new Error('CREDENTIAL_INVALID: 密钥必须为非空单行文本且不超过 4096 字符');
function validKey(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0 && value.length <= 4096 && !/[\r\n]/.test(value);
}

/** 主进程私有凭据仓库；开发与发布存储完全隔离，任何错误均不携带密钥或底层错误正文。 */
export class CredentialVault {
  private secrets: Secrets = {};
  private loaded = false;
  private pending: Promise<void> = Promise.resolve();
  constructor(private readonly options: Options) {}

  private serial(action: () => Promise<void>): Promise<void> {
    const operation = this.pending.then(action);
    this.pending = operation.catch(() => undefined);
    return operation;
  }
  private requireEncryption(): void {
    if (!this.options.safeStorage.isEncryptionAvailable()) {
      throw new Error('CREDENTIAL_ENCRYPTION_UNAVAILABLE: 系统安全存储不可用');
    }
  }
  private get filename(): string { return path.join(this.options.userData, 'credentials.enc.json'); }

  /** 只加载指定运行模式的来源；损坏数据使仓库保持锁定，防止后续保存覆盖原文件。 */
  load(): Promise<void> {
    return this.serial(async () => {
      this.loaded = false;
      this.secrets = {};
      if (!this.options.development) this.requireEncryption();
      let text: string;
      try {
        text = await fs.readFile(this.options.development ? path.join(this.options.root, '.env.local') : this.filename, 'utf8');
      } catch (error) {
        if ((error as NodeJS.ErrnoException).code === 'ENOENT') { this.loaded = true; return; }
        throw new Error('CREDENTIAL_READ_FAILED: 无法读取凭据');
      }
      const next: Secrets = {};
      try {
        if (this.options.development) {
          // 只解析固定变量，绝不执行表达式、展开环境变量；搜索凭据与模型凭据分开命名。
          const values = new Map<string, string>();
          for (const line of text.replace(/^\uFEFF/, '').split(/\r?\n/)) {
            const match = line.match(/^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/);
            if (!match || !Object.values(variables).includes(match[1])) continue;
            let value = match[2];
            if (value.startsWith('"') || value.startsWith("'")) {
              const quoted = value.match(/^(["'])(.*?)\1\s*(?:#.*)?$/);
              if (!quoted) throw invalid();
              value = quoted[2];
            } else value = value.replace(/\s+#.*$/, '').trim();
            values.set(match[1], value);
          }
          for (const role of roles) {
            const value = values.get(variables[role]);
            if (value === undefined || value === '') continue;
            if (!validKey(value)) throw invalid();
            next[role] = value;
          }
        } else {
          const parsed: unknown = JSON.parse(text);
          if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw invalid();
          for (const [role, encrypted] of Object.entries(parsed)) {
            if (!roles.includes(role as CredentialRole) || typeof encrypted !== 'string' || !encrypted || Buffer.from(encrypted, 'base64').toString('base64') !== encrypted) throw invalid();
            const value = this.options.safeStorage.decryptString(Buffer.from(encrypted, 'base64'));
            if (!validKey(value)) throw invalid();
            next[role as CredentialRole] = value;
          }
        }
      } catch {
        throw new Error('CREDENTIAL_CORRUPT: 凭据格式损坏或无法解密');
      }
      this.secrets = next;
      this.loaded = true;
    });
  }

  /** 仅供主进程向后端私有管道注入；禁止将结果返回 renderer 或写入日志。 */
  getSecrets(): Secrets { return { ...this.secrets }; }

  /** 可公开给界面的状态仅含角色、是否配置、来源，不含密钥或密钥片段。 */
  getStatus(): { role: CredentialRole; configured: boolean; source: 'development_env' | 'safe_storage' | 'missing' }[] {
    return roles.map(role => ({ role, configured: !!this.secrets[role], source: this.secrets[role] ? (this.options.development ? 'development_env' : 'safe_storage') : 'missing' }));
  }

  /** 发布版保存；串行提交完整快照，原子替换成功后才改变内存。 */
  save(role: CredentialRole, key: string): Promise<void> {
    return this.change(role, key);
  }
  /** 发布版删除指定角色；开发模式只能由用户编辑 .env.local。 */
  remove(role: CredentialRole): Promise<void> { return this.change(role, undefined); }

  private change(role: CredentialRole, key: string | undefined): Promise<void> {
    return this.serial(async () => {
      if (this.options.development) throw new Error('CREDENTIAL_DEVELOPMENT_READ_ONLY: 开发凭据只能编辑 .env.local');
      if (!this.loaded) throw new Error('CREDENTIAL_NOT_LOADED: 请先成功加载凭据');
      if (!roles.includes(role) || (key !== undefined && !validKey(key))) throw invalid();
      this.requireEncryption();
      const next = { ...this.secrets };
      if (key === undefined) delete next[role]; else next[role] = key;
      const temporary = `${this.filename}.${randomUUID()}.tmp`;
      try {
        const encrypted: Partial<Record<CredentialRole, string>> = {};
        for (const item of roles) if (next[item]) encrypted[item] = this.options.safeStorage.encryptString(next[item]!).toString('base64');
        await fs.mkdir(this.options.userData, { recursive: true });
        await fs.writeFile(temporary, JSON.stringify(encrypted), { encoding: 'utf8', mode: 0o600, flag: 'wx' });
        await fs.rename(temporary, this.filename);
      } catch {
        // 临时文件只含系统加密数据；清理失败不掩盖主要失败，内存仍保持原状态。
        await fs.unlink(temporary).catch(() => undefined);
        throw new Error('CREDENTIAL_WRITE_FAILED: 凭据保存失败');
      }
      this.secrets = next;
    });
  }
}
