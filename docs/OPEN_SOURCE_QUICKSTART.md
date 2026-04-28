# Open Source Quickstart (Windows)

This guide is the shortest path for first-time users.

## Prerequisites

- Python 3.11+
- Node.js 22+
- PowerShell (Windows 10/11)

## Path A: Web/Admin only (no Weixin/WhatsApp required)

1) Bootstrap Python venv:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_venv.ps1
```

2) Start full stack in background:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_all.ps1 -Background
```

3) Open:

- Admin: `http://127.0.0.1:8787/admin`
- Chat: `http://127.0.0.1:8787/chat`

Notes:

- If Weixin/WhatsApp sidecars are not installed, `start_all.ps1` will skip them with a warning and continue.
- This does not block Admin/Chat.

## Path B: Enable Weixin (Personal WeChat)

```powershell
powershell -ExecutionPolicy Bypass -File .\runtime\operations\scripts\weixin_install.ps1
powershell -ExecutionPolicy Bypass -File .\runtime\operations\scripts\weixin_login.ps1
powershell -ExecutionPolicy Bypass -File .\runtime\operations\scripts\weixin_start.ps1
```

Notes:

- No global `openclaw` CLI installation is required.
- Runtime dependencies are installed locally in sidecar workspace.

## Path C: Enable WhatsApp (experimental)

```powershell
powershell -ExecutionPolicy Bypass -File .\runtime\operations\scripts\whatsapp_install.ps1
powershell -ExecutionPolicy Bypass -File .\runtime\operations\scripts\whatsapp_login.ps1
powershell -ExecutionPolicy Bypass -File .\runtime\operations\scripts\whatsapp_start.ps1
```

## Admin dispatch controls (Weixin/WhatsApp)

In Admin:

- `Stack` page: channel-level controls (`Bind specialist` / `Comprehensive`)
- `User/Channel binding` page: account-level controls per channel/account

Priority:

1. Account-level dispatch config
2. Channel-level dispatch config
3. Default (`expert + generalist`)

## Common commands

Start:

```powershell
.\scripts\start_all.ps1 -Background
```

Status:

```powershell
.\scripts\status_all.ps1
```

Stop:

```powershell
.\scripts\stop_all.ps1
```

Force stop:

```powershell
.\scripts\stop_all.ps1 -Force
```

