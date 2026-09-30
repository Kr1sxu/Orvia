import { _electron as electron, expect, test, type ElectronApplication } from '@playwright/test';
import { execFile } from 'node:child_process';
import { mkdir, mkdtemp, readFile, stat, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { promisify } from 'node:util';
import { documentFixtures } from '../integration/m13-fixtures';

const executable = process.env.ORVIA_PACKAGED_EXE;
const results = path.resolve('artifacts/test-results/M14');
const run = promisify(execFile);
test.skip(!executable, '需显式提供 M14 安装版或目录包 EXE；开发启动不替代发布资源验证');

/** 仅保留系统 PATH；生成合成夹具的开发 Python 不进入被测发布进程。 */
function packagedEnvironment(): NodeJS.ProcessEnv {
  const env = { ...process.env };
  const excluded = /^(PATH|ELECTRON_RUN_AS_NODE|PYTHONHOME|PYTHONPATH|DEEPSEEK_API_KEY|ZHIPU_API_KEY|MIMO_API_KEY|TAVILY_API_KEY|PLAYWRIGHT_NODEJS_PATH|PLAYWRIGHT_BROWSERS_PATH|NODE_OPTIONS|NODE_PATH|ORVIA_DEV_DATA_DIR|ORVIA_TEST_DIRECTORY|ORVIA_BACKEND.*)$/i;
  for (const key of Object.keys(env)) if (excluded.test(key)) delete env[key];
  env.PATH = path.join(process.env.SystemRoot ?? 'C:\\Windows', 'System32');
  return env;
}

async function fixture() {
  await mkdir(results, { recursive: true });
  const work = await mkdtemp(path.join(results, 'packaged-'));
  documentFixtures(work);
  const profile = path.join(work, 'profile');
  return {
    work, profile,
    launch: () => electron.launch({ executablePath: executable!, cwd: work,
      args: [`--user-data-dir=${profile}`], env: packagedEnvironment() }),
  };
}

/** 只替代系统选择器的用户选择，不修改凭据仓库、解析、存储或授权接口。 */
async function selectDocument(app: ElectronApplication, input: string, output: string) {
  await app.evaluate(({ dialog }, selected) => {
    dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [selected.input] });
    dialog.showSaveDialog = async () => ({ canceled: false, filePath: selected.output });
  }, { input, output });
}

