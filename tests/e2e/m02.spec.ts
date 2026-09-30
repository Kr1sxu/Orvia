import { _electron as electron, expect, test } from '@playwright/test';
import path from 'node:path';
import { mkdir, mkdtemp, readFile } from 'node:fs/promises';

test('真实设置、草稿重启持久化、受限 IPC 与 Windows safeStorage', async () => {
  const results = path.resolve(process.env.ORVIA_TEST_RESULTS ?? 'artifacts/test-results/M02');
  await mkdir(results, { recursive: true });
  const directory = await mkdtemp(path.join(results, 'e2e-profile-'));
  const env = { ...process.env, ORVIA_DEV_DATA_DIR: directory }; delete (env as NodeJS.ProcessEnv).ELECTRON_RUN_AS_NODE;
  for (const variable of ['DEEPSEEK_API_KEY', 'ZHIPU_API_KEY', 'MIMO_API_KEY', 'TAVILY_API_KEY']) delete (env as NodeJS.ProcessEnv)[variable];
  // 无凭据启动器不会读取 .env.local，草稿与协议仍使用真实 SQLite/Python。
  let app = await electron.launch({ args: [path.resolve('tests/e2e/m10-launch.cjs')], env });
  const title = '合成草稿 · 重启后配置保持一致';
  let saved: unknown;
  try {
    const page = await app.firstWindow();
    await expect(page.getByText('本地服务已连接', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: '设置' }).click();
    await expect(page.getByText('deepseek-flash', { exact: true })).toBeVisible();
    await expect(page.getByText('glm-5.3-flashx', { exact: true })).toBeVisible();
    await expect(page.getByText('mimo-v2.6-flash', { exact: true })).toBeVisible();
    // M10 界面以会话为入口；通过保留的窄 API 验证 M02 草稿契约。
    expect((await page.evaluate(name => window.orvia.createMission({ title: name, client_request_id: crypto.randomUUID() }), title)).ok).toBe(true);
    saved = await page.evaluate(async () => {
      const reply = await window.orvia.missions();
      if (!reply.ok) throw new Error('list failed');
      return reply.result.missions;
    });
    const denied = await page.evaluate(async () => ({
      arbitrary: typeof (window.orvia as any).invoke,
      initialize: typeof (window.orvia as any).initialize,
      secrets: typeof (window.orvia as any).getSecrets,
      invalid: await window.orvia.createMission({ title: '合成', client_request_id: crypto.randomUUID(), models: [] } as any),
      devWrite: await window.orvia.saveCredential({ role: 'main', key: 'synthetic-dev-write-must-fail' }),
    }));
    expect(denied.arbitrary).toBe('undefined'); expect(denied.initialize).toBe('undefined'); expect(denied.secrets).toBe('undefined');
    expect(denied.invalid.ok).toBe(false); expect(denied.devWrite.ok).toBe(false);
    // 使用真实 Electron safeStorage 和生产 CredentialVault，仅注入合成秘密。
    const secure = await app.evaluate(async ({ safeStorage }, args) => {
      const requireModule = process.getBuiltinModule('module').createRequire(args.modulePath);
      // 启动器仅隔离主窗口凭据；加密测试重新加载原始类，不能测试 mock。
      delete requireModule.cache[requireModule.resolve(args.modulePath)];
      const { CredentialVault } = requireModule(args.modulePath);
      const options = { development: false, root: args.directory, userData: args.directory, safeStorage };
      const vault = new CredentialVault(options);
      await vault.load();
      await vault.save('main', 'synthetic-windows-encrypted-secret');
      const reloaded = new CredentialVault(options); await reloaded.load();
      const matches = reloaded.getSecrets().main === 'synthetic-windows-encrypted-secret';
      const fs = process.getBuiltinModule('fs');
      const cipher = fs.readFileSync(args.directory + '/credentials.enc.json', 'utf8');
      const plaintextAbsent = !cipher.includes('synthetic-windows-encrypted-secret');
      await reloaded.remove('main');
      return { available: safeStorage.isEncryptionAvailable(), matches, plaintextAbsent, removed: !reloaded.getStatus()[0].configured };
    }, { modulePath: path.resolve('apps/desktop/dist/main/credentials/index.js'), directory: path.join(directory, 'secure') });
    expect(secure).toEqual({ available: true, matches: true, plaintextAbsent: true, removed: true });
    await page.screenshot({ path: path.join(results, 'settings-and-draft.png'), fullPage: true });
    await app.close();
    app = await electron.launch({ args: [path.resolve('tests/e2e/m10-launch.cjs')], env });
    const reopened = await app.firstWindow();
    await expect(reopened.getByText('本地服务已连接', { exact: true })).toBeVisible();
    expect(await reopened.evaluate(async () => { const reply = await window.orvia.missions(); return reply.ok ? reply.result.missions : null; })).toEqual(saved);
  } finally { await app.close(); }
  const database = await readFile(path.join(directory, 'app.sqlite'));
  expect(database.includes(Buffer.from('synthetic-windows-encrypted-secret'))).toBe(false);
});
