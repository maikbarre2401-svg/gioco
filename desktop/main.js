/* Zeph Desktop — processo principale.
   Crea una striscia trasparente sempre in primo piano lungo il bordo
   inferiore dello schermo (sopra la barra delle applicazioni): Zeph ci
   cammina dentro, sopra le tue finestre, come Desktop Goose. */
'use strict';
const { app, BrowserWindow, Tray, Menu, ipcMain, screen, nativeImage, shell } = require('electron');
const { spawn } = require('child_process');
const path = require('path');

// trasparenza su Linux
app.commandLine.appendSwitch('enable-transparent-visuals');
app.commandLine.appendSwitch('disable-gpu-sandbox');

if (!app.requestSingleInstanceLock()) app.quit();

let win = null;
let chatWin = null;
let tray = null;
const flags = { voice: true, wander: true, follow: false, dog: false };

const STRIP_HEIGHT = 460;

function createZephWindow() {
  const wa = screen.getPrimaryDisplay().workArea; // esclude la taskbar
  win = new BrowserWindow({
    x: wa.x,
    y: wa.y + wa.height - STRIP_HEIGHT,
    width: wa.width,
    height: STRIP_HEIGHT,
    transparent: true,
    frame: false,
    resizable: false,
    movable: false,
    skipTaskbar: true,
    hasShadow: false,
    focusable: false,
    alwaysOnTop: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      sandbox: false, // il preload legge avatar.glb dal disco
    },
  });
  win.setAlwaysOnTop(true, 'screen-saver');
  // click-through: i clic passano alle finestre sotto, tranne quando
  // il renderer segnala che il mouse è sopra Zeph
  win.setIgnoreMouseEvents(true, { forward: true });
  win.loadFile('renderer.html');
  win.on('closed', () => { win = null; });
}

function createChatWindow() {
  if (chatWin) { chatWin.focus(); return; }
  const wa = screen.getPrimaryDisplay().workArea;
  chatWin = new BrowserWindow({
    width: 420,
    height: 96,
    x: wa.x + wa.width - 440,
    y: wa.y + wa.height - STRIP_HEIGHT - 110,
    alwaysOnTop: true,
    resizable: false,
    maximizable: false,
    minimizable: false,
    fullscreenable: false,
    skipTaskbar: false,
    title: 'Parla con Zeph',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      sandbox: false,
    },
  });
  chatWin.setMenuBarVisibility(false);
  chatWin.loadFile('chat.html');
  chatWin.on('closed', () => { chatWin = null; });
}

function sendCmd(cmd) {
  if (win) win.webContents.send('cmd', cmd);
}

function buildTrayMenu() {
  return Menu.buildFromTemplate([
    { label: '💬 Parla con Zeph…', click: () => createChatWindow() },
    { type: 'separator' },
    { label: '👋 Saluta', click: () => sendCmd('saluta') },
    { label: '💃 Balla', click: () => sendCmd('balla') },
    { label: '🦘 Salta', click: () => sendCmd('salta') },
    { label: '🤸 Salto mortale', click: () => sendCmd('flip') },
    { label: '🌀 Piroetta', click: () => sendCmd('spin') },
    { label: '😂 Barzelletta', click: () => sendCmd('barzelletta') },
    { type: 'separator' },
    {
      label: '🚶 Passeggia da solo', type: 'checkbox', checked: flags.wander,
      click: item => { flags.wander = item.checked; sendCmd('wander:' + (item.checked ? 'on' : 'off')); },
    },
    {
      label: '🐶 Rocky il cane', type: 'checkbox', checked: flags.dog,
      click: item => { flags.dog = item.checked; sendCmd('dog:' + (item.checked ? 'on' : 'off')); },
    },
    {
      label: '🖱️ Segui il mouse', type: 'checkbox', checked: flags.follow,
      click: item => { flags.follow = item.checked; sendCmd('follow:' + (item.checked ? 'on' : 'off')); },
    },
    {
      label: '🔊 Voce attiva', type: 'checkbox', checked: flags.voice,
      click: item => { flags.voice = item.checked; sendCmd('mute:' + (item.checked ? 'off' : 'on')); },
    },
    { type: 'separator' },
    { label: '❌ Chiudi Zeph', click: () => app.quit() },
  ]);
}