test('M14 发布版 safeStorage、附件引用导出、重启及会话隔离（合成数据，无云调用）', async () => {
  test.setTimeout(180000);
  const { work, profile, launch } = await fixture();
  const output = path.join(work, 'synthetic-export.md');
  let app = await launch();
  try {
    expect(await app.evaluate(({ app }) => ({ packaged: app.isPackaged, userData: app.getPath('userData') })))
      .toEqual({ packaged: true, userData: profile });
    let page = await app.firstWindow();
    await expect(page.getByText('本地服务已连接', { exact: true })).toBeVisible({ timeout: 30000 });
    const settings = await page.evaluate(() => window.orvia.settings());
    expect(settings.ok && settings.result.mode).toBe('secure_storage');
    expect(settings.ok && settings.result.profiles.every(item => !item.configured)).toBe(true);
    expect(settings.ok && settings.result.search_available).toBe(false);
    // 使用明确标记的合成值，仅验证 Windows 实际加密存储，绝不发起搜索。
    await page.getByRole('button', { name: '设置' }).click();
    await page.getByLabel('凭据类型').selectOption('tavily');
    await page.getByLabel('API Key').fill('synthetic-m14-packaged-key');
    await page.getByRole('button', { name: '加密保存' }).click();
    await expect(page.getByText('凭据已更新。', { exact: true })).toBeVisible();
    await expect(page.getByLabel('API Key')).toHaveValue('');
    expect(await readFile(path.join(profile, 'credentials.enc.json'), 'utf8')).not.toContain('synthetic-m14-packaged-key');
    await page.getByRole('button', { name: '关闭设置' }).click();
    for (const label of ['自动任务', '技能广场', '插件市场', '团队管理', '管家团队', '推荐信息流']) {
      await expect(page.getByText(label, { exact: true })).toHaveCount(0);
    }
    expect(await page.evaluate(() => ({ node: typeof (window as any).require,
      ipc: typeof (window.orvia as any).invoke, grant: typeof (window.orvia as any).chatGrant })))
      .toEqual({ node: 'undefined', ipc: 'undefined', grant: 'undefined' });
    await selectDocument(app, path.join(work, 'synthetic.docx'), output);
    await page.getByRole('button', { name: '添加附件', exact: true }).click();
    const card = page.getByLabel('文档与引用').last();
    await expect(card).toContainText('synthetic.docx', { timeout: 60000 });
    await card.locator('summary').first().click();
    await card.getByRole('button', { name: '查看文档证据', exact: true }).click();
    const detail = page.getByLabel('文档证据详情');
    await expect(detail).toContainText('保留来源');
    await expect(page.getByLabel('当前操作计划')).toHaveCount(0);
    await detail.getByRole('button', { name: '预览 Markdown 导出' }).click();
    const preview = page.getByLabel('文档导出预览');
    await expect(preview).toContainText('2/2');
    await preview.getByRole('button', { name: '选择路径并确认导出' }).click();
    await expect(page.getByText('已创建新导出文件并核验；不会覆盖已有文件。')).toBeVisible();
    await expect(page.getByLabel('文档导出记录')).toContainText('synthetic-export.md');
    const saved = await readFile(output, 'utf8');
    expect(saved).toContain('保留来源'); expect(saved).toContain('SHA256');
    await detail.getByRole('button', { name: '预览 Markdown 导出' }).click();
    await preview.getByRole('button', { name: '选择路径并确认导出' }).click();
    await expect(page.getByText('目标已存在，请选择新的文件名', { exact: true })).toBeVisible();
    expect(await readFile(output, 'utf8')).toBe(saved);
    await page.screenshot({ path: path.join(results, 'packaged-document-export.png'), fullPage: true });

    await app.close(); app = await launch(); page = await app.firstWindow();
    await expect(page.getByText('本地服务已连接', { exact: true })).toBeVisible({ timeout: 30000 });
    const restored = await page.evaluate(() => window.orvia.settings());
    expect(restored.ok && restored.result.search_available).toBe(true);
    await page.getByRole('button', { name: '设置' }).click();
    await page.getByLabel('凭据类型').selectOption('tavily');
    await page.getByRole('button', { name: '移除凭据' }).click();
    await expect(page.getByText('未配置 Tavily，搜索不可用；仍可读取已知公开网页。', { exact: true })).toBeVisible();
    expect(JSON.parse(await readFile(path.join(profile, 'credentials.enc.json'), 'utf8'))).toEqual({});
    await page.getByRole('button', { name: '关闭设置' }).click();
    await page.getByRole('navigation', { name: '历史会话' }).getByRole('button').first().click();
    await expect(page.getByLabel('文档导出记录')).toContainText('synthetic-export.md');
    await page.getByLabel('需求类型').selectOption('document');
    await page.getByLabel('输入需求').fill('许可'); await page.getByLabel('输入需求').press('Enter');
    await expect(page.getByLabel('文档与引用')).toHaveCount(2);
    await page.getByRole('button', { name: '新建对话', exact: true }).click();
    await page.getByLabel('需求类型').selectOption('document');
    await page.getByLabel('输入需求').fill('许可'); await page.getByLabel('输入需求').press('Enter');
    await expect(page.getByText('请先添加文档附件。', { exact: true })).toBeVisible();
    await expect(page.getByLabel('文档与引用')).toHaveCount(0);
    await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].setSize(760, 560));
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: path.join(results, 'packaged-conversation-narrow.png') });
  } finally { await app.close(); }
});

test('M14 发布资源本地 OCR 可识别合成图片并提供置信度（无下载）', async () => {
  test.setTimeout(120000);
  const { work, launch } = await fixture(); const app = await launch();
  try {
    const page = await app.firstWindow();
    await expect(page.getByText('本地服务已连接', { exact: true })).toBeVisible({ timeout: 30000 });
    await selectDocument(app, path.join(work, 'synthetic.png'), path.join(work, 'unused.md'));
    await page.getByRole('button', { name: '添加附件', exact: true }).click();
    const card = page.getByLabel('文档与引用').last();
    await expect(card).toContainText('synthetic.png', { timeout: 60000 });
    await card.locator('summary').first().click();
    await card.getByRole('button', { name: '查看文档证据' }).click();
    const detail = page.getByLabel('文档证据详情');
    await expect(detail).toContainText('OCR 识别'); await expect(detail).toContainText('置信度');
    await expect(detail).toContainText('ORVIA');
    await page.screenshot({ path: path.join(results, 'packaged-ocr-evidence.png'), fullPage: true });
  } finally { await app.close(); }
});

