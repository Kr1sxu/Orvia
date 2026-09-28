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
  const env = { ...process.env, ORVIA_DEV_DATA_DIR: profile };
  delete (env as NodeJS.ProcessEnv).ELECTRON_RUN_AS_NODE;
  delete (env as NodeJS.ProcessEnv).ORVIA_TEST_DIRECTORY;
  for (const variable of ['DEEPSEEK_API_KEY', 'ZHIPU_API_KEY', 'MIMO_API_KEY', 'TAVILY_API_KEY']) delete (env as NodeJS.ProcessEnv)[variable];
  const app = await electron.launch({ args: [path.resolve('tests/e2e/m10-launch.cjs')], env });
  try {
    const page = await app.firstWindow();
    await expect(page.getByText('本地服务已连接', { exact: true })).toBeVisible();
    // 测试侧替换系统对话框；产品不接收测试目录环境变量或任意 renderer 路径。
    await app.evaluate(({ dialog }, directory) => {
      dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [directory] });
    }, root);
    await page.getByRole('button', { name: '＋ 选择目录', exact: true }).click();
    await expect(page.getByText('会议记录.txt', { exact: true })).toBeVisible();
    await page.getByText('会议记录.txt', { exact: true }).locator('..').getByRole('button', { name: '属性' }).click();
    await expect(page.locator('.result-card').last()).toContainText('修改时间');
    await expect(page.locator('.result-card').last()).toContainText('会议记录.txt');
    await page.getByLabel('文件名搜索').fill('照片');
    await page.getByRole('button', { name: '搜索' }).click();
    await expect(page.locator('.result-card').last()).toContainText('照片.jpg');
    await page.getByRole('button', { name: '空间与大文件' }).click();
    await expect(page.locator('.result-card').last()).toContainText('2.0 KB');
    await page.getByRole('button', { name: '目录列表', exact: true }).click();
    await expect(page.locator('.result-card').last()).toContainText('会议记录.txt');
    await page.screenshot({ path: path.join(results, 'm09-window.png'), fullPage: true });
  } finally { await app.close(); }
});
