const { app, BrowserWindow, dialog, ipcMain, shell } = require("electron");
const path = require("node:path");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const net = require("node:net");
const http = require("node:http");

const DEFAULT_HOST = "127.0.0.1";
const DEFAULT_PORT = 8787;
const APP_DISPLAY_NAME = "oclaw";
const APP_ROOT = path.resolve(__dirname, "..", "..");
const APP_ICON_PATH = path.join(APP_ROOT, "src", "admin", "static", "oliver.svg");
const DATA_ROOT = path.join(app.getPath("userData"), "runtime-data");
const LOG_ROOT = path.join(app.getPath("userData"), "logs");
const BACKEND_LOG_FILE = path.join(LOG_ROOT, "backend.log");
const STARTUP_TIMEOUT_MS = 30000;
const POLL_INTERVAL_MS = 600;

let mainWindow = null;
let backendProc = null;
let channelProc = null;
let runtimeState = null;
let backendStopping = false;
let channelStopping = false;
let backendCrashDialogOpen = false;
let quitAfterCleanup = false;
let channelStartWarningShown = false;

// Improve first-paint reliability on Windows: avoid renderer backgrounding/timer throttling
// that can delay UI updates until the first user interaction (e.g. click/focus).
try {
  app.commandLine.appendSwitch("disable-renderer-backgrounding");
  app.commandLine.appendSwitch("disable-background-timer-throttling");
} catch (_) {}

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function nowIso() {
  return new Date().toISOString();
}

function logDesktop(msg) {
  try {
    ensureDir(LOG_ROOT);
    fs.appendFileSync(path.join(LOG_ROOT, "desktop.log"), `[${nowIso()}] ${String(msg || "")}\n`, "utf8");
  } catch (_) {}
}

function resolvePythonBin() {
  const fromEnv = String(process.env.PYTHON_EXECUTABLE || "").trim();
  if (fromEnv) return fromEnv;
  const venvPy =
    process.platform === "win32"
      ? path.join(APP_ROOT, "oclaw", ".venv", "Scripts", "python.exe")
      : path.join(APP_ROOT, "oclaw", ".venv", "bin", "python");
  try {
    if (fs.existsSync(venvPy)) return venvPy;
  } catch (_) {}
  if (process.platform === "win32") return "python";
  return "python3";
}

function buildPythonEnv(extra = {}) {
  return {
    ...process.env,
    PYTHONPATH: APP_ROOT,
    PYTHONUTF8: "1",
    ...extra,
  };
}

function checkPythonAvailable(pythonBin) {
  return new Promise((resolve) => {
    const probe = spawn(pythonBin, ["--version"], {
      cwd: APP_ROOT,
      windowsHide: true,
      stdio: "ignore",
    });
    probe.once("error", () => resolve(false));
    probe.once("close", (code) => resolve(code === 0));
  });
}

function pickPort(preferredPort) {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on("error", reject);
    server.listen(preferredPort, DEFAULT_HOST, () => {
      const addr = server.address();
      const chosenPort = typeof addr === "object" && addr ? addr.port : preferredPort;
      server.close(() => resolve(chosenPort));
    });
  });
}

function waitForBackend(url, deadlineAtMs) {
  return new Promise((resolve, reject) => {
    const attempt = () => {
      const req = http.get(url, (res) => {
        res.resume();
        if (res.statusCode && res.statusCode < 500) {
          resolve();
          return;
        }
        if (Date.now() >= deadlineAtMs) {
          reject(new Error(`backend not ready: HTTP ${res.statusCode || "unknown"}`));
          return;
        }
        setTimeout(attempt, POLL_INTERVAL_MS);
      });
      req.on("error", () => {
        if (Date.now() >= deadlineAtMs) {
          reject(new Error("backend did not become reachable in time"));
          return;
        }
        setTimeout(attempt, POLL_INTERVAL_MS);
      });
      req.setTimeout(2500, () => {
        req.destroy(new Error("backend readiness probe timeout"));
      });
    };
    attempt();
  });
}

