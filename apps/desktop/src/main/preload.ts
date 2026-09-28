import { contextBridge, ipcRenderer } from 'electron';

// 不暴露 invoke/send、路径、命令或 Electron 对象，渲染端无自选通道能力。
contextBridge.exposeInMainWorld('orvia', Object.freeze({
  health: () => ipcRenderer.invoke('orvia:health'),
}));
