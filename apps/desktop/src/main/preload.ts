import { contextBridge, ipcRenderer } from 'electron';

// 不暴露 invoke/send、路径、命令或 Electron 对象，渲染端无自选通道能力。
contextBridge.exposeInMainWorld('orvia', Object.freeze({
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
