const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('JARVIS_DESKTOP', {
  shell: 'electron-overlay',
  version: '2.5.0',
  windowControl: (action, value) => ipcRenderer.send('window-control', action, value)
});
