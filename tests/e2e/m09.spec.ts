import { _electron as electron, expect, test } from '@playwright/test';
import path from 'node:path';
import { mkdir, mkdtemp, writeFile } from 'node:fs/promises';

test('M09 桌面整理只读界面闭环（合成目录）', async () => {
  const results = path.resolve(process.env.ORVIA_TEST_RESULTS ?? 'artifacts/test-results/M09');
  await mkdir(results, { recursive: true });
  const profile = await mkdtemp(path.join(results, 'e2e-profile-'));
  const root = await mkdtemp(path.join(results, 'synthetic-root-'));
  await writeFile(path.join(root, '会议记录.txt'), 'synthetic', 'utf8');
  await writeFile(path.join(root, '照片.jpg'), Buffer.alloc(2048));
  const env = { ...process.env, ORVIA_DEV_DATA_DIR: profile, ORVIA_TEST_DIRECTORY: root };
  for (const variable of ['DEEPSEEK_API_KEY', 'ZHIPU_API_KEY', 'MIMO_API_KEY', 'TAVILY_API_KEY']) delete (env as NodeJS.ProcessEnv)[variable];
  const app = await electron.launch({ args: [path.resolve('apps/desktop')], env });
  try {
    const page = await app.firstWindow();
    await expect(page.getByRole('status')).toHaveText('健康检查通过 · orvia-backend');
    await page.getByRole('button', { name: '选择目录' }).click();
    await expect(page.getByText(path.basename(root), { exact: true })).toBeVisible();
    await expect(page.getByText('会议记录.txt', { exact: true })).toBeVisible();
    await page.getByText('会议记录.txt', { exact: true }).click();
    await expect(page.getByText('相对路径').locator('..')).toContainText('会议记录.txt');
    await page.getByLabel('文件名搜索').fill('照片');
    await page.getByRole('button', { name: '搜索' }).click();
    await expect(page.getByText('照片.jpg', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: '刷新' }).click();
    await expect(page.getByText('空间统计', { exact: true })).toBeVisible();
    await page.screenshot({ path: path.join(results, 'm09-window.png'), fullPage: true });
  } finally { await app.close(); }
});
