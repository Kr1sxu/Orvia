import { _electron as electron, expect, test } from '@playwright/test';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { mkdir, mkdtemp } from 'node:fs/promises';

test('真实窗口 → 受限 IPC → Python → 健康响应与退出清理', async () => {
  // 复用无凭据启动器：Electron/Python/协议均真实，仅模型适配为 mock；本测试不调用模型。
  const env = { ...process.env }; delete env.ELECTRON_RUN_AS_NODE;
  const results = path.resolve(process.env.ORVIA_TEST_RESULTS ?? 'artifacts/test-results/M02');
  await mkdir(results, { recursive: true });
  env.ORVIA_DEV_DATA_DIR = await mkdtemp(path.join(results, 'health-'));
  for (const name of ['DEEPSEEK_API_KEY', 'ZHIPU_API_KEY', 'MIMO_API_KEY', 'TAVILY_API_KEY']) delete env[name];
  const app = await electron.launch({ args: [path.resolve('tests/e2e/m10-launch.cjs')], env });
  let pythonPid: number | undefined;
  try {
    const page = await app.firstWindow();
    await expect(page.getByRole('textbox', { name: '输入需求' })).toBeVisible();
    await expect(page.getByText('本地服务已连接', { exact: true })).toBeVisible();
    const health = await page.evaluate(() => window.orvia.health());
    expect(health.ok).toBe(true);
    // 只查询本次 Electron 的直接子进程 PID，不枚举用户命令行或环境变量。
    const mainPid = await app.evaluate(() => process.pid);
    pythonPid = Number(execFileSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command',
      `(Get-CimInstance Win32_Process -Filter "ParentProcessId=${mainPid} AND Name='python.exe'").ProcessId`], { encoding: 'utf8', windowsHide: true }).trim());
    expect(pythonPid).toBeGreaterThan(0);
    await page.getByRole('button', { name: '⚙ 设置' }).click();
    await page.getByRole('button', { name: '重新检查连接' }).click();
    await expect(page.getByText('本地服务已连接', { exact: true })).toBeVisible();
    expect(await page.evaluate(() => ({ keys: Object.keys(window.orvia), require: typeof (window as any).require, process: typeof (window as any).process })))
      .toEqual({ keys: ['chatList', 'chatCreate', 'chatGet', 'chatSend', 'chatChooseDirectory', 'chatInspect',
        'chatApprove', 'chatResume', 'chatUndo', 'health', 'settings', 'missions', 'createMission',
        'saveCredential', 'removeCredential', 'chooseDirectory', 'computerStatus', 'computerScan'],
        require: 'undefined', process: 'undefined' });
    const security = await app.evaluate(({ BrowserWindow }) => {
      const prefs = BrowserWindow.getAllWindows()[0].webContents.getLastWebPreferences();
      return { sandbox: prefs.sandbox, contextIsolation: prefs.contextIsolation, nodeIntegration: prefs.nodeIntegration };
    });
    expect(security).toEqual({ sandbox: true, contextIsolation: true, nodeIntegration: false });
    await page.screenshot({ path: path.join(results, 'health-window.png'), fullPage: true });
  } finally { await app.close(); }
  expect(() => process.kill(pythonPid!, 0)).toThrow();
});
