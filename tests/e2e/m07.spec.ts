import { _electron as electron, expect, test } from '@playwright/test';
import path from 'node:path';
import { mkdir, mkdtemp } from 'node:fs/promises';

test('M07 真实 Electron Tavily 加密、私有管道同步与三模型边界（不联网）', async () => {
  const results = path.resolve(process.env.ORVIA_TEST_RESULTS ?? 'artifacts/test-results/M07');
  await mkdir(results, { recursive: true });
  const directory = await mkdtemp(path.join(results, 'electron-'));
  const env = { ...process.env, ORVIA_DEV_DATA_DIR: directory };
  delete (env as NodeJS.ProcessEnv).ELECTRON_RUN_AS_NODE;
  for (const variable of ['DEEPSEEK_API_KEY', 'ZHIPU_API_KEY', 'MIMO_API_KEY', 'TAVILY_API_KEY']) delete (env as NodeJS.ProcessEnv)[variable];
  const app = await electron.launch({ args: [path.resolve('tests/e2e/m10-launch.cjs')], env });
  try {
    const page = await app.firstWindow();
    await expect(page.getByText('本地服务已连接', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: '⚙ 设置' }).click();
    await expect(page.getByText('未配置 Tavily，搜索不可用。', { exact: true })).toBeVisible();
    const result = await app.evaluate(async ({ safeStorage }, args) => {
      const requireModule = process.getBuiltinModule('module').createRequire(args.vaultModule);
      // safeStorage 必须使用原始 CredentialVault，不能沿用无凭据启动器的替身。
      delete requireModule.cache[requireModule.resolve(args.vaultModule)];
      const { CredentialVault } = requireModule(args.vaultModule);
      const { BackendClient } = requireModule(args.backendModule);
      const options = { development: false, root: args.root, userData: args.directory, safeStorage };
      const vault = new CredentialVault(options); await vault.load();
      await vault.save('tavily', 'synthetic-m07-safe-storage');
      const reloaded = new CredentialVault(options); await reloaded.load();
      const client = new BackendClient(args.root, 5000, { dataDirectory: args.directory, credentials: () => reloaded.getSecrets() });
      try {
        const before = await client.configuration();
        await reloaded.remove('tavily');
        await client.replaceCredentials(reloaded.getSecrets());
        const after = await client.configuration();
        return { encrypted: safeStorage.isEncryptionAvailable(), configured: before.search_available,
          removed: !after.search_available, roles: before.profiles.map((p: { role: string }) => p.role) };
      } finally { await client.stop(); }
    }, { root: process.cwd(), directory: path.join(directory, 'synthetic-secure'),
      vaultModule: path.resolve('apps/desktop/dist/main/credentials/index.js'), backendModule: path.resolve('apps/desktop/dist/main/backend.js') });
    expect(result).toEqual({ encrypted: true, configured: true, removed: true, roles: ['main', 'computer', 'browser'] });
    const exposed = await page.evaluate(() => ({
      browser: typeof (window.orvia as any).readWeb, arbitrary: typeof (window.orvia as any).invoke,
    }));
    expect(exposed).toEqual({ browser: 'undefined', arbitrary: 'undefined' });
    await page.screenshot({ path: path.join(results, 'settings.png'), fullPage: true });
  } finally { await app.close(); }
});
