import { defineConfig } from '@playwright/test';

// 按当前模块分离结果，默认使用正在开发的 M02。
const moduleName = process.env.ORVIA_TEST_MODULE === 'M01' ? 'M01' : 'M02';
export default defineConfig({
  testDir: './tests/e2e', timeout: 30000, workers: 1,
  outputDir: `artifacts/test-results/${moduleName}/e2e`,
  reporter: [['list'], ['json', { outputFile: `artifacts/test-results/${moduleName}/e2e.json` }]],
});
