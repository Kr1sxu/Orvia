import { defineConfig } from '@playwright/test';

// 按模块分离结果；保留历史默认值，M07 显式选择自己的报告目录。
const moduleName = process.env.ORVIA_TEST_MODULE === 'M09' ? 'M09' : process.env.ORVIA_TEST_MODULE === 'M08' ? 'M08' : process.env.ORVIA_TEST_MODULE === 'M07' ? 'M07' : process.env.ORVIA_TEST_MODULE === 'M01' ? 'M01' : 'M02';
export default defineConfig({
  testDir: './tests/e2e', timeout: 90000, workers: 1,
  outputDir: `artifacts/test-results/${moduleName}/e2e`,
  reporter: [['list'], ['json', { outputFile: `artifacts/test-results/${moduleName}/e2e.json` }]],
});
