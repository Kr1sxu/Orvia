import { promises as fs } from 'node:fs';
import path from 'node:path';
import { beforeEach, describe, expect, it, vi, afterEach } from 'vitest';
import { CredentialVault, type SafeStorageAdapter } from '../src/main/credentials';

let root: string;
let userData: string;
let adapter: SafeStorageAdapter;
beforeEach(async () => {
  const artifacts = path.resolve('artifacts/test-results/M07');
  await fs.mkdir(artifacts, { recursive: true });
  root = await fs.mkdtemp(path.join(artifacts, 'credentials-'));
  userData = path.join(root, 'userData');
  // 模拟系统加密接口；仅使用合成密钥，测试产物不提供真实加密保障。
  adapter = {
    isEncryptionAvailable: vi.fn(() => true),
    encryptString: vi.fn(value => Buffer.from(`synthetic:${value}`)),
    decryptString: vi.fn(value => {
      if (!value.toString().startsWith('synthetic:')) throw new Error('synthetic-secret-do-not-leak');
      return value.toString().slice(10);
    }),
  };
});
afterEach(() => vi.restoreAllMocks());
function vault(development = false) { return new CredentialVault({ development, root, userData, safeStorage: adapter }); }

describe('凭据存储（模拟 safeStorage，真实临时文件，无模型）', () => {
  it('开发模式解析 BOM、引号、export 与注释，只读且不使用系统存储', async () => {
    const content = '\uFEFF# synthetic\nexport DEEPSEEK_API_KEY="main-synthetic" # comment\nZHIPU_API_KEY=\'computer-synthetic\'\nMIMO_API_KEY=browser-synthetic # comment\nTAVILY_API_KEY=tavily-synthetic';
    await fs.writeFile(path.join(root, '.env.local'), content);
    const store = vault(true); await store.load();
    expect(store.getSecrets()).toEqual({ main: 'main-synthetic', computer: 'computer-synthetic', browser: 'browser-synthetic', tavily: 'tavily-synthetic' });
    expect(store.getStatus().every(item => item.source === 'development_env')).toBe(true);
    await expect(store.save('main', 'replacement')).rejects.toThrow('DEVELOPMENT_READ_ONLY');
    await expect(store.remove('main')).rejects.toThrow('DEVELOPMENT_READ_ONLY');
    expect(await fs.readFile(path.join(root, '.env.local'), 'utf8')).toBe(content);
    expect(adapter.isEncryptionAvailable).not.toHaveBeenCalled();
    await expect(fs.stat(userData)).rejects.toMatchObject({ code: 'ENOENT' });
  });
  it('发布模式不读取开发环境文件，保存/重载/删除且状态不暴露密钥', async () => {
    await fs.writeFile(path.join(root, '.env.local'), 'DEEPSEEK_API_KEY=must-not-load');
    const store = vault(); await store.load(); expect(store.getSecrets()).toEqual({});
    await store.save('main', 'main-synthetic');
    const persisted = await fs.readFile(path.join(userData, 'credentials.enc.json'), 'utf8');
    expect(persisted).not.toContain('main-synthetic');
    expect(JSON.stringify(store.getStatus())).not.toContain('main-synthetic');
    const second = vault(); await second.load(); expect(second.getSecrets()).toEqual({ main: 'main-synthetic' });
    await second.remove('main'); await store.load(); expect(store.getSecrets()).toEqual({});
  });
  it('系统加密不可用时拒绝加载且禁止明文降级', async () => {
    vi.mocked(adapter.isEncryptionAvailable).mockReturnValue(false);
    await expect(vault().load()).rejects.toThrow('ENCRYPTION_UNAVAILABLE');
  });
  it.each(['{', '[]', '{"unknown":"YQ=="}', '{"main":"not-base64"}', '{"main":"YQ=="}'])('损坏或无法解密文件不覆盖：%s', async content => {
    await fs.mkdir(userData); await fs.writeFile(path.join(userData, 'credentials.enc.json'), content);
    const store = vault(); await expect(store.load()).rejects.toThrow('CREDENTIAL_CORRUPT');
    await expect(store.save('main', 'replacement')).rejects.toThrow('NOT_LOADED');
    expect(await fs.readFile(path.join(userData, 'credentials.enc.json'), 'utf8')).toBe(content);
  });
  it('原子替换失败保留磁盘和内存，错误不泄露底层异常', async () => {
    const store = vault(); await store.load(); await store.save('main', 'old-synthetic');
    const before = await fs.readFile(path.join(userData, 'credentials.enc.json'), 'utf8');
    vi.spyOn(fs, 'rename').mockRejectedValueOnce(new Error('new-synthetic-secret'));
    await expect(store.save('main', 'new-synthetic-secret')).rejects.toThrow('CREDENTIAL_WRITE_FAILED: 凭据保存失败');
    expect(store.getSecrets()).toEqual({ main: 'old-synthetic' });
    expect(await fs.readFile(path.join(userData, 'credentials.enc.json'), 'utf8')).toBe(before);
    expect(await fs.readdir(userData)).toEqual(['credentials.enc.json']);
  });
  it('并发保存不会丢失另一角色更新，失败不阻断后续保存', async () => {
    const store = vault(); await store.load();
    await Promise.all([store.save('main', 'a'), store.save('computer', 'b'), store.save('browser', 'c')]);
    await expect(store.save('main', '\ninvalid')).rejects.toThrow('CREDENTIAL_INVALID');
    await store.save('main', 'd');
    const second = vault(); await second.load(); expect(second.getSecrets()).toEqual({ main: 'd', computer: 'b', browser: 'c' });
  });
  it.each(['', '   ', 'x\ry', 'x\ny', 'x'.repeat(4097)])('拒绝无效密钥而不写入', async value => {
    const store = vault(); await store.load();
    await expect(store.save('main', value)).rejects.toThrow('CREDENTIAL_INVALID');
    expect(store.getSecrets()).toEqual({});
  });
});
