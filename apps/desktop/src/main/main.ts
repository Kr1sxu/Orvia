import { app, BrowserWindow, dialog, ipcMain, session, safeStorage } from 'electron';
import { randomUUID } from 'node:crypto';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { BackendClient, BackendRequestError, BackendConnectionError } from './backend';
import { chatIdSchema, chatCreateSchema, chatSendSchema, chatApprovalSchema, chatCancelSchema, chatBrowserSearchSchema, chatBrowserReadSchema, chatBrowserAskSchema, chatBrowserSourceSchema, parseInspect } from './chat-contracts';
import { chatErrorMessage } from './chat-errors';
import { mayInvoke } from './ipc-policy';
import { CredentialVault } from './credentials';
import { synchronizeCredentials, CredentialSynchronizationError } from './credentials/synchronize';
import { credentialInputSchema, missionCreateSchema, credentialRoleSchema, computerCallSchema } from './contracts';

let backend: BackendClient;
let window: BrowserWindow | null = null;
let quitting = false;
const activeComputerGrants = new Map<string, string>();

// 单实例避免两个主进程同时覆盖凭据文件；M02 不支持多工作区进程。
const primaryInstance = app.requestSingleInstanceLock();
if (!primaryInstance) app.quit();
app.on('second-instance', () => {
  if (window?.isMinimized()) window.restore();
  window?.focus();
});

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
  const createBackend = () => new BackendClient(root, development ? 5000 : 20000, { dataDirectory, credentials: () => vault.getSecrets() },
    development ? undefined : { resourcesPath: process.resourcesPath });
  backend = createBackend();
  let chatBusy = false;
  let reconnecting = false;
  let ordinaryRequests = 0;
  let activeSend: { id: string; request_id: string } | undefined;
  const page = path.join(__dirname, '../renderer/index.html');
  const pageUrl = pathToFileURL(page).href;
  // 模型请求仅后端显式发起；渲染端仍拒绝权限申请及所有联网请求。
  session.defaultSession.setPermissionRequestHandler((_webContents, _permission, callback) => callback(false));
  session.defaultSession.setPermissionCheckHandler(() => false);
  session.defaultSession.webRequest.onBeforeRequest({ urls: ['http://*/*', 'https://*/*', 'ws://*/*', 'wss://*/*'] }, (_details, callback) => callback({ cancel: true }));
  window = new BrowserWindow({ width: 1120, height: 880, minWidth: 760, minHeight: 560,
    title: '序航 Orvia', backgroundColor: '#f7f8fa', autoHideMenuBar: true,
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
      if (quitting || (reconnecting && channel !== 'orvia:connection-status')) return { ok: false, message: '本地服务正在重连或退出，请稍候。' };
      // 防止短超时设置请求排在模型规划后，使正常规划被误判为后端失联。
      if (chatBusy && !['orvia:connection-status', 'orvia:chat-cancel'].includes(channel)) return { ok: false, message: '任务正在处理，请等待完成或取消本次规划。' };
      const control = ['orvia:connection-status', 'orvia:chat-cancel'].includes(channel);
      if (channel === 'orvia:reconnect' && ordinaryRequests) return {ok: false, message: '还有请求正在收尾，请稍候再重新连接。'};
      if (!control) ordinaryRequests++;
      try { return { ok: true, result: await action(...args) }; }
      catch (error) { return { ok: false, message: error instanceof CredentialSynchronizationError ? error.message : error instanceof BackendRequestError || error instanceof BackendConnectionError ? chatErrorMessage(error.code) : '操作失败：请检查输入、凭据状态或重启本地服务' }; }
      finally { if (!control) ordinaryRequests--; }
    });
  }
  handle('orvia:health', 0, () => backend.health());
  handle('orvia:connection-status', 0, async () => ({state: reconnecting ? 'starting' : backend.connectionState,
    busy: chatBusy || reconnecting, cancellable: !!activeSend && backend.connectionState === 'ready', ...(activeSend ? {activeSend} : {})}));
  handle('orvia:reconnect', 0, async () => {
    reconnecting = true;
    try {
      // 旧进程确认退出之后才启动新实例；授权内存丢弃，任何业务请求都不重放。
      await backend.stop();
      if (quitting) throw new Error('应用正在退出');
      activeComputerGrants.clear();
      backend = createBackend();
      await backend.start();
      return {connected: true};
    } finally { reconnecting = false; }
  });
  handle('orvia:chat-cancel', 1, async input => {
    const request = chatCancelSchema.parse(input);
    if (!activeSend || request.id !== activeSend.id || request.request_id !== activeSend.request_id) return {cancelled: false};
    return backend.chatCancel(request);
  });
  // 串行会话操作防止多次点击原生选择器及写动作；后台仍独立检查归属、版本和状态。
  async function chatAction<T>(action: () => Promise<T>) {
    if (chatBusy) throw new Error('会话操作进行中');
    chatBusy = true;
    try { return await action(); } finally { chatBusy = false; }
  }
  handle('orvia:chat-list', 0, () => chatAction(() => backend.chatList()));
  handle('orvia:chat-create', 1, input => chatAction(() => backend.chat('chat.create', chatCreateSchema.parse(input))));
  handle('orvia:chat-get', 1, input => chatAction(() => backend.chat('chat.get', chatIdSchema.parse(input))));
  handle('orvia:chat-send', 1, input => chatAction(async () => {
    const request = chatSendSchema.parse(input);
    activeSend = {id: request.id, request_id: request.request_id};
    try { return await backend.chat('chat.send', request); } finally { activeSend = undefined; }
  }));
  handle('orvia:chat-inspect', 1, input => chatAction(() => backend.chat('chat.inspect', parseInspect(input))));
  handle('orvia:chat-browser-search', 1, input => chatAction(() => { const request = chatBrowserSearchSchema.parse(input); return backend.chat('chat.browser.search', request); }));
  handle('orvia:chat-browser-read', 1, input => chatAction(() => { const request = chatBrowserReadSchema.parse(input); return backend.chat('chat.browser.read', request); }));
  handle('orvia:chat-browser-ask', 1, input => chatAction(() => backend.chat('chat.browser.ask',chatBrowserAskSchema.parse(input))));
  handle('orvia:chat-browser-source', 1, input => chatAction(() => backend.chatSource(chatBrowserSourceSchema.parse(input))));
  handle('orvia:chat-approve', 1, input => chatAction(() => backend.chat('chat.approve', chatApprovalSchema.parse(input))));
  handle('orvia:chat-resume', 1, input => chatAction(() => backend.chat('chat.resume', chatApprovalSchema.parse(input))));
  handle('orvia:chat-undo', 1, input => chatAction(() => backend.chat('chat.undo', chatApprovalSchema.parse(input))));
  handle('orvia:chat-choose-directory', 1, input => chatAction(async () => {
    const { id } = chatIdSchema.parse(input);
    await backend.chat('chat.get', { id });
    const selection = await dialog.showOpenDialog(window!, {
      title: '授权此对话访问一个本地目录', buttonLabel: '选择并授权', properties: ['openDirectory'],
    });
    if (selection.canceled || selection.filePaths.length !== 1) return { cancelled: true };
    // 只有主进程可以提供绝对根；Python 复用 PathPolicy 校验原始路径链和根身份。
    const conversation = await backend.chat('chat.grant', { id, root: selection.filePaths[0] });
    return { cancelled: false, conversation };
  }));
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
    await vault.remove(credentialRoleSchema.parse(role));
    return synchronizeCredentials(vault, backend);
  });
  handle('orvia:choose-directory', 0, async () => {
    const selection = await dialog.showOpenDialog(window!, { title: '选择要扫描的本地目录', properties: ['openDirectory'] });
    if (selection.canceled || !selection.filePaths[0]) return { cancelled: true };
    // 目录绝对路径只在主进程内传给 Computer；renderer 仅得到不可推导的任务/授权标识。
    const mission = await backend.createMission({ client_request_id: randomUUID(), title: '桌面整理只读扫描' });
    const grant = await backend.grantComputer({ mission_id: mission.id, root: selection.filePaths[0] });
    if (!grant.grant_id) throw new Error('目录授权未建立');
    activeComputerGrants.set(mission.id, grant.grant_id);
    return { cancelled: false, mission_id: mission.id, grant_id: grant.grant_id, root_label: grant.root_label, calls_remaining: grant.calls_remaining };
  });
  handle('orvia:computer-status', 1, async missionId => backend.computerStatus(String(missionId)));
  handle('orvia:computer-scan', 1, async input => {
    const request = computerCallSchema.parse(input);
    if (activeComputerGrants.get(request.mission_id) !== request.grant_id) throw new Error('目录授权已失效，请重新选择目录');
    return backend.executeComputer(request);
  });
  window.on('closed', () => { window = null; });
  await window.loadFile(page);
});

app.on('window-all-closed', () => app.quit());
app.on('before-quit', (event) => {
  if (quitting || !backend) return;
  event.preventDefault();
  quitting = true;
  // 无法确认后端退出也不能产生未处理 Promise；下次启动由 SQLite 账本识别中断。
  void backend.stop().catch(() => {}).finally(() => app.quit());
});
