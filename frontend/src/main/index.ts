import { app, BrowserWindow, Tray, Menu, nativeImage, Notification } from 'electron';
import * as path from 'path';

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let reminderInterval: ReturnType<typeof setInterval> | null = null;

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: '律师智能中心',
    icon: path.join(__dirname, '../../public/icon.png'),
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // 开发模式加载 vite 开发服务器，生产模式加载打包后的文件
  if (process.env.NODE_ENV === 'development' || process.argv.includes('--dev')) {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function createTray(): void {
  // 创建系统托盘图标
  const icon = nativeImage.createEmpty();
  tray = new Tray(icon);
  const contextMenu = Menu.buildFromTemplate([
    { label: '显示主窗口', click: () => mainWindow?.show() },
    { label: '退出', click: () => app.quit() },
  ]);
  tray.setToolTip('律师智能中心');
  tray.setContextMenu(contextMenu);
  tray.on('double-click', () => mainWindow?.show());
}

/**
 * 检查开庭提醒（通过后端 API）
 * 每 5 分钟检查一次，有提醒时弹出 Windows 系统通知
 */
async function checkReminders(): Promise<void> {
  try {
    const apiUrl = 'http://127.0.0.1:8000/api/schedules/reminders';
    const response = await fetch(apiUrl, {
      headers: { 'X-Internal-Call': 'electron-main' },
    });

    // 提醒接口允许内部调用（无需完整认证）
    if (!response.ok) return;

    const reminders = await response.json();
    if (!reminders || reminders.length === 0) return;

    for (const item of reminders) {
      const schedule = item.schedule;
      for (const reminder of item.reminders || []) {
        const notification = new Notification({
          title: `📅 ${reminder.label}`,
          body: `${schedule.title}\n${schedule.location || ''}\n时间：${new Date(schedule.start_time).toLocaleString('zh-CN')}`,
          urgency: 'critical',
        });
        notification.show();

        // 托盘闪烁提示
        if (tray) {
          tray.setToolTip(`🔔 ${reminder.label} - ${schedule.title}`);
        }
      }
    }
  } catch {
    // 后端未启动或网络错误，静默忽略
  }
}

app.whenReady().then(() => {
  createWindow();
  createTray();

  // 启动定时提醒检查（每 5 分钟）
  reminderInterval = setInterval(checkReminders, 5 * 60 * 1000);
  // 启动后 10 秒先检查一次
  setTimeout(checkReminders, 10000);

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    // Windows 下关闭所有窗口时保持托盘运行
  }
});

app.on('before-quit', () => {
  if (reminderInterval) clearInterval(reminderInterval);
  tray?.destroy();
});
