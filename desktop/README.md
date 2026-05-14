# Desktop Shell

Electron wrapper for existing `admin/chat` frontend with an embedded local backend process.

## Prerequisites

- Node.js 20+
- Python 3.10+ (available in `PATH` as `python`)
- Python deps installed in repo root:

```powershell
python -m pip install -r requirements.txt
```

## Development

From this `oclaw/desktop` directory:

```powershell
npm install
npm run dev
```

The app will:

1. Pick an available local port (default prefers `8787`).
2. Start backend using `python -m runtime.operations gateway start --host 127.0.0.1 --port <port>`.
3. Open `http://127.0.0.1:<port>/chat` in the desktop window.

Logs (embedded backend, desktop shell, optional WeCom channel child) are written under the **runtime log root** (same as `AIA_RUNTIME_LOG_DIR` / `data/logs/` — see repo root [`docs/LOGGING.md`](../docs/LOGGING.md)). When launched via `runtime/operations/scripts/start_desktop.ps1`, `OCLAW_DESKTOP_LOG_ROOT` is set for you.

Typical files:

- `desktop.log`
- `backend.log`

## Environment knobs

- `PYTHON_EXECUTABLE`: absolute path to python executable.
- `AIA_DESKTOP_BACKEND_PORT`: preferred backend port.

## Packaging (Windows)

```powershell
npm run pack:win
```

Output goes to `oclaw/desktop/dist/`, e.g.:

- `oclaw-setup-<version>.exe`
- `oclaw-setup-<version>.exe.blockmap`
- `win-unpacked/oclaw.exe`