test('M14 自带 Node、Playwright 和 Chromium 可渲染本地 data 页面', async () => {
  await mkdir(results, { recursive: true });
  const resources = path.join(path.dirname(path.resolve(executable!)), 'resources');
  const driver = path.join(resources, 'backend/_internal/playwright/driver');
  const screenshot = path.join(results, 'packaged-chromium.png');
  const env = { ...packagedEnvironment(), PLAYWRIGHT_BROWSERS_PATH: path.join(resources, 'chromium') };
  const html = '<html><body><h1>Orvia M14 synthetic packaged browser</h1><script>document.body.dataset.ready="yes"</script></body></html>';
  await run(path.join(driver, 'node.exe'), [path.join(driver, 'package/cli.js'), 'screenshot', '--browser=chromium',
    `data:text/html;base64,${Buffer.from(html).toString('base64')}`, screenshot], { env, windowsHide: true, timeout: 30000 });
  expect((await stat(screenshot)).size).toBeGreaterThan(1000);
});

test('M14 发布版目录授权重启失效、无凭据搜索及私有 URL 拒绝（无模型网络）', async () => {
  test.setTimeout(120000);
  const { work, launch } = await fixture();
  const directory = path.join(work, 'synthetic-directory');
  await mkdir(directory);
  await writeFile(path.join(directory, 'M14合成说明.txt'), 'M14 synthetic local directory fixture', 'utf8');
  let app = await launch();
  try {
    let page = await app.firstWindow();
    await expect(page.getByText('本地服务已连接', { exact: true })).toBeVisible({ timeout: 30000 });
    await app.evaluate(({ dialog }, selected) => {
      dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [selected] });
    }, directory);
    await page.getByRole('button', { name: '选择目录', exact: true }).click();
    await expect(page.getByText('M14合成说明.txt', { exact: true })).toBeVisible();
    await expect(page.locator('.directory-bar')).toContainText('已授权：synthetic-directory');
    await expect(page.getByRole('button', { name: '目录列表', exact: true })).toBeEnabled();
    const id = await page.evaluate(async () => {
      const reply = await window.orvia.chatList();
      if (!reply.ok || reply.result.conversations.length !== 1) throw new Error('合成会话数量异常');
      return reply.result.conversations[0].id;
    });
    // Tavily 缺失在发送 HTTP 前拒绝；字面量环回 IP 在 DNS/HTTP 前拒绝。
    await page.getByLabel('需求类型').selectOption('search');
    await expect(page.locator('#composer-hint')).toContainText('搜索不可用');
    await page.getByLabel('输入需求').fill('M14 合成来源');
    await page.getByLabel('输入需求').press('Enter');
    await expect(page.locator('.source-card').last()).toContainText('SEARCH_UNAVAILABLE');
    await expect(page.getByLabel('需求类型')).toBeEnabled();
    await page.getByLabel('需求类型').selectOption('read');
    await page.getByLabel('输入需求').fill('http://127.0.0.1/');
    await page.getByLabel('输入需求').press('Enter');
    await expect(page.locator('.source-card').last()).toContainText('URL_BLOCKED');
    await expect(page.getByLabel('当前操作计划')).toHaveCount(0);
    await expect(page.getByLabel('需求类型')).toBeEnabled();
    await page.screenshot({ path: path.join(results, 'packaged-directory-and-browser-rejection.png'), fullPage: true });

    await app.close(); app = await launch(); page = await app.firstWindow();
    await expect(page.getByText('本地服务已连接', { exact: true })).toBeVisible({ timeout: 30000 });
    await page.getByRole('navigation', { name: '历史会话' }).getByRole('button').first().click();
    await expect(page.getByText('当前未授权目录；历史记录不会恢复目录权限。', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: '目录列表', exact: true })).toHaveCount(0);
    await expect(page.getByText('M14合成说明.txt', { exact: true })).toBeVisible();
    // 历史扫描可以展示，但固定业务 IPC 也不得借旧会话恢复文件读取权限。
    const denied = await page.evaluate(conversationId => window.orvia.chatInspect({
      id: conversationId, tool: 'list_directory', arguments: { path: '.', limit: 100 },
    }), id);
    expect(denied.ok).toBe(false);
    await page.screenshot({ path: path.join(results, 'packaged-directory-permission-expired.png'), fullPage: true });
  } finally { await app.close(); }
});
