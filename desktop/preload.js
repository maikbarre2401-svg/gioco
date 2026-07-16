'use strict';
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('zephBridge', {
  // finestra di Zeph
  setInteractive: on => ipcRenderer.send('zeph-interactive', !!on),
  onCommand: cb => ipcRenderer.on('cmd', (e, c) => cb(c)),
  onChat: cb => ipcRenderer.on('chat-message', (e, t) => cb(t)),
  quit: () => ipcRenderer.send('zeph-quit'),
  // finestra della chat
  sendChat: text => ipcRenderer.send('chat-message', text),
});
