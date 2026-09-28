import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e', timeout: 30000, workers: 1,
  outputDir: 'artifacts/test-results/M01/e2e',
  reporter: [['list'], ['json', { outputFile: 'artifacts/test-results/M01/e2e.json' }]],
});
