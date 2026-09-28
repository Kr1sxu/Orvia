import path from 'node:path';
import { afterEach, expect, it, vi } from 'vitest';
import { backendLaunch } from '../src/main/runtime';

afterEach(() => vi.unstubAllEnvs());
it('发布固定资源路径，忽略系统解释器、模型 Key 和浏览器覆盖', () => {
  vi.stubEnv('PATH', 'C:/synthetic-untrusted-python');
  vi.stubEnv('DEEPSEEK_API_KEY', 'synthetic-secret');
  vi.stubEnv('PLAYWRIGHT_BROWSERS_PATH', 'C:/synthetic-user-browser');
  vi.stubEnv('PLAYWRIGHT_NODEJS_PATH', 'C:/untrusted-node.exe');
  const resourcesPath = path.resolve('artifacts/test-results/M08/synthetic resources');
  const launch = backendLaunch('C:/unused-root', { resourcesPath });
  expect(launch.executable).toBe(path.join(resourcesPath, 'backend', 'orvia-backend.exe'));
  expect(launch.args).toEqual([]);
  expect(launch.env.PLAYWRIGHT_BROWSERS_PATH).toBe(path.join(resourcesPath, 'chromium'));
  for (const key of ['PATH', 'PYTHONPATH', 'PYTHONHOME', 'DEEPSEEK_API_KEY', 'PLAYWRIGHT_NODEJS_PATH']) expect(launch.env[key]).toBeUndefined();
});
it('开发仍用固定虚拟环境，发布相对资源路径直接拒绝', () => {
  const root = path.resolve('artifacts/test-results/M08/synthetic-repo');
  expect(backendLaunch(root).executable).toBe(path.join(root, 'backend', '.venv', 'Scripts', 'python.exe'));
  expect(() => backendLaunch(root, { resourcesPath: 'relative' })).toThrow('绝对路径');
});
