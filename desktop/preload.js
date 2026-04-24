const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("desktopBridge", {
  getRuntimeInfo: () => ipcRenderer.invoke("desktop:getRuntimeInfo"),
  restartBackend: () => ipcRenderer.invoke("desktop:restartBackend"),
});
