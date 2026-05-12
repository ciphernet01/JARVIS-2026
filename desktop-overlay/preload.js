const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('JARVIS_DESKTOP', {
  shell: 'electron-overlay',
  version: '2.0.0',
});
