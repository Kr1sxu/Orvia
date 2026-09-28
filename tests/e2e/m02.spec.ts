import { _electron as electron, expect, test } from '@playwright/test';
import path from 'node:path';
import { mkdir, mkdtemp, readFile } from 'node:fs/promises';

test('真实设置、草稿重启持久化、受限 IPC 与 Windows safeStorage', async () => {
  await mkdir('artifacts/test-results/M02', { recursive: true });
  const directory = await mkdtemp(path.resolve('artifacts/test-results/M02/e2e-profile-'));
  const env = { ...process.env, ORVIA_DEV_DATA_DIR: directory }; delete (env as NodeJS.ProcessEnv).ELECTRON_RUN_AS_NODE;
  for (const variable of ['DEEPSEEK_API_KEY', 'ZHIPU_API_KEY', 'MIMO_API_KEY', 'TAVILY_API_KEY']) delete (env as NodeJS.ProcessEnv)[variable];
  let app = await electron.launch({ args: [path.resolve('apps/desktop')], env });
  const title = '合成草稿 · 重启后配置保持一致';
  let saved: unknown;
  try {
    const page = await app.firstWindow();
    await expect(page.getByRole('status')).toHaveText('健康检查通过 · orvia-backend');
    await expect(page.getByText('deepseek-flash', { exact: true })).toBeVisible();
    await expect(page.getByText('glm-5.3-flashx', { exact: true })).toBeVisible();
    await expect(page.getByText('mimo-v2.6-flash', { exact: true })).toBeVisible();
    await page.getByLabel('草稿名称').fill(title);
    await page.getByRole('button', { name: '保存草稿' }).click();
    await expect(page.getByText(title, { exact: true })).toBeVisible();
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
    await page.screenshot({ path: 'artifacts/test-results/M02/settings-and-draft.png', fullPage: true });
    await app.close();
    app = await electron.launch({ args: [path.resolve('apps/desktop')], env });
    const reopened = await app.firstWindow();
    await expect(reopened.getByText(title, { exact: true })).toBeVisible();
    expect(await reopened.evaluate(async () => { const reply = await window.orvia.missions(); return reply.ok ? reply.result.missions : null; })).toEqual(saved);
  } finally { await app.close(); }
  const database = await readFile(path.join(directory, 'app.sqlite'));
  expect(database.includes(Buffer.from('synthetic-windows-encrypted-secret'))).toBe(false);
});
