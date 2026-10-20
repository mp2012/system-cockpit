'use strict';

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('systemCockpit', {
  getStats: () => ipcRenderer.invoke('stats:get')
});