function loadingHtml(text) {
  const safe = String(text || "").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>${APP_DISPLAY_NAME}</title>
    <style>
      html, body { height: 100%; margin: 0; background: #0d0d0d; color: #e6e6e6; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; }
      .wrap { height: 100%; display: flex; align-items: center; justify-content: center; }
      .card { width: min(720px, 92vw); padding: 22px 22px 18px; border: 1px solid rgba(255,255,255,.08); border-radius: 14px; background: rgba(255,255,255,.03); }
      .title { font-size: 16px; font-weight: 700; margin-bottom: 10px; }
      .muted { opacity: .78; line-height: 1.5; white-space: pre-wrap; }
      .spinner { width: 18px; height: 18px; border: 2px solid rgba(255,255,255,.18); border-top-color: rgba(255,255,255,.72); border-radius: 999px; animation: spin 1s linear infinite; display: inline-block; vertical-align: -3px; margin-right: 8px; }
      @keyframes spin { to { transform: rotate(360deg); } }
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="card">
        <div class="title"><span class="spinner"></span>${APP_DISPLAY_NAME}</div>
        <div class="muted">${safe}</div>
      </div>
    </div>
  </body>
</html>`;
}

async function startBackendProcess() {
  if (backendProc) return runtimeState;
  backendStopping = false;
  ensureDir(DATA_ROOT);
  ensureDir(LOG_ROOT);

  const preferredPortRaw = Number.parseInt(String(process.env.AIA_DESKTOP_BACKEND_PORT || ""), 10);
  const preferredPort = Number.isFinite(preferredPortRaw) ? preferredPortRaw : DEFAULT_PORT;
  const port = await pickPort(preferredPort);
  const host = DEFAULT_HOST;
  const baseUrl = `http://${host}:${port}`;

  const logStream = fs.createWriteStream(BACKEND_LOG_FILE, { flags: "a" });
  const pythonBin = resolvePythonBin();
  const pythonOk = await checkPythonAvailable(pythonBin);
  if (!pythonOk) {
    logStream.end();
    throw new Error(
      `Python not found: ${pythonBin}. 请先安装 Python 3.10+，或设置环境变量 PYTHON_EXECUTABLE 指向可用解释器。`
    );
  }
  const env = buildPythonEnv({
    AIA_ASSISTANT_GATEWAY_HOST: host,
    AIA_ASSISTANT_GATEWAY_PORT: String(port),
    AIA_DATA_DIR: DATA_ROOT,
    AIA_DESKTOP_MODE: "1",
  });

  const args = ["-m", "oclaw.runtime.operations", "gateway", "start", "--host", host, "--port", String(port)];
  backendProc = spawn(pythonBin, args, {
    cwd: APP_ROOT,
    env,
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
  });
  runtimeState = { host, port, baseUrl, pythonBin };

  backendProc.stdout.on("data", (chunk) => {
    logStream.write(chunk);
  });
  backendProc.stderr.on("data", (chunk) => {
    logStream.write(chunk);
  });
  backendProc.on("close", async (code, signal) => {
    const msg = `[backend-exit] code=${code} signal=${signal || "none"}\n`;
    logStream.write(msg);
    logStream.end();
    const crashed = !backendStopping;
    backendProc = null;
    if (crashed) {
      await showBackendCrashedDialog(code, signal);
    }
  });

  const deadlineAtMs = Date.now() + STARTUP_TIMEOUT_MS;
  await waitForBackend(`${baseUrl}/health`, deadlineAtMs);
  return runtimeState;
}

function waitForProcessHealthy(proc, deadlineAtMs) {
  return new Promise((resolve, reject) => {
    const check = () => {
      if (!proc) {
        resolve(false);
        return;
      }
      if (proc.exitCode !== null) {
        resolve(false);
        return;
      }
      if (Date.now() >= deadlineAtMs) {
        resolve(true);
        return;
      }
      setTimeout(check, 250);
    };
    check();
  });
}

function runPythonInline(pythonBin, code, extraEnv = {}) {
  return new Promise((resolve) => {
    const proc = spawn(pythonBin, ["-c", code], {
      cwd: APP_ROOT,
      env: buildPythonEnv(extraEnv),
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
    });
    let out = "";
    let err = "";
    proc.stdout.on("data", (c) => {
      out += String(c || "");
    });
    proc.stderr.on("data", (c) => {
      err += String(c || "");
    });
    proc.once("error", (e) => {
      resolve({ ok: false, code: -1, out, err: `${err}\n${String(e && e.message ? e.message : e)}` });
    });
    proc.once("close", (code0) => {
      resolve({ ok: code0 === 0, code: Number(code0 ?? -1), out, err });
    });
  });
}

async function startChannelProcess() {
  if (channelProc) return true;
  ensureDir(LOG_ROOT);
  if (!runtimeState || !runtimeState.host || !runtimeState.port) {
    throw new Error("runtime_state_missing");
  }
  const channelLogFile = path.join(LOG_ROOT, "channel-wecom.log");
  const logStream = fs.createWriteStream(channelLogFile, { flags: "a" });
  const pythonBin = resolvePythonBin();
  // Kill stale/orphan WeCom workers first to avoid single-instance lock conflicts.
  try {
    const cleanupRes = await runPythonInline(
      pythonBin,
      "from oclaw.runtime.operations.runtime import cleanup_orphan_service_processes; k=cleanup_orphan_service_processes('channel:wecom'); print('killed=' + ','.join(str(x) for x in k))",
      { AIA_DATA_DIR: DATA_ROOT },
    );
    if (!cleanupRes.ok) {
      logStream.write(`[channel-cleanup-warn] code=${cleanupRes.code} err=${String(cleanupRes.err || "").trim()}\n`);
    } else {
      const line = String(cleanupRes.out || "").trim();
      if (line) logStream.write(`[channel-cleanup] ${line}\n`);
    }
  } catch (_) {}
  const env = buildPythonEnv({
    AIA_ASSISTANT_GATEWAY_HOST: String(runtimeState.host),
    AIA_ASSISTANT_GATEWAY_PORT: String(runtimeState.port),
    AIA_DATA_DIR: DATA_ROOT,
    AIA_DESKTOP_MODE: "1",
  });
  const args = ["-m", "oclaw.runtime.operations", "channel", "wecom", "start", "--mode", "ws", "--interval", "3.0", "--deliver-outbound"];
  channelStopping = false;
  channelProc = spawn(pythonBin, args, {
    cwd: APP_ROOT,
    env,
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
  });
  channelProc.stdout.on("data", (chunk) => {
    logStream.write(chunk);
  });
  channelProc.stderr.on("data", (chunk) => {
    logStream.write(chunk);
  });
  channelProc.on("close", (code, signal) => {
    logStream.write(`[channel-exit] code=${code} signal=${signal || "none"}\n`);
    logStream.end();
    const crashed = !channelStopping;
    channelProc = null;
    if (crashed) {
      setTimeout(() => {
        if (!quitAfterCleanup) {
          startChannelProcess().catch(() => {});
        }
      }, 1200);
    }
  });
  const healthy = await waitForProcessHealthy(channelProc, Date.now() + 2000);
  if (!healthy) {
    const msg = `[channel-start-warn] process_exit_${channelProc && channelProc.exitCode !== null ? channelProc.exitCode : "unknown"}\n`;
    try {
      fs.appendFileSync(BACKEND_LOG_FILE, msg, { encoding: "utf-8" });
    } catch (_) {}
    return false;
  }
  return true;
}

function waitProcessClose(proc, timeoutMs) {
  return new Promise((resolve) => {
    if (!proc || proc.exitCode !== null || proc.killed) {
      resolve();
      return;
    }
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      resolve();
    };
    const timer = setTimeout(finish, Math.max(200, Number(timeoutMs) || 6000));
    proc.once("close", () => {
      clearTimeout(timer);
      finish();
    });
    proc.once("exit", () => {
      clearTimeout(timer);
      finish();
    });
  });
}

