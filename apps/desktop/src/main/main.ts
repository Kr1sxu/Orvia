import { app, BrowserWindow, ipcMain, session } from 'electron';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { BackendClient } from './backend';
import { mayCheckHealth } from './ipc-policy';

let backend: BackendClient;
let window: BrowserWindow | null = null;
let quitting = false;

app.whenReady().then(async () => {
  backend = new BackendClient(path.resolve(app.getAppPath(), '../..'));
  const page = path.join(__dirname, '../renderer/index.html');
  const pageUrl = pathToFileURL(page).href;
  // M01 无联网需求，拒绝权限请求及 HTTP(S)/WebSocket 请求。
  session.defaultSession.setPermissionRequestHandler((_webContents, _permission, callback) => callback(false));
  session.defaultSession.setPermissionCheckHandler(() => false);
  session.defaultSession.webRequest.onBeforeRequest({ urls: ['http://*/*', 'https://*/*', 'ws://*/*', 'wss://*/*'] }, (_details, callback) => callback({ cancel: true }));
  window = new BrowserWindow({ width: 1050, height: 740, minWidth: 760, minHeight: 560,
    title: '序航 Orvia', backgroundColor: '#101a24', autoHideMenuBar: true,
    webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true, nodeIntegration: false, sandbox: true, webviewTag: false },
  });
  const contents = window.webContents;
  contents.setWindowOpenHandler(() => ({ action: 'deny' }));
  contents.on('will-navigate', (event) => event.preventDefault());
  contents.on('will-attach-webview', (event) => event.preventDefault());
  ipcMain.handle('orvia:health', async (event, ...args: unknown[]) => {
    if (!mayCheckHealth(event.sender === contents, event.senderFrame === contents.mainFrame, event.senderFrame?.url ?? '', pageUrl, args)) {
      return { ok: false, message: '此来源或请求不允许调用健康检查' };
    }
    try { return { ok: true, result: await backend.health() }; }
    catch (error) { return { ok: false, message: error instanceof Error ? error.message : '本地后端不可用' }; }
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
