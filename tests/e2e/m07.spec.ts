import { _electron as electron, expect, test } from '@playwright/test';
import path from 'node:path';
import { mkdir, mkdtemp } from 'node:fs/promises';

test('M07 真实 Electron Tavily 加密、私有管道同步与三模型边界（不联网）', async () => {
  const results = path.resolve(process.env.ORVIA_TEST_RESULTS ?? 'artifacts/test-results/M07');
  await mkdir(results, { recursive: true });
  const directory = await mkdtemp(path.join(results, 'electron-'));
  const env = { ...process.env, ORVIA_DEV_DATA_DIR: directory };
  delete (env as NodeJS.ProcessEnv).ELECTRON_RUN_AS_NODE;
  const app = await electron.launch({ args: [path.resolve('apps/desktop')], env });
  try {
    const page = await app.firstWindow();
    await expect(page.getByRole('status')).toHaveText('健康检查通过 · orvia-backend');
    await expect(page.getByText(/Tavily/)).toBeVisible();
    const result = await app.evaluate(async ({ safeStorage }, args) => {
      const requireModule = process.getBuiltinModule('module').createRequire(args.vaultModule);
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