function taskkillTree(pid) {
  return new Promise((resolve) => {
    const killer = spawn("taskkill", ["/PID", String(pid), "/T", "/F"], {
      windowsHide: true,
      stdio: "ignore",
    });
    killer.once("error", () => resolve(false));
    killer.once("close", (code) => resolve(code === 0));
  });
}

async function stopBackendProcess() {
  if (!backendProc) return;
  const proc = backendProc;
  backendStopping = true;
  if (process.platform === "win32") {
    const ok = await taskkillTree(proc.pid);
    if (!ok) {
      try {
        proc.kill("SIGTERM");
      } catch (_) {}
    }
    await waitProcessClose(proc, 8000);
    return;
  }
  try {
    proc.kill("SIGTERM");
  } catch (_) {}
  await waitProcessClose(proc, 5000);
  if (proc.exitCode === null && !proc.killed) {
    try {
      proc.kill("SIGKILL");
    } catch (_) {}
    await waitProcessClose(proc, 3000);
  }
}

async function stopChannelProcess() {
  if (!channelProc) return;
  const proc = channelProc;
  channelStopping = true;
  if (process.platform === "win32") {
    const ok = await taskkillTree(proc.pid);
    if (!ok) {
      try {
        proc.kill("SIGTERM");
      } catch (_) {}
    }
    await waitProcessClose(proc, 6000);
    return;
  }
  try {
    proc.kill("SIGTERM");
  } catch (_) {}
  await waitProcessClose(proc, 4000);
}

