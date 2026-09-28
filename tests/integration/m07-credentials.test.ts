import { promises as fs } from 'node:fs';
import path from 'node:path';
import { expect, it } from 'vitest';
import { CredentialVault } from '../../apps/desktop/src/main/credentials';
import { BackendClient } from '../../apps/desktop/src/main/backend';
import { configurationSchema, credentialInputSchema, roleSchema } from '../../apps/desktop/src/main/contracts';

it('Tavily safeStorage 保存/重载/删除，搜索凭据不会变为第四个模型角色', async () => {
  const base = path.resolve(process.env.ORVIA_TEST_RESULTS ?? 'artifacts/test-results/M07');
  await fs.mkdir(base, { recursive: true });
  const root = await fs.mkdtemp(path.join(base, 'tavily-'));
  const options = { development: false, root, userData: root, safeStorage: {
    isEncryptionAvailable: () => true,
    encryptString: (v: string) => Buffer.from(`synthetic-encrypted:${v}`),
    decryptString: (v: Buffer) => v.toString().slice('synthetic-encrypted:'.length),
  }};
  const vault = new CredentialVault(options); await vault.load();
  await vault.save('tavily', 'synthetic-only-search');
  expect(await fs.readFile(path.join(root, 'credentials.enc.json'), 'utf8')).not.toContain('synthetic-only-search');
  const loaded = new CredentialVault(options); await loaded.load();
  expect(loaded.getSecrets()).toEqual({ tavily: 'synthetic-only-search' });
  expect(JSON.stringify(loaded.getStatus())).not.toContain('synthetic-only-search');
  await loaded.remove('tavily'); await vault.load();
  expect(vault.getSecrets()).toEqual({});
  expect(credentialInputSchema.safeParse({ role: 'tavily', key: 'synthetic' }).success).toBe(true);
  expect(roleSchema.safeParse('tavily').success).toBe(false);
  expect(configurationSchema.shape.search_available.parse(true)).toBe(true);
});

it('Tavily 私有 stdio 注入、替换、状态和模型快照分离（真实 Python，无联网）', async () => {
  const root = path.resolve(process.env.ORVIA_TEST_RESULTS ?? 'artifacts/test-results/M07');
  await fs.mkdir(root, { recursive: true });
  const dataDirectory = await fs.mkdtemp(path.join(root, 'stdio-tavily-'));
  const backend = new BackendClient(process.cwd(), 5000, { dataDirectory, credentials: () => ({ tavily: 'synthetic-stdio-search-key' }) });
  try {
    const configuration = await backend.configuration();
    expect(configuration.search_available).toBe(true);
    expect(configuration.profiles).toHaveLength(3);
    expect(configuration.profiles.every(p => !p.configured)).toBe(true);
    await backend.replaceCredentials({});
    expect((await backend.configuration()).search_available).toBe(false);
  } finally { await backend.stop(); }
  for (const name of await fs.readdir(dataDirectory)) {
    expect((await fs.readFile(path.join(dataDirectory, name))).includes(Buffer.from('synthetic-stdio-search-key'))).toBe(false);
  }
});
