import { _electron as electron, expect, test } from '@playwright/test';
import path from 'node:path';
import { mkdir, mkdtemp, readFile, stat } from 'node:fs/promises';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

const run = promisify(execFile);
const executable = process.env.ORVIA_PACKAGED_EXE;
test.skip(!executable, '需显式提供安装版或目录包 EXE');
test('M08 安装资源、发布 safeStorage、草稿重启及自带 Chromium（无模型/网络）', async () => {
  const results = path.resolve('artifacts/test-results/M08');
  await mkdir(results, { recursive: true });
  const directory = await mkdtemp(path.join(results, 'packaged-profile-'));
  const resources = path.join(path.dirname(path.resolve(executable!)), 'resources');
  const env = { ...process.env, PATH: path.join(process.env.SystemRoot!, 'System32') };
  for (const name of ['ELECTRON_RUN_AS_NODE', 'PYTHONHOME', 'PYTHONPATH', 'DEEPSEEK_API_KEY', 'ZHIPU_API_KEY', 'MIMO_API_KEY', 'TAVILY_API_KEY', 'PLAYWRIGHT_NODEJS_PATH', 'NODE_OPTIONS']) delete (env as NodeJS.ProcessEnv)[name];
  let app = await electron.launch({ executablePath: executable, args: [`--user-data-dir=${directory}`], env });
  const title = 'M08 安装包合成草稿';
  try {
    const actual = await app.evaluate(({ app }) => ({ packaged: app.isPackaged, userData: app.getPath('userData') }));
    expect(actual).toEqual({ packaged: true, userData: directory });
    const page = await app.firstWindow();
    await expect(page.getByRole('status')).toHaveText('健康检查通过 · orvia-backend', { timeout: 25000 });
    await expect(page.getByLabel('凭据类型')).toBeVisible();
    const settings = await page.evaluate(() => window.orvia.settings());
    expect(settings.ok && settings.result.mode).toBe('secure_storage');
    expect(settings.ok && settings.result.profiles.every(p => !p.configured)).toBe(true);
    await page.getByLabel('凭据类型').selectOption('tavily');
    await page.getByLabel('API Key').fill('synthetic-m08-packaged-key');
    await page.getByRole('button', { name: '加密保存' }).click();
    await expect(page.getByText('凭据已更新。', { exact: true })).toBeVisible();
    await expect(page.getByLabel('API Key')).toHaveValue('');
    expect(await readFile(path.join(directory, 'credentials.enc.json'), 'utf8')).not.toContain('synthetic-m08-packaged-key');
    await page.getByLabel('草稿名称').fill(title);
    await page.getByRole('button', { name: '保存草稿' }).click();
    await expect(page.getByText(title, { exact: true })).toBeVisible();
    await app.close();
    app = await electron.launch({ executablePath: executable, args: [`--user-data-dir=${directory}`], env });
    const reopened = await app.firstWindow();
    await expect(reopened.getByText(title, { exact: true })).toBeVisible({ timeout: 25000 });
    await expect(reopened.getByText('Tavily 已配置；搜索与网页读取目前仅提供后端接口。', { exact: true })).toBeVisible();
    await reopened.getByLabel('凭据类型').selectOption('tavily');
    await reopened.getByRole('button', { name: '移除凭据' }).click();
    await expect(reopened.getByText('未配置 Tavily，搜索不可用；公开网页读取不需要搜索凭据。', { exact: true })).toBeVisible();
    await reopened.screenshot({ path: path.join(results, 'packaged-window.png'), fullPage: true });
  } finally { await app.close(); }
  // 使用发布资源内 Node/Playwright 和 Chromium，固定 data 页面不产生网站请求。
  const driver = path.join(resources, 'backend/_internal/playwright/driver');
  const screenshot = path.join(results, 'packaged-chromium.png');
  const browserEnv = { ...env, PLAYWRIGHT_BROWSERS_PATH: path.join(resources, 'chromium') };
  const html = '<html><body><h1>Orvia synthetic packaged browser</h1><script>document.body.dataset.ready="yes"</script></body></html>';
  await run(path.join(driver, 'node.exe'), [path.join(driver, 'package/cli.js'), 'screenshot', '--browser=chromium', `data:text/html;base64,${Buffer.from(html).toString('base64')}`, screenshot], { env: browserEnv, windowsHide: true, timeout: 30000 });
  expect((await stat(screenshot)).size).toBeGreaterThan(1000);
});
