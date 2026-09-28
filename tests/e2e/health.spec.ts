import { _electron as electron, expect, test } from '@playwright/test';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

test('真实窗口 → 受限 IPC → Python → 健康响应与退出清理', async () => {
  // 使用真实 Electron 和真实 Python，不模拟任何通信层。
  const env = { ...process.env }; delete env.ELECTRON_RUN_AS_NODE;
  for (const name of ['DEEPSEEK_API_KEY', 'ZHIPU_API_KEY', 'MIMO_API_KEY', 'TAVILY_API_KEY']) delete env[name];
  const app = await electron.launch({ args: [path.resolve('apps/desktop')], env });
  let pythonPid: number | undefined;
  try {
    const page = await app.firstWindow();
    await expect(page.getByRole('heading', { name: '你的本地工作助手' })).toBeVisible();
    await expect(page.getByRole('status')).toHaveText('健康检查通过 · orvia-backend');
    // 只查询本次 Electron 的直接子进程 PID，不枚举用户命令行或环境变量。
    const mainPid = await app.evaluate(() => process.pid);
    pythonPid = Number(execFileSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command',
      `(Get-CimInstance Win32_Process -Filter "ParentProcessId=${mainPid} AND Name='python.exe'").ProcessId`], { encoding: 'utf8', windowsHide: true }).trim());
    expect(pythonPid).toBeGreaterThan(0);
    await page.getByRole('button', { name: '重新检查连接' }).click();
    await expect(page.getByRole('status')).toHaveText('健康检查通过 · orvia-backend');
    expect(await page.evaluate(() => ({ keys: Object.keys(window.orvia), require: typeof (window as any).require, process: typeof (window as any).process })))
      .toEqual({ keys: ['health'], require: 'undefined', process: 'undefined' });
    const security = await app.evaluate(({ BrowserWindow }) => {
      const prefs = BrowserWindow.getAllWindows()[0].webContents.getLastWebPreferences();
      return { sandbox: prefs.sandbox, contextIsolation: prefs.contextIsolation, nodeIntegration: prefs.nodeIntegration };
    });
    expect(security).toEqual({ sandbox: true, contextIsolation: true, nodeIntegration: false });
    await page.screenshot({ path: 'artifacts/test-results/M01/health-window.png' });
  } finally { await app.close(); }
  expect(() => process.kill(pythonPid!, 0)).toThrow();
});
