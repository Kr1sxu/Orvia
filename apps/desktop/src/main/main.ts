import { app, BrowserWindow, ipcMain, session, safeStorage } from 'electron';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { BackendClient } from './backend';
import { mayInvoke } from './ipc-policy';
import { CredentialVault } from './credentials';
import { synchronizeCredentials, CredentialSynchronizationError } from './credentials/synchronize';
import { credentialInputSchema, missionCreateSchema, roleSchema } from './contracts';

let backend: BackendClient;
let window: BrowserWindow | null = null;
let quitting = false;

// 单实例避免两个主进程同时覆盖凭据文件；M02 不支持多工作区进程。
const primaryInstance = app.requestSingleInstanceLock();
if (!primaryInstance) app.quit();

app.whenReady().then(async () => {
  if (!primaryInstance) return;
  const root = path.resolve(app.getAppPath(), '../..');
  const development = !app.isPackaged;
  // 开发测试可隔离应用数据；此路径只来自本地主进程环境，renderer 无法选择。
  const dataDirectory = development ? path.resolve(process.env.ORVIA_DEV_DATA_DIR ?? path.join(root, '.orvia')) : app.getPath('userData');
  if (development) app.setPath('userData', dataDirectory);
  const vault = new CredentialVault({ development, root, userData: dataDirectory, safeStorage });
  let credentialError: string | null = null;
  try { await vault.load(); } catch (error) { credentialError = error instanceof Error ? error.message : '凭据不可用'; }
  backend = new BackendClient(root, 5000, { dataDirectory, credentials: () => vault.getSecrets() });
  const page = path.join(__dirname, '../renderer/index.html');
  const pageUrl = pathToFileURL(page).href;
  // 模型请求仅后端显式发起；渲染端仍拒绝权限申请及所有联网请求。
  session.defaultSession.setPermissionRequestHandler((_webContents, _permission, callback) => callback(false));
  session.defaultSession.setPermissionCheckHandler(() => false);
  session.defaultSession.webRequest.onBeforeRequest({ urls: ['http://*/*', 'https://*/*', 'ws://*/*', 'wss://*/*'] }, (_details, callback) => callback({ cancel: true }));
  window = new BrowserWindow({ width: 1120, height: 880, minWidth: 760, minHeight: 560,
    title: '序航 Orvia', backgroundColor: '#101a24', autoHideMenuBar: true,
    webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true, nodeIntegration: false, sandbox: true, webviewTag: false },
  });
  const contents = window.webContents;
  contents.setWindowOpenHandler(() => ({ action: 'deny' }));
  contents.on('will-navigate', (event) => event.preventDefault());
  contents.on('will-attach-webview', (event) => event.preventDefault());
  function handle(channel: string, count: number, action: (...args: unknown[]) => Promise<unknown>) {
    ipcMain.handle(channel, async (event, ...args: unknown[]) => {
      if (!mayInvoke(event.sender === contents, event.senderFrame === contents.mainFrame, event.senderFrame?.url ?? '', pageUrl, args, count)) {
        return { ok: false, message: '此来源或请求不允许调用该接口' };
      }
      try { return { ok: true, result: await action(...args) }; }
      catch (error) { return { ok: false, message: error instanceof CredentialSynchronizationError ? error.message : '操作失败：请检查输入、凭据状态或重启本地服务' }; }
    });
  }
  handle('orvia:health', 0, () => backend.health());
  handle('orvia:settings', 0, async () => ({ ...await backend.configuration(), mode: development ? 'development' : 'secure_storage',
    encryption_available: safeStorage.isEncryptionAvailable(), credential_error: credentialError, credentials: vault.getStatus() }));
  handle('orvia:missions', 0, () => backend.missions());
  handle('orvia:create-mission', 1, input => backend.createMission(missionCreateSchema.parse(input)));
  handle('orvia:save-credential', 1, async input => {
    const { role, key } = credentialInputSchema.parse(input);
    await vault.save(role, key);
    return synchronizeCredentials(vault, backend);
  });
  handle('orvia:remove-credential', 1, async role => {
    await vault.remove(roleSchema.parse(role));
    return synchronizeCredentials(vault, backend);
  });
  window.on('closed', () => { window = null; });
  await window.loadFile(page);
});

app.on('window-all-closed', () => app.quit());
app.on('before-quit', (event) => {
  if (quitting || !backend) return;
  event.preventDefault();
  quitting = true;
  void backend.stop().finally(() => app.quit());
});
