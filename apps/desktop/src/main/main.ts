import { app, BrowserWindow, dialog, ipcMain, session, safeStorage } from 'electron';
import { randomUUID } from 'node:crypto';
import path from 'node:path';
import {stat} from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import { BackendClient, BackendRequestError, BackendConnectionError } from './backend';
import { chatRenameSchema, chatPinSchema, chatDocumentAttachSchema, chatDocumentSourceSchema, chatDocumentAskSchema, chatDocumentPreviewSchema, chatDocumentExportSchema, chatSynthesisPreviewSchema, chatSynthesisGenerateSchema, chatPublicationPreviewSchema, chatPublicationSaveSchema, developmentContextRequestSchema, developmentGenerateRequestSchema, developmentDraftRequestSchema, developmentApplyRequestSchema, cleanupPlanRequestSchema, cleanupExecuteRequestSchema, cleanupRestoreRequestSchema, type DevelopmentContext, type DevelopmentDraft, type CleanupPlan, type SynthesisPreview, type PublicationPreview, chatIdSchema, chatCreateSchema, chatSendSchema, chatApprovalSchema, chatCancelSchema, chatBrowserSearchSchema, chatBrowserReadSchema, chatBrowserAskSchema, chatBrowserSourceSchema, parseInspect } from './chat-contracts';
import { chatErrorMessage } from './chat-errors';
import { mayInvoke } from './ipc-policy';
import { CredentialVault } from './credentials';
import { synchronizeCredentials, CredentialSynchronizationError } from './credentials/synchronize';
import { credentialInputSchema, missionCreateSchema, credentialRoleSchema, computerCallSchema } from './contracts';
import {registerM18} from './m18-ipc';
import {windowPresentation,attachWindowPresentation,taskbarAppId} from './window-presentation';
import {naturalInput,continuationInput,materialRemoveInput,revokeInput,scanPageInput,streamPullInput,streamAckInput,attachmentInput,fallbackConfirmInput} from './m20-contracts';
import {auxiliaryConfig} from './auxiliary-contracts';
import {registerSkills} from './skills-ipc';
import {registerRetrieval} from './retrieval-ipc';
import {registerMemory} from './memory-ipc';
import {registerGraph} from './graph-ipc';
import {registerRewrite} from './rewrite-ipc';
import {registerMcp} from './mcp-ipc';
import {registerShell} from './shell-ipc';
import {registerProcesses} from './process-ipc';
import {registerResearch} from './research-ipc';
import {registerRetry} from './retry-ipc';
import {McpCredentialVault} from './mcp-credentials';

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
  const windowsAppId=taskbarAppId(app.isPackaged,app.getAppPath());
  app.setAppUserModelId(windowsAppId);
  const root = path.resolve(app.getAppPath(), '../..');
  const development = !app.isPackaged;
  // 开发测试可隔离应用数据；此路径只来自本地主进程环境，renderer 无法选择。
  const dataDirectory = development ? path.resolve(process.env.ORVIA_DEV_DATA_DIR ?? path.join(root, '.orvia')) : app.getPath('userData');
  if (development) app.setPath('userData', dataDirectory);
  const vault = new CredentialVault({ development, root, userData: dataDirectory, safeStorage });
  let credentialError: string | null = null;
  try { await vault.load(); } catch (error) { credentialError = error instanceof Error ? error.message : '凭据不可用'; }
  const mcpVault = new McpCredentialVault({userData:dataDirectory,safeStorage});
  // 默认匿名仍可用；损坏凭据保持锁定，不明文回退或自动发送角色Key。
  await mcpVault.load().catch(()=>undefined);
  const createBackend = () => new BackendClient(root, development ? 5000 : 20000, { dataDirectory, credentials: () => vault.getSecrets(), mcpCredentials:()=>mcpVault.getSecrets() },
    development ? undefined : { resourcesPath: process.resourcesPath });
  backend = createBackend();
  let chatBusy = false;
  let reconnecting = false;
  let ordinaryRequests = 0;
  let documentPreviewAuthorization: {id:string;evidence_id:string;format:string;revision:string} | undefined;
  let synthesisAuthorization: {id:string;selection:string;preview:SynthesisPreview} | undefined;
  let publicationAuthorization: {id:string;selection:string;preview:PublicationPreview} | undefined;
  let developmentContextAuthorization: {id:string;selection:string;preview:DevelopmentContext} | undefined;
  let developmentDraftAuthorization: {id:string;draft:DevelopmentDraft} | undefined;
  let cleanupAuthorization: {id:string;plan:CleanupPlan} | undefined;
  let activeSend: { id: string; request_id: string } | undefined;
  let materialProcessing:{id:string;items:{title:string;status:'pending'|'parsing'|'ready'|'failed'|'cancelled'}[]}|undefined;
  let m18Authorization: {clear:()=>void} | undefined;
  let memoryAuthorization: {clear:()=>void} | undefined;
  let mcpAuthorization: {clear:()=>void} | undefined;
  let shellAuthorization: {clear:()=>void} | undefined;
  let processAuthorization: {clear:()=>void} | undefined;
  let researchAuthorization: {clear:()=>void} | undefined;
  let rewriteAuthorization: {clear:()=>void} | undefined;
  let graphAuthorization: {clear:()=>void} | undefined;
  const page = path.join(__dirname, '../renderer/index.html');
  const pageUrl = pathToFileURL(page).href;
  // 模型请求仅后端显式发起；渲染端仍拒绝权限申请及所有联网请求。
  session.defaultSession.setPermissionRequestHandler((_webContents, _permission, callback) => callback(false));
  session.defaultSession.setPermissionCheckHandler(() => false);
  session.defaultSession.webRequest.onBeforeRequest({ urls: ['http://*/*', 'https://*/*', 'ws://*/*', 'wss://*/*'] }, (_details, callback) => callback({ cancel: true }));
  window = new BrowserWindow({ ...windowPresentation(root,app.isPackaged,process.resourcesPath),
    webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true, nodeIntegration: false, sandbox: true, webviewTag: false },
  });
  // Windows任务栏按AppUserModelId分组；明确窗口重启图标，避免仅改EXE后仍回退Electron默认图。
  if(process.platform==='win32')window.setAppDetails({appId:windowsAppId,
    appIconPath:windowPresentation(root,app.isPackaged,process.resourcesPath).icon as string,appIconIndex:0,
    relaunchCommand:app.isPackaged?`"${process.execPath}"`:`"${process.execPath}" "${app.getAppPath()}"`,
    relaunchDisplayName:'序航 Orvia'});
  attachWindowPresentation(window);
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
      // 设置页并发加载仅本地事实投影；允许这些有界读取，审批/外发/执行仍串行。
      const control = ['orvia:retry-history','orvia:research-status','orvia:research-history','orvia:research-cancel','orvia:process-list','orvia:process-status','orvia:process-history','orvia:shell-detect','orvia:shell-history','orvia:shell-status','orvia:shell-cancel','orvia:mcp-list','orvia:mcp-history','orvia:mcp-credential-status','orvia:memory-list','orvia:memory-context','orvia:graph-list','orvia:rewrite-history','orvia:connection-status', 'orvia:chat-cancel','orvia:chat-get','orvia:chat-list','orvia:chat-scan-page','orvia:chat-stream-pull','orvia:chat-stream-ack','orvia:m18-cancel','orvia:m18-script-status','orvia:m18-browser-pending','orvia:m18-browser-close','orvia:m18-history'].includes(channel);
      if (chatBusy && !control) return { ok: false, message: '任务正在处理，请等待完成或取消本次规划。' };
      if (channel === 'orvia:reconnect' && ordinaryRequests) return {ok: false, message: '还有请求正在收尾，请稍候再重新连接。'};
      if (!control) ordinaryRequests++;
      try { return { ok: true, result: await action(...args) }; }
      catch (error) { return { ok: false, message: error instanceof CredentialSynchronizationError ? error.message : error instanceof BackendRequestError || error instanceof BackendConnectionError ? chatErrorMessage(error.code) : '操作失败：请检查输入、凭据状态或重启本地服务' }; }
      finally { if (!control) ordinaryRequests--; }
    });
  }
  handle('orvia:health', 0, () => backend.health());
  handle('orvia:connection-status', 0, async () => ({state: reconnecting ? 'starting' : backend.connectionState,
    busy: chatBusy || reconnecting, cancellable: !!activeSend && backend.connectionState === 'ready', ...(activeSend ? {activeSend} : {}),...(materialProcessing?{materialProcessing}:{})}));
  handle('orvia:reconnect', 0, async () => {
    reconnecting = true;
    try {
      // 旧进程确认退出之后才启动新实例；授权内存丢弃，任何业务请求都不重放。
      await backend.stop();
      if (quitting) throw new Error('应用正在退出');
      activeComputerGrants.clear();
      documentPreviewAuthorization=undefined;
      synthesisAuthorization=undefined;
      publicationAuthorization=undefined;
      developmentContextAuthorization=undefined;
      developmentDraftAuthorization=undefined;
      cleanupAuthorization=undefined;
      memoryAuthorization?.clear();
      graphAuthorization?.clear();
      rewriteAuthorization?.clear();
      mcpAuthorization?.clear();shellAuthorization?.clear();processAuthorization?.clear();researchAuthorization?.clear();
      m18Authorization?.clear();
      materialProcessing=undefined;
      backend = createBackend();
      await backend.start();
      return {connected: true};
    } finally { reconnecting = false; }
  });
  handle('orvia:chat-cancel', 1, async input => {
    const request = chatCancelSchema.parse(input);
    // 等待资料的M20请求也可取消；后端核对会话和请求，旧接续身份由它一次性失效。
    return backend.chatCancel(request);
  });
  // 串行会话操作防止多次点击原生选择器及写动作；后台仍独立检查归属、版本和状态。
  async function chatAction<T>(action: () => Promise<T>) {
    if (chatBusy) throw new Error('会话操作进行中');
    chatBusy = true;
    try { return await action(); } finally { chatBusy = false; }
  }
  m18Authorization=registerM18({handle,serial:chatAction,window:()=>window!,backend:()=>backend});
  registerSkills({handle,serial:chatAction,window:()=>window!,backend:()=>backend});
  registerRetrieval({handle,serial:chatAction,window:()=>window!,backend:()=>backend});
  memoryAuthorization=registerMemory({handle,serial:chatAction,window:()=>window!,backend:()=>backend});
  mcpAuthorization=registerMcp({handle,serial:chatAction,window:()=>window!,backend:()=>backend,vault:()=>mcpVault});
  shellAuthorization=registerShell({handle,serial:chatAction,window:()=>window!,backend:()=>backend});
  processAuthorization=registerProcesses({handle,serial:chatAction,window:()=>window!,backend:()=>backend});
  researchAuthorization=registerResearch({handle,serial:chatAction,window:()=>window!,backend:()=>backend});
  registerRetry({handle,backend:()=>backend});
  rewriteAuthorization=registerRewrite({handle,serial:chatAction,window:()=>window!,backend:()=>backend});
  graphAuthorization=registerGraph({handle,serial:chatAction,window:()=>window!,backend:()=>backend});
  handle('orvia:chat-rename',1,input=>chatAction(()=>backend.chat('chat.rename',chatRenameSchema.parse(input))));
  handle('orvia:chat-pin',1,input=>chatAction(()=>backend.chat('chat.pin',chatPinSchema.parse(input))));
  handle('orvia:chat-delete',1,input=>chatAction(async()=>{
    const request=chatIdSchema.parse(input),check=await backend.chatDeleteCheck(request);
    if(check.blocked)throw new BackendRequestError('DELETE_BLOCKED');
    // renderer只能给会话身份；永久删除必须在主进程原生确认后，后端再核对所有任务状态。
    const decision=await dialog.showMessageBox(window!,{type:'warning',title:'永久删除对话',message:`永久删除“${check.title}”？`,detail:'将永久删除本机的会话消息、引用证据、任务记录和私有脚本副本，无法恢复，也将失去任务撤销入口。不会删除用户原文件、已导出的成品或回滚已发生的操作。备份和磁盘取证擦除不在此操作范围。',buttons:['取消','永久删除'],defaultId:0,cancelId:0,noLink:true});
    if(decision.response!==1)return{id:request.id,cancelled:true as const};
    const result=await backend.chatDelete(request);
    invalidatePreviews();m18Authorization?.clear();activeComputerGrants.delete(request.id);
    return result;
  }));
  handle('orvia:chat-list', 0, () => backend.chatList());
  handle('orvia:chat-create', 1, input => chatAction(() => backend.chat('chat.create', chatCreateSchema.parse(input))));
  handle('orvia:chat-get', 1, input => backend.chat('chat.get', chatIdSchema.parse(input)));
  handle('orvia:chat-natural',1,input=>chatAction(async()=>{
    const request=naturalInput.parse(input);activeSend={id:request.id,request_id:request.request_id};
    try{return await backend.chat('chat.natural',request);}finally{activeSend=undefined;}
  }));
  handle('orvia:chat-continue',1,input=>chatAction(async()=>{
    const request=continuationInput.parse(input);activeSend={id:request.id,request_id:request.request_id};
    try{return await backend.chat('chat.continue',request);}finally{activeSend=undefined;}
  }));
  handle('orvia:chat-fallback-confirm',1,input=>chatAction(async()=>{
    const request=fallbackConfirmInput.parse(input),fresh=await backend.chat('chat.get',{id:request.id}),wf=fresh.workflow;
    if(!wf||wf.action!=='stream_fallback'||wf.request_id!==request.request_id||wf.continuation_id!==request.continuation_id||wf.input?.purpose==='synthesis')throw new BackendRequestError('STALE_APPROVAL');
    const confirmation=await dialog.showMessageBox(window!,{type:'question',title:'明确批准固定Main非流式新请求',message:'向同一deepseek-flash模型发起一次非流式新请求？',detail:'保留固定 https://api.deepseek.com，不更换供应商。此前请求可能已产生费用；本次是明确批准的新请求，可能重复收费。失败或未知结果不会自动重试。',buttons:['取消','批准此次非流式请求'],defaultId:0,cancelId:0,noLink:true});
    if(confirmation.response!==1)return{cancelled:true};
    activeSend={id:request.id,request_id:request.request_id};try{return{cancelled:false,conversation:await backend.chat('chat.fallback.confirm',request)};}finally{activeSend=undefined;}
  }));
  handle('orvia:chat-stream-pull',1,async input=>backend.streamPull(streamPullInput.parse(input)));
  handle('orvia:chat-stream-ack',1,async input=>backend.streamAck(streamAckInput.parse(input)));
  handle('orvia:chat-scan-page',1,input=>backend.scanPage(scanPageInput.parse(input)));
  function invalidatePreviews(){researchAuthorization?.clear();processAuthorization?.clear();mcpAuthorization?.clear();shellAuthorization?.clear();rewriteAuthorization?.clear();graphAuthorization?.clear();memoryAuthorization?.clear();documentPreviewAuthorization=undefined;synthesisAuthorization=undefined;publicationAuthorization=undefined;developmentContextAuthorization=undefined;developmentDraftAuthorization=undefined;}
  handle('orvia:chat-material-remove',1,input=>chatAction(async()=>{invalidatePreviews();return backend.chat('chat.material.remove',materialRemoveInput.parse(input));}));
  handle('orvia:chat-revoke',1,input=>chatAction(async()=>{invalidatePreviews();m18Authorization?.clear();return backend.chat('chat.revoke',revokeInput.parse(input));}));
  handle('orvia:chat-add-files',1,input=>chatAction(async()=>{
    const request=attachmentInput.parse(input);await backend.chat('chat.get',{id:request.id});
    const selection=await dialog.showOpenDialog(window!,{title:'添加本地资料（最多3个，每个10 MiB；不上传云端）',buttonLabel:'添加并在本机解析',properties:['openFile','multiSelections'],filters:[{name:'文档与图片',extensions:['pdf','docx','pptx','png','jpg','jpeg']}]});
    if(selection.canceled||!selection.filePaths.length)return{cancelled:true,items:[]};
    if(selection.filePaths.length>3)throw new BackendRequestError('OUTPUT_LIMIT');
    // 路径只来自原生选择器；预算先查全批，解析仍由后端受限网关复核，不授予父目录。
    const sizes=await Promise.all(selection.filePaths.map(async file=>{const value=await stat(file);if(!value.isFile()||value.size>10*1024*1024)throw new BackendRequestError('OUTPUT_LIMIT');return value.size;}));
    if(sizes.reduce((sum,value)=>sum+value,0)>30*1024*1024)throw new BackendRequestError('OUTPUT_LIMIT');
    const items:{title:string;status:'ready'|'failed'|'cancelled'}[]=[];let conversation;
    materialProcessing={id:request.id,items:selection.filePaths.map(file=>({title:path.basename(file),status:'pending' as const}))};
    try{for(const [index,file] of selection.filePaths.entries()){
      materialProcessing.items[index].status='parsing';
      try{const parseRequestId=randomUUID();activeSend={id:request.id,request_id:parseRequestId};
        conversation=await backend.chat('chat.document.attach',{id:request.id,request_id:parseRequestId,path:file});const message=conversation.messages.at(-1),cancelled=message?.data?.code==='REQUEST_CANCELLED',failed=message?.kind==='error'||!!message?.data?.error,status=cancelled?'cancelled' as const:failed?'failed' as const:'ready' as const;items.push({title:path.basename(file),status});materialProcessing.items[index].status=status;
        if(cancelled){if(conversation.workflow)await backend.chatCancel({id:request.id,request_id:conversation.workflow.request_id});for(const remaining of selection.filePaths.slice(index+1))items.push({title:path.basename(remaining),status:'cancelled'});for(const remaining of materialProcessing.items.slice(index+1))remaining.status='cancelled';break;}
      }
      catch(error){if(error instanceof BackendConnectionError)throw error;items.push({title:path.basename(file),status:'failed'});materialProcessing.items[index].status='failed';}
      finally{activeSend=undefined;}
    }
    conversation=await backend.chat('chat.get',{id:request.id});return{cancelled:false,conversation,items};}finally{materialProcessing=undefined;}
  }));
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
  handle('orvia:chat-document-source',1,input=>chatAction(()=>backend.chatDocumentSource(chatDocumentSourceSchema.parse(input))));
  handle('orvia:chat-document-preview',1,input=>chatAction(async()=>{
    documentPreviewAuthorization=undefined;
    const request=chatDocumentPreviewSchema.parse(input);
    const preview=await backend.chatDocumentPreview(request);
    // 主进程记录实际返回的预览身份；renderer 自造版本不能跳过预览直接保存。
    documentPreviewAuthorization={...request,revision:preview.revision};
    return preview;
  }));
  handle('orvia:chat-document-ask',1,input=>chatAction(()=>backend.chat('chat.document.ask',chatDocumentAskSchema.parse(input))));
  handle('orvia:chat-document-attach',1,input=>chatAction(async()=>{
    const request=chatDocumentAttachSchema.parse(input);
    await backend.chat('chat.get',{id:request.id});
    const selection=await dialog.showOpenDialog(window!,{title:'添加一个本地文档（最多10 MiB）',buttonLabel:'读取此附件',properties:['openFile'],filters:[{name:'文档与图片',extensions:['pdf','docx','pptx','png','jpg','jpeg']}]});
    if(selection.canceled||selection.filePaths.length!==1)return {cancelled:true};
    // 单文件读取不授予父目录权限；Python 经 Computer gateway 再校验路径及大小。
    const conversation=await backend.chat('chat.document.attach',{...request,path:selection.filePaths[0]});
    return {cancelled:false,conversation};
  }));
  handle('orvia:chat-document-export',1,input=>chatAction(async()=>{
    const request=chatDocumentExportSchema.parse(input);
    const authorization=documentPreviewAuthorization;
    documentPreviewAuthorization=undefined;
    if(!authorization||authorization.id!==request.id||authorization.evidence_id!==request.evidence_id||authorization.format!==request.format||authorization.revision!==request.revision)throw new BackendRequestError('STALE_APPROVAL');
    const preview=await backend.chatDocumentPreview({id:request.id,evidence_id:request.evidence_id,format:request.format});
    if(preview.revision!==request.revision)throw new BackendRequestError('STALE_APPROVAL');
    // 原生保存确认仅授权当前证据版本这一次新建写入，绝不转成目录授权或覆盖许可。
    const selection=await dialog.showSaveDialog(window!,{title:'确认保存已预览的引用文档（不覆盖已有文件）',buttonLabel:'确认导出',defaultPath:path.basename(preview.filename),filters:[{name:request.format==='md'?'Markdown':'JSON',extensions:[request.format]}]});
    if(selection.canceled||!selection.filePath)return {cancelled:true};
    const conversation=await backend.chat('chat.document.export',{...request,path:selection.filePath});
    return {cancelled:false,conversation};
  }));
  handle('orvia:chat-synthesis-preview',1,input=>chatAction(async()=>{
    synthesisAuthorization=undefined;
    const request=chatSynthesisPreviewSchema.parse(input);
    const preview=await backend.chatSynthesisPreview(request);
    synthesisAuthorization={id:request.id,selection:JSON.stringify(request),preview};
    return preview;
  }));
  handle('orvia:chat-synthesis-generate',1,input=>chatAction(async()=>{
    const request=chatSynthesisGenerateSchema.parse(input);
    const authorization=synthesisAuthorization;
    synthesisAuthorization=undefined;
    const selection=JSON.stringify({id:request.id,mode:request.mode,question:request.question,sources:request.sources});
    if(!authorization||authorization.id!==request.id||authorization.selection!==selection||authorization.preview.revision!==request.revision)throw new BackendRequestError('STALE_APPROVAL');
    const fresh=await backend.chatSynthesisPreview({id:request.id,mode:request.mode,question:request.question,sources:request.sources});
    if(fresh.revision!==request.revision)throw new BackendRequestError('STALE_APPROVAL');
    // 产品正文上云必须再次经原生确认；renderer 调接口或选择附件本身均不能直接发送。
    const confirmation=await dialog.showMessageBox(window!,{type:'question',title:'确认发送文件内容',
      message:request.stream_mode==='confirmed_nonstream'?`固定Main流式不兼容。明确发起同一deepseek-flash非流式新请求，可能产生第二次费用；发送${fresh.fragments.length}个片段？`:`向 deepseek-flash 发送 ${fresh.fragments.length} 个片段（${fresh.fragments.reduce((n,item)=>n+Array.from(item.text).length,0)} 字）？`,
      detail:'仅发送预览中的内容、来源位置和本次问题，可能产生费用。回答范围以预览为准，结论请结合原文核对。',
      buttons:['取消','确认发送并生成'],defaultId:0,cancelId:0,noLink:true});
    if(confirmation.response!==1)return {cancelled:true};
    activeSend={id:request.id,request_id:request.request_id};
    try{return {cancelled:false,conversation:await backend.chat('chat.synthesis.generate',request)};}
    finally{activeSend=undefined;}
  }));
  handle('orvia:chat-publication-preview',1,input=>chatAction(async()=>{
    publicationAuthorization=undefined;
    const request=chatPublicationPreviewSchema.parse(input);
    const preview=await backend.chatPublicationPreview(request);
    publicationAuthorization={id:request.id,selection:JSON.stringify(request),preview};
    return preview;
  }));
  handle('orvia:chat-publication-save',1,input=>chatAction(async()=>{
    const request=chatPublicationSaveSchema.parse(input);
    const authorization=publicationAuthorization;
    publicationAuthorization=undefined;
    const selection=JSON.stringify({id:request.id,message_id:request.message_id,format:request.format,title:request.title,answer:request.answer,claim_texts:request.claim_texts});
    if(!authorization||authorization.id!==request.id||authorization.selection!==selection||authorization.preview.revision!==request.revision)throw new BackendRequestError('STALE_APPROVAL');
    const fresh=await backend.chatPublicationPreview({id:request.id,message_id:request.message_id,format:request.format,title:request.title,answer:request.answer,claim_texts:request.claim_texts});
    if(fresh.revision!==request.revision)throw new BackendRequestError('STALE_APPROVAL');
    // 原生保存框只授权本次预览版本的一次新文件写入，路径不进入 renderer 或历史消息。
    const chosen=await dialog.showSaveDialog(window!,{title:'保存已预览简报成品（不能覆盖）',buttonLabel:'确认创建新文件',defaultPath:fresh.filename,
      filters:[{name:{docx:'Word 文档',pptx:'PowerPoint 演示',pdf:'PDF 文档'}[request.format],extensions:[request.format]}]});
    if(chosen.canceled||!chosen.filePath)return {cancelled:true};
    const conversation=await backend.chat('chat.publication.save',{...request,path:chosen.filePath});
    return {cancelled:false,conversation};
  }));
  handle('orvia:development-context',1,input=>chatAction(async()=>{
    developmentContextAuthorization=undefined;
    const request=developmentContextRequestSchema.parse(input);
    const preview=await backend.developmentContext(request);
    developmentContextAuthorization={id:request.id,selection:JSON.stringify(request),preview};
    return preview;
  }));
  handle('orvia:development-generate',1,input=>chatAction(async()=>{
    const request=developmentGenerateRequestSchema.parse(input);
    const authorization=developmentContextAuthorization;
    developmentContextAuthorization=undefined;
    const selection=JSON.stringify({id:request.id,requirement:request.requirement,paths:request.paths,sources:request.sources,result_message_id:request.result_message_id});
    if(!authorization||authorization.id!==request.id||authorization.selection!==selection||authorization.preview.revision!==request.context_revision)throw new BackendRequestError('STALE_APPROVAL');
    const fresh=await backend.developmentContext({id:request.id,requirement:request.requirement,paths:request.paths,sources:request.sources,result_message_id:request.result_message_id});
    if(fresh.revision!==request.context_revision)throw new BackendRequestError('STALE_APPROVAL');
    // 文件正文和需求仅此一次送固定 Computer；选择目录本身不授权上云。
    const bytes=new TextEncoder().encode(JSON.stringify({files:fresh.files,fragments:fresh.fragments,saved_result:fresh.saved_result})).length;
    const confirm=await dialog.showMessageBox(window!,{type:'question',title:'确认发送代码需求与选定上下文',
      message:`向固定 Computer glm-5.3-flashx 发送需求、${fresh.files.length} 个文件、${fresh.fragments.length} 个引用片段及${fresh.saved_result?'一条已保存结果':'零条结果'}（约 ${bytes} 字节）？`,
      detail:'请先核对完整预览。可能产生费用；模型只返回待审查草稿，不执行代码或写入项目。',buttons:['取消','确认发送'],defaultId:0,cancelId:0,noLink:true});
    if(confirm.response!==1)return {cancelled:true};
    const draft=await backend.developmentGenerate(request);
    developmentDraftAuthorization={id:request.id,draft};
    return {cancelled:false,draft};
  }));
  handle('orvia:development-draft',1,input=>chatAction(async()=>{
    developmentDraftAuthorization=undefined;
    const request=developmentDraftRequestSchema.parse(input);
    const draft=await backend.developmentDraft(request);
    developmentDraftAuthorization={id:request.id,draft};
    return draft;
  }));
  handle('orvia:development-apply',1,input=>chatAction(async()=>{
    const request=developmentApplyRequestSchema.parse(input);
    const authorization=developmentDraftAuthorization;
    if(!authorization||authorization.id!==request.id||authorization.draft.draft_id!==request.draft_id||authorization.draft.revision!==request.revision)throw new BackendRequestError('STALE_APPROVAL');
    const fresh=await backend.developmentDraft({id:request.id,draft_id:request.draft_id});
    const file=fresh.files[request.index];
    if(fresh.revision!==request.revision||!file||file.status!=='pending'||file.content!==authorization.draft.files[request.index]?.content)throw new BackendRequestError('STALE_APPROVAL');
    const confirm=await dialog.showMessageBox(window!,{type:'warning',title:'逐文件确认代码写入',
      message:`${file.operation==='modify'?'修改':'新建'} ${file.path}？`,
      detail:`版本 ${fresh.revision.slice(0,12)}；请核对已展示的完整差异。写入后仅做字节核验，不执行生成代码。`,
      buttons:['取消','确认写入此文件'],defaultId:0,cancelId:0,noLink:true});
    if(confirm.response!==1)return {cancelled:true};
    developmentDraftAuthorization=undefined;
    const result=await backend.developmentApply(request);
    const draft=await backend.developmentDraft({id:request.id,draft_id:request.draft_id});
    developmentDraftAuthorization={id:request.id,draft};
    return {cancelled:false,result,draft};
  }));
  handle('orvia:cleanup-scan',1,input=>chatAction(async()=>{
    cleanupAuthorization=undefined;
    const request=chatIdSchema.parse(input);
    const plan=await backend.cleanupScan(request);
    cleanupAuthorization={id:request.id,plan};
    return plan;
  }));
  handle('orvia:cleanup-plan',1,input=>chatAction(async()=>{
    cleanupAuthorization=undefined;
    const request=cleanupPlanRequestSchema.parse(input);
    const plan=await backend.cleanupPlan(request);
    cleanupAuthorization={id:request.id,plan};
    return plan;
  }));
  handle('orvia:cleanup-execute',1,input=>chatAction(async()=>{
    const request=cleanupExecuteRequestSchema.parse(input);
    const authorization=cleanupAuthorization;
    cleanupAuthorization=undefined;
    if(!authorization||authorization.id!==request.id||authorization.plan.plan_id!==request.plan_id||authorization.plan.revision!==request.revision)throw new BackendRequestError('STALE_APPROVAL');
    const fresh=await backend.cleanupPlan({id:request.id,plan_id:request.plan_id});
    if(fresh.status!=='planned'||fresh.revision!==request.revision||new Set(request.indices).size!==request.indices.length)throw new BackendRequestError('STALE_APPROVAL');
    const chosen=request.indices.map(index=>fresh.entries[index]);
    if(chosen.some(item=>!item||item.status!=='pending'))throw new BackendRequestError('STALE_APPROVAL');
    const bytes=chosen.reduce((n,item)=>n+item.size,0);
    const confirm=await dialog.showMessageBox(window!,{type:'warning',title:'确认旧临时文件隔离',
      message:`隔离 ${chosen.length} 个已列出的旧临时文件（逻辑大小 ${bytes} 字节）？`,
      detail:`版本 ${request.revision.slice(0,12)}。仅当前用户 Temp 顶层旧 .tmp/.log；30 天内受限恢复。隔离移动不释放磁盘空间。`,
      buttons:['取消','批准此版本并隔离'],defaultId:0,cancelId:0,noLink:true});
    if(confirm.response!==1)return {cancelled:true};
    const plan=await backend.cleanupExecute(request);
    return {cancelled:false,plan};
  }));
  handle('orvia:cleanup-restore',1,input=>chatAction(async()=>{
    const request=cleanupRestoreRequestSchema.parse(input);
    const fresh=await backend.cleanupPlan({id:request.id,plan_id:request.plan_id});
    const entry=fresh.entries[request.index];
    if(!entry||entry.status!=='moved')throw new BackendRequestError('INVALID_STATE');
    const confirm=await dialog.showMessageBox(window!,{type:'question',title:'确认恢复隔离文件',message:`将 ${entry.name} 恢复到原临时目录？`,
      detail:'若原位置已有文件或隔离内容变化，程序拒绝覆盖。',buttons:['取消','确认恢复'],defaultId:0,cancelId:0,noLink:true});
    if(confirm.response!==1)return {cancelled:true};
    const plan=await backend.cleanupRestore(request);
    return {cancelled:false,plan};
  }));
  async function approvedFileAction(method:'chat.approve'|'chat.resume'|'chat.undo',input:unknown){
    const request=chatApprovalSchema.parse(input),fresh=await backend.chat('chat.get',{id:request.id}),operation=fresh.operation;
    if(!operation||operation.operation_id!==request.operation_id||operation.revision!==request.revision)throw new BackendRequestError('STALE_APPROVAL');
    const title=method==='chat.approve'?'确认此版本文件变更':method==='chat.resume'?'确认核验并恢复此文件任务':'确认受限撤销最近文件变更';
    // 对话“同意”、模型计划与renderer均不能代替此版本原生批准；后端仍复核根和文件身份。
    const confirmation=await dialog.showMessageBox(window!,{type:'question',title,message:`${title}（${operation.actions.length}个动作）？`,detail:`版本 ${operation.revision}\n`+operation.actions.map((action,index)=>`${index+1}. ${action.kind}: ${action.source??''} → ${action.destination}`).join('\n')+'\n拒绝覆盖、删除和跨卷移动；执行后须查看程序核验。',buttons:['取消','确认此版本'],defaultId:0,cancelId:0,noLink:true});
    if(confirmation.response!==1)return fresh;
    return backend.chat(method,request);
  }
  handle('orvia:chat-approve', 1, input => chatAction(() => approvedFileAction('chat.approve',input)));
  handle('orvia:chat-resume', 1, input => chatAction(() => approvedFileAction('chat.resume',input)));
  handle('orvia:chat-undo', 1, input => chatAction(() => approvedFileAction('chat.undo',input)));
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
  // 配置仅改变辅助连接；没有服务安装、启动、停止或任意 Redis 命令入口。
  handle('orvia:auxiliary-status',0,()=>backend.auxiliaryStatus());
  handle('orvia:auxiliary-probe',0,()=>backend.auxiliaryProbe());
  handle('orvia:auxiliary-configure',1,input=>backend.auxiliaryConfigure(auxiliaryConfig.parse(input)));
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
