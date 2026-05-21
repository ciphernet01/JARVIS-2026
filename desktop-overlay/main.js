const { app, BrowserWindow, Menu, shell, screen, Tray, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');
const http = require('http');
const https = require('https');

const DEFAULT_URL = process.env.JARVIS_WEB_URL || 'http://localhost:3000';
const BACKGROUND = '#020617';
const ROOT_DIR = path.resolve(__dirname, '..');
const LOCAL_BUILD = path.join(ROOT_DIR, 'frontend', 'build', 'index.html');
const WINDOW_OPACITY = 0.85; // Increased default for better readability in shell
let mainWindow = null;
let tray = null;

const singleInstanceLock = app.requestSingleInstanceLock();

if (!singleInstanceLock) {
  app.quit();
}

function urlExists(targetUrl) {
  return new Promise((resolve) => {
    const client = targetUrl.startsWith('https') ? https : http;
    const req = client.request(targetUrl, { method: 'HEAD', timeout: 1500 }, (res) => {
      resolve(res.statusCode >= 200 && res.statusCode < 400);
      res.resume();
    });
    req.on('error', () => resolve(false));
    req.on('timeout', () => {
      req.destroy();
      resolve(false);
    });
    req.end();
  });
}

async function resolveEntry() {
  if (await urlExists(DEFAULT_URL)) {
    return { type: 'url', value: DEFAULT_URL };
  }

  if (fs.existsSync(LOCAL_BUILD)) {
    return { type: 'file', value: LOCAL_BUILD };
  }

  return { type: 'url', value: DEFAULT_URL };
}

function enableAutoLaunch() {
  if (process.platform === 'win32' || process.platform === 'darwin') {
    app.setLoginItemSettings({
      openAtLogin: true,
      openAsHidden: false,
    });
  }
}

function createWindow() {
  const { workAreaSize } = screen.getPrimaryDisplay();

  mainWindow = new BrowserWindow({
    width: workAreaSize.width,
    height: workAreaSize.height,
    minWidth: workAreaSize.width,
    minHeight: workAreaSize.height,
    backgroundColor: '#00000000',
    title: 'A.S.T.R.A Overlay',
    show: false,
    frame: false,
    titleBarStyle: 'hidden',
    transparent: true,
    hasShadow: true,
    alwaysOnTop: true,
    fullscreen: true,
    fullscreenable: false,
    maximizable: false,
    minimizable: false,
    skipTaskbar: false,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  // ── IPC Handlers ──────────────────────────────────────────────────────────
  ipcMain.on('window-control', (event, action, value) => {
    switch (action) {
      case 'close': app.quit(); break;
      case 'minimize': mainWindow.minimize(); break;
      case 'set-opacity': mainWindow.setOpacity(value || WINDOW_OPACITY); break;
      case 'set-always-on-top': mainWindow.setAlwaysOnTop(!!value); break;
      case 'set-click-through': mainWindow.setIgnoreMouseEvents(!!value); break;
    }
  });

  Menu.setApplicationMenu(null);

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.once('ready-to-show', () => {
    mainWindow.setBounds({ x: 0, y: 0, width: workAreaSize.width, height: workAreaSize.height });
    mainWindow.setOpacity(WINDOW_OPACITY);
    mainWindow.show();
    mainWindow.focus();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function createTray() {
  const iconPath = path.join(__dirname, 'assets', 'icon.png');
  // Check if icon exists, fallback to empty if not (to avoid crash)
  tray = new Tray(fs.existsSync(iconPath) ? iconPath : path.join(__dirname, 'package.json')); 
  
  const contextMenu = Menu.buildFromTemplate([
    { label: 'A.S.T.R.A OS', enabled: false },
    { type: 'separator' },
    { label: 'Show Dashboard', click: () => { mainWindow.show(); mainWindow.focus(); } },
    { label: 'Hide Dashboard', click: () => { mainWindow.hide(); } },
    { type: 'separator' },
    { label: 'Always on Top', type: 'checkbox', checked: true, click: (item) => { mainWindow.setAlwaysOnTop(item.checked); } },
    { label: 'Click Through', type: 'checkbox', checked: false, click: (item) => { mainWindow.setIgnoreMouseEvents(item.checked); } },
    { type: 'separator' },
    { label: 'Quit A.S.T.R.A', click: () => { app.isQuitting = true; app.quit(); } }
  ]);

  tray.setToolTip('A.S.T.R.A Spatial Interface');
  tray.setContextMenu(contextMenu);
  
  tray.on('double-click', () => {
    mainWindow.isVisible() ? mainWindow.hide() : mainWindow.show();
  });
}

async function boot() {
  const entry = await resolveEntry();
  createWindow();

  if (entry.type === 'file') {
    await mainWindow.loadFile(entry.value);
    return;
  }

  await mainWindow.loadURL(entry.value);
}

app.whenReady().then(async () => {
  if (!singleInstanceLock) {
    return;
  }

  enableAutoLaunch();
  createTray();
  await boot();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      boot().catch((error) => {
        console.error('Failed to reopen A.S.T.R.A overlay:', error);
      });
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('web-contents-created', (_, contents) => {
  contents.on('will-navigate', (event, navigationUrl) => {
    if (navigationUrl !== DEFAULT_URL && !navigationUrl.startsWith('file://')) {
      event.preventDefault();
      shell.openExternal(navigationUrl);
    }
  });
});
