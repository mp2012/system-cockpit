'use strict';

const { app, BrowserWindow, ipcMain } = require('electron');
const si = require('systeminformation');
const os = require('node:os');
const path = require('node:path');
const { execFile } = require('node:child_process');
const { promisify } = require('node:util');
const { pathToFileURL } = require('node:url');

const execFileAsync = promisify(execFile);
const ignoredProcesses = new Set(['system idle process', 'system', 'idle', 'registry']);
let previousNetwork = null;
let previousDisk = null;
let cachedGpu = { at: 0, value: null };
let collecting = null;

function rate(now, previous, bytes) {
  if (!previous || now <= previous.at) return 0;
  return Math.max(0, (bytes - previous.bytes) / ((now - previous.at) / 1000));
}

function sumInterfaces(interfaces) {
  return interfaces.reduce((totals, item) => {
    const name = String(item.iface || '').toLowerCase();
    if (name === 'lo' || name === 'lo0' || name.startsWith('loopback')) return totals;
    totals.rx += Number(item.rx_bytes) || 0;
    totals.tx += Number(item.tx_bytes) || 0;
    return totals;
  }, { rx: 0, tx: 0 });
}

async function collectGpu() {
  if (Date.now() - cachedGpu.at < 2500) return cachedGpu.value;

  let gpu = null;
  try {
    const { stdout } = await execFileAsync('nvidia-smi', [
      '--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,clocks.current.graphics,power.draw',
      '--format=csv,noheader,nounits'
    ], { timeout: 2500, windowsHide: true });
    const values = stdout.trim().split(/\r?\n/)[0]?.split(',').map(value => value.trim());
    if (values?.length >= 3) {
      const number = index => Number.parseFloat(values[index]) || 0;
      gpu = {
        name: values[0] || 'GPU',
        util: number(1),
        memUsedMb: number(2),
        memTotalMb: number(3),
        temp: number(4),
        clockMHz: number(5),
        powerW: number(6)
      };
    }
  } catch {
    gpu = null;
  }

  cachedGpu = { at: Date.now(), value: gpu };
  return gpu;
}

async function collectStats() {
  if (collecting) return collecting;
  collecting = (async () => {
    const [load, memory, filesystems, network, diskIo, processes, cpu, time, temperature, gpu] = await Promise.all([
      si.currentLoad(),
      si.mem(),
      si.fsSize(),
      si.networkStats(),
      si.fsStats(),
      si.processes(),
      si.cpu(),
      si.time(),
      si.cpuTemperature().catch(() => ({ main: 0 })),
      collectGpu()
    ]);

    const now = Date.now();
    const networkTotals = sumInterfaces(network);
    const diskRead = Number(diskIo?.rx) || 0;
    const diskWrite = Number(diskIo?.wx) || 0;
    const networkRx = (rate(now, previousNetwork && { at: previousNetwork.at, bytes: previousNetwork.rx }, networkTotals.rx) * 8) / 1e6;
    const networkTx = (rate(now, previousNetwork && { at: previousNetwork.at, bytes: previousNetwork.tx }, networkTotals.tx) * 8) / 1e6;
    const diskR = rate(now, previousDisk && { at: previousDisk.at, bytes: previousDisk.read }, diskRead) / 1e6;
    const diskW = rate(now, previousDisk && { at: previousDisk.at, bytes: previousDisk.write }, diskWrite) / 1e6;
    previousNetwork = { at: now, ...networkTotals };
    previousDisk = { at: now, read: diskRead, write: diskWrite };

    const homePath = path.resolve(os.homedir()).toLowerCase();
    const homeFilesystem = filesystems
      .map(item => ({ item, mount: path.resolve(String(item.mount || item.fs || '/').replace(/[\\/]+$/, '') + path.sep).toLowerCase() }))
      .filter(entry => homePath === entry.mount || homePath.startsWith(entry.mount))
      .sort((left, right) => right.mount.length - left.mount.length)[0]?.item || filesystems[0];
    const usedMemory = Math.max(0, memory.total - memory.available);
    const cpuLoad = Number(load.currentLoad) || 0;
    const temp = Number(temperature.main) || 34 + cpuLoad * 0.42;
    const topProc = (processes.list || [])
      .filter(process => !ignoredProcesses.has(String(process.name || '').toLowerCase()))
      .sort((left, right) => (Number(right.cpu) || 0) - (Number(left.cpu) || 0))
      .slice(0, 5)
      .map(process => ({
        name: String(process.name || '?').slice(0, 24),
        cpu: Math.round((Number(process.cpu) || 0) * 10) / 10,
        memMb: Math.round((Number(process.memRss) || 0) / 1024)
      }));

    return {
      hostname: os.hostname() || 'LOCAL-WORKSTATION',
      uptime: Number(time.uptime) || os.uptime(),
      cores: Number(cpu.cores) || os.cpus().length || 1,
      load: Math.round(((Number(load.avgLoad) || (cpuLoad / 100) * (Number(cpu.cores) || 1)) * 100)) / 100,
      cpu: Math.round(cpuLoad * 10) / 10,
      mem: memory.total ? Math.round((usedMemory / memory.total) * 1000) / 10 : 0,
      memUsedGb: Math.round((usedMemory / 1073741824) * 10) / 10,
      memTotalGb: Math.round((memory.total / 1073741824) * 10) / 10,
      disk: Number(homeFilesystem?.use) || 0,
      diskR: Math.round(diskR * 10) / 10,
      diskW: Math.round(diskW * 10) / 10,
      netRx: Math.round(networkRx * 10) / 10,
      netTx: Math.round(networkTx * 10) / 10,
      temp: Math.round(temp * 10) / 10,
      procs: Number(processes.all) || (processes.list || []).length,
      perCpu: (load.cpus || []).map(item => Math.round((Number(item.load) || 0) * 10) / 10),
      topProc,
      gpu
    };
  })();

  try {
    return await collecting;
  } finally {
    collecting = null;
  }
}

function createWindow() {
  const dashboardPath = path.join(app.getAppPath(), '系统数据驾驶舱.html');
  const window = new BrowserWindow({
    width: 1440,
    height: 960,
    minWidth: 960,
    minHeight: 640,
    backgroundColor: '#06101a',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });

  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  window.webContents.on('will-navigate', (event, targetUrl) => {
    if (targetUrl !== pathToFileURL(dashboardPath).href) event.preventDefault();
  });
  window.once('ready-to-show', () => window.show());
  window.loadFile(dashboardPath);
}

ipcMain.handle('stats:get', event => {
  const dashboardUrl = pathToFileURL(path.join(app.getAppPath(), '系统数据驾驶舱.html')).href;
  if (event.senderFrame?.url !== dashboardUrl) {
    throw new Error('Stats are only available to the local dashboard.');
  }
  return collectStats();
});

app.whenReady().then(async () => {
  if (process.argv.includes('--smoke-test')) {
    try {
      console.log(JSON.stringify(await collectStats()));
      app.quit();
    } catch (error) {
      console.error(error);
      app.exit(1);
    }
    return;
  }

  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});