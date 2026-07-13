import { contextBridge, ipcRenderer } from 'electron';

// 暴露安全的 API 给渲染进程
contextBridge.exposeInMainWorld('electronAPI', {
  // 窗口控制
  minimizeWindow: () => ipcRenderer.send('window:minimize'),
  maximizeWindow: () => ipcRenderer.send('window:maximize'),
  closeWindow: () => ipcRenderer.send('window:close'),

  // 文件操作
  openFileDialog: (options: any) => ipcRenderer.invoke('dialog:openFile', options),
  saveFileDialog: (options: any) => ipcRenderer.invoke('dialog:saveFile', options),

  // 系统通知
  sendNotification: (title: string, body: string) =>
    ipcRenderer.send('notification:send', { title, body }),
});