app.whenReady().then(() => {
  createZephWindow();

  const icon = nativeImage.createFromPath(path.join(__dirname, 'tray-icon.png'));
  tray = new Tray(icon);
  tray.setToolTip('Zeph — il tuo compagno 3D');
  tray.setContextMenu(buildTrayMenu());
  tray.on('click', () => tray.popUpContextMenu());

  ipcMain.on('zeph-interactive', (e, on) => {
    if (win) win.setIgnoreMouseEvents(!on, { forward: true });
  });
  ipcMain.on('chat-message', (e, text) => {
    if (win) win.webContents.send('chat-message', String(text || ''));
  });
  ipcMain.on('zeph-quit', () => app.quit());
  ipcMain.on('zeph-open-chat', () => createChatWindow());

  // permessi: solo microfono e notifiche
  const { session } = require('electron');
  session.defaultSession.setPermissionRequestHandler((wc, permission, cb) => {
    cb(permission === 'media' || permission === 'notifications');
  });

  // azioni "assistente": solo URL/protocolli sicuri e app in lista consentita
  const URL_OK = /^(https?:|mailto:|whatsapp:|tg:|spotify:|discord:|steam:|ms-settings:|ms-windows-store:|microsoft\.windows\.camera:)/i;
  const APP_CMDS = {
    win32: {
      calc: 'calc', notepad: 'notepad', paint: 'mspaint', explorer: 'explorer',
      terminal: 'cmd', taskmgr: 'taskmgr', control: 'control', snip: 'snippingtool',
      word: 'winword', excel: 'excel', powerpoint: 'powerpnt',
    },
    darwin: {
      calc: 'Calculator', notepad: 'TextEdit', paint: 'Preview', explorer: 'Finder',
      terminal: 'Terminal', taskmgr: 'Activity Monitor', control: 'System Settings',
      snip: 'Screenshot', word: 'Microsoft Word', excel: 'Microsoft Excel', powerpoint: 'Microsoft PowerPoint',
    },
    linux: {
      calc: 'gnome-calculator', notepad: 'gedit', paint: 'gimp', explorer: 'nautilus',
      terminal: 'gnome-terminal', taskmgr: 'gnome-system-monitor', control: 'gnome-control-center',
      snip: 'gnome-screenshot',
    },
  };
  ipcMain.on('zeph-action', (e, a) => {
    if (!a || typeof a !== 'object') return;
    if (a.type === 'url' && typeof a.url === 'string' && URL_OK.test(a.url)) {
      shell.openExternal(a.url).catch(() => {});
    } else if (a.type === 'app' && typeof a.id === 'string') {
      const table = APP_CMDS[process.platform] || APP_CMDS.linux;
      const cmd = table[a.id];
      if (!cmd) return;
      try {
        if (process.platform === 'win32') spawn('cmd', ['/c', 'start', '', cmd], { detached: true, stdio: 'ignore' });
        else if (process.platform === 'darwin') spawn('open', ['-a', cmd], { detached: true, stdio: 'ignore' });
        else spawn(cmd, [], { detached: true, stdio: 'ignore' });
      } catch (err) { /* app non disponibile su questo sistema */ }
    } else if (a.type === 'volume' && ['up', 'down', 'mute'].indexOf(a.dir) !== -1) {
      // tasti multimediali di sistema: sicuro e reversibile
      try {
        if (process.platform === 'win32') {
          const code = a.dir === 'up' ? 175 : a.dir === 'down' ? 174 : 173;
          const times = a.dir === 'mute' ? 1 : 5;
          spawn('powershell', ['-NoProfile', '-Command',
            '$w=New-Object -ComObject WScript.Shell; 1..' + times + ' | ForEach-Object { $w.SendKeys([char]' + code + ') }'],
            { detached: true, stdio: 'ignore' });
        } else if (process.platform === 'darwin') {
          const script = a.dir === 'mute' ? 'set volume with output muted'
            : 'set volume output volume ((output volume of (get volume settings)) ' + (a.dir === 'up' ? '+ 10)' : '- 10)');
          spawn('osascript', ['-e', script], { detached: true, stdio: 'ignore' });
        } else {
          const arg = a.dir === 'mute' ? ['set-sink-mute', '@DEFAULT_SINK@', 'toggle']
            : ['set-sink-volume', '@DEFAULT_SINK@', a.dir === 'up' ? '+10%' : '-10%'];
          spawn('pactl', arg, { detached: true, stdio: 'ignore' });
        }
      } catch (err) { /* niente controllo volume */ }
    }
  });
});

// niente finestra = app chiusa (anche su macOS: è un compagno, non un documento)
app.on('window-all-closed', () => app.quit());