async function showBackendCrashedDialog(code, signal) {
  if (backendCrashDialogOpen) return;
  backendCrashDialogOpen = true;
  try {
    const result = await dialog.showMessageBox({
      type: "error",
      title: "Backend stopped unexpectedly",
      message: "本地后端进程已退出",
      detail: `exit_code=${code ?? "unknown"}, signal=${signal || "none"}\n\n日志文件：${BACKEND_LOG_FILE}`,
      buttons: ["重启后端", "打开日志目录", "退出应用"],
      defaultId: 0,
      cancelId: 2,
    });
    if (result.response === 0) {
      await startBackendProcess();
      if (mainWindow && !mainWindow.isDestroyed()) {
        await mainWindow.loadURL(`${runtimeState.baseUrl}/chat`);
      }
      return;
    }
    if (result.response === 1) {
      shell.showItemInFolder(BACKEND_LOG_FILE);
      await showBackendCrashedDialog(code, signal);
      return;
    }
    app.quit();
  } finally {
    backendCrashDialogOpen = false;
  }
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    title: APP_DISPLAY_NAME,
    width: 1400,
    height: 900,
    minWidth: 1100,
    minHeight: 700,
    icon: APP_ICON_PATH,
    show: false,
    backgroundColor: "#0d0d0d",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      devTools: true,
      backgroundThrottling: false,
    },
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (String(url || "").startsWith(runtimeState?.baseUrl || "")) {
      return { action: "allow" };
    }
    shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.webContents.on("will-navigate", (event, url) => {
    const base = runtimeState?.baseUrl || "";
    if (!base || !String(url).startsWith(base)) {
      event.preventDefault();
    }
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  mainWindow.webContents.on("did-fail-load", (event, code, desc, url, isMainFrame) => {
    if (!isMainFrame) return;
    logDesktop(`did-fail-load: code=${code} url=${url} desc=${desc}`);
  });
  mainWindow.webContents.on("did-start-navigation", (event, url, isInPlace, isMainFrame) => {
    if (!isMainFrame) return;
    logDesktop(`did-start-navigation: url=${url} inPlace=${Boolean(isInPlace)}`);
  });
  mainWindow.webContents.on("dom-ready", () => {
    logDesktop("dom-ready");
  });
  mainWindow.webContents.on("did-finish-load", () => {
    logDesktop("did-finish-load");
  });
  mainWindow.webContents.on("did-stop-loading", () => {
    logDesktop("did-stop-loading");
  });
}

async function showStartupError(error) {
  const message = String(error && error.message ? error.message : error || "unknown startup failure");
  await dialog.showMessageBox({
    type: "error",
    title: "Desktop startup failed",
    message: "无法启动本地后端服务",
    detail: `${message}\n\n日志文件：${BACKEND_LOG_FILE}`,
  });
}

async function boot() {
  try {
    app.setName(APP_DISPLAY_NAME);
    createMainWindow();
    // Show window immediately to avoid "black screen" during backend startup.
    try {
      await mainWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(loadingHtml("Starting local gateway…"))}`);
    } catch (_) {}
    mainWindow.show();
    try {
      mainWindow.focus();
    } catch (_) {}

    const t0 = Date.now();
    logDesktop("boot:start");

    // Desktop policy: every restart requires explicit login.
    // Clear persisted web storage before first page load. Do not block window display.
    const clearStoragePromise = (async () => {
      try {
        await mainWindow.webContents.session.clearStorageData();
        logDesktop(`boot:clearStorage:ok:${Date.now() - t0}ms`);
      } catch (e) {
        logDesktop(`boot:clearStorage:err:${Date.now() - t0}ms:${String(e && e.message ? e.message : e)}`);
      }
    })();
    const clearCachePromise = (async () => {
      try {
        await mainWindow.webContents.session.clearCache();
        if (typeof mainWindow.webContents.session.clearHostResolverCache === "function") {
          mainWindow.webContents.session.clearHostResolverCache();
        }
        logDesktop(`boot:clearCache:ok:${Date.now() - t0}ms`);
      } catch (e) {
        logDesktop(`boot:clearCache:err:${Date.now() - t0}ms:${String(e && e.message ? e.message : e)}`);
      }
    })();

    await startBackendProcess();
    logDesktop(`boot:backendReady:${Date.now() - t0}ms`);

    try {
      await mainWindow.loadURL(
        `data:text/html;charset=utf-8,${encodeURIComponent(loadingHtml(`Backend ready at ${runtimeState.baseUrl}\nStarting channel…`))}`,
      );
    } catch (_) {}

    const channelOk = await startChannelProcess();
    logDesktop(`boot:channel:${channelOk ? "ok" : "fail"}:${Date.now() - t0}ms`);
    if (!channelOk && !channelStartWarningShown) {
      channelStartWarningShown = true;
      await dialog.showMessageBox({
        type: "warning",
        title: "Channel startup warning",
        message: "企微通道启动失败（不影响桌面端启动）",
        detail: "你可以在 Admin -> 运行时中查看并重试服务。",
      });
    }
    await clearStoragePromise;
    await clearCachePromise;
    // Desktop policy: always require fresh login on every app restart.
    logDesktop(`boot:loadChat:start:${Date.now() - t0}ms`);
    await mainWindow.loadURL(`${runtimeState.baseUrl}/chat?v=${Date.now()}`);
    logDesktop(`boot:loadChat:done:${Date.now() - t0}ms`);
    try {
      mainWindow.show();
      mainWindow.focus();
    } catch (_) {}
  } catch (error) {
    await showStartupError(error);
    app.quit();
  }
}

ipcMain.handle("desktop:getRuntimeInfo", async () => {
  const state = runtimeState || {};
  return {
    host: state.host || DEFAULT_HOST,
    port: state.port || DEFAULT_PORT,
    baseUrl: state.baseUrl || "",
    logFile: BACKEND_LOG_FILE,
  };
});

ipcMain.handle("desktop:restartBackend", async () => {
  if (mainWindow && !mainWindow.isDestroyed()) {
    try {
      await mainWindow.loadURL(
        `data:text/html;charset=utf-8,${encodeURIComponent(loadingHtml("Restarting local gateway…"))}`,
      );
      mainWindow.show();
      try {
        mainWindow.focus();
      } catch (_) {}
    } catch (_) {}
  }
  await stopChannelProcess();
  await stopBackendProcess();
  await startBackendProcess();
  await startChannelProcess();
  if (mainWindow && !mainWindow.isDestroyed()) {
    try {
      await mainWindow.webContents.session.clearCache();
    } catch (_) {}
    await mainWindow.loadURL(`${runtimeState.baseUrl}/chat?v=${Date.now()}`);
    try {
      mainWindow.show();
      mainWindow.focus();
    } catch (_) {}
  }
  return true;
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", (event) => {
  if (quitAfterCleanup) return;
  event.preventDefault();
  quitAfterCleanup = true;
  // Turn quit into graceful async shutdown so backend child tree is fully reaped.
  (async () => {
    await stopChannelProcess();
    await stopBackendProcess();
    app.quit();
  })().catch(() => {
    app.quit();
  });
});

app.whenReady().then(boot);
