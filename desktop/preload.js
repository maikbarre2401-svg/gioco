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
  // azioni assistente (validate nel processo principale)
  doAction: a => ipcRenderer.send('zeph-action', a),
  // avatar personalizzato: cerca avatar.glb e ne restituisce i byte
  loadAvatar: () => {
    try {
      const fs = require('fs');
      const path = require('path');
      const candidates = [
        path.join(__dirname, '..', 'avatars', 'avatar.glb'),
        path.join(__dirname, 'avatar.glb'),
        path.join(__dirname, '..', 'avatar.glb'),
      ];
      for (const p of candidates) {
        if (fs.existsSync(p)) {
          const buf = fs.readFileSync(p);
          return buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
        }
      }
    } catch (e) { /* nessun avatar: si usa Zeph */ }
    return null;
  },
});
