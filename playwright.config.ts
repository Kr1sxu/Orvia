import { defineConfig } from '@playwright/test';

// 按模块分离结果；保留历史默认值，M07 显式选择自己的报告目录。
const moduleName = ['V4-006','V4-005','V4-003','V4-004','V4-002','V4-001','V3-005','V3-004','V3-001','V3-002','V3-003','M01','M02','M07','M08','M09','M10','M11','M12','M13','M14','M15','M16','M17','M18','M19','M20'].includes(process.env.ORVIA_TEST_MODULE ?? '') ? process.env.ORVIA_TEST_MODULE! : 'M02';
export default defineConfig({
  testDir: './tests/e2e', timeout: 90000, workers: 1,
  outputDir: `artifacts/test-results/${moduleName}/e2e`,
  reporter: [['list'], ['json', { outputFile: `artifacts/test-results/${moduleName}/e2e.json` }]],
});
