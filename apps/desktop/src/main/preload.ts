import { contextBridge, ipcRenderer } from 'electron';

// 不暴露 invoke/send、路径、命令或 Electron 对象，渲染端无自选通道能力。
contextBridge.exposeInMainWorld('orvia', Object.freeze({
  connectionStatus: () => ipcRenderer.invoke('orvia:connection-status'),
  reconnect: () => ipcRenderer.invoke('orvia:reconnect'),
  chatCancel: (input: unknown) => ipcRenderer.invoke('orvia:chat-cancel', input),
  chatList: () => ipcRenderer.invoke('orvia:chat-list'),
  chatCreate: (input: unknown) => ipcRenderer.invoke('orvia:chat-create', input),
  chatGet: (input: unknown) => ipcRenderer.invoke('orvia:chat-get', input),
  chatSend: (input: unknown) => ipcRenderer.invoke('orvia:chat-send', input),
  chatChooseDirectory: (input: unknown) => ipcRenderer.invoke('orvia:chat-choose-directory', input),
  chatInspect: (input: unknown) => ipcRenderer.invoke('orvia:chat-inspect', input),
  chatApprove: (input: unknown) => ipcRenderer.invoke('orvia:chat-approve', input),
  chatResume: (input: unknown) => ipcRenderer.invoke('orvia:chat-resume', input),
  chatUndo: (input: unknown) => ipcRenderer.invoke('orvia:chat-undo', input),
  health: () => ipcRenderer.invoke('orvia:health'),
  settings: () => ipcRenderer.invoke('orvia:settings'),
  missions: () => ipcRenderer.invoke('orvia:missions'),
  createMission: (input: unknown) => ipcRenderer.invoke('orvia:create-mission', input),
  saveCredential: (input: unknown) => ipcRenderer.invoke('orvia:save-credential', input),
  removeCredential: (role: unknown) => ipcRenderer.invoke('orvia:remove-credential', role),
  chooseDirectory: () => ipcRenderer.invoke('orvia:choose-directory'),
  computerStatus: (missionId: unknown) => ipcRenderer.invoke('orvia:computer-status', missionId),
  computerScan: (input: unknown) => ipcRenderer.invoke('orvia:computer-scan', input),
}));
