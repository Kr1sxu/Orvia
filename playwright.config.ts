import { defineConfig } from '@playwright/test';

// 按模块分离结果；保留历史默认值，M07 显式选择自己的报告目录。
const moduleName = ['M01','M02','M07','M08','M09','M10','M11','M12','M13','M14','M17'].includes(process.env.ORVIA_TEST_MODULE ?? '') ? process.env.ORVIA_TEST_MODULE! : 'M02';
export default defineConfig({
  testDir: './tests/e2e', timeout: 90000, workers: 1,
  outputDir: `artifacts/test-results/${moduleName}/e2e`,
  reporter: [['list'], ['json', { outputFile: `artifacts/test-results/${moduleName}/e2e.json` }]],
});
