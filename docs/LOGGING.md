# 日志与排障

本文说明 Oclaw **日志根目录**、进程级日志与 **Python 轮转日志** 的落点，便于线上/本机排障。环境变量完整列表仍以 [`ENVIRONMENT_VARIABLES.md`](./ENVIRONMENT_VARIABLES.md) 为准。

## 日志根目录

由 **`AIA_RUNTIME_LOG_DIR`** 指定；未设置时与 `runtime.operations.runtime.assistant_runtime_log_dir()` 一致：**助手库文件（`db_path()`）所在目录下的 `logs/`**（常见为仓库下 `data/logs/`）。

网关、`stack up` 启用的渠道进程、**轮转应用日志**、**内置 Hook 文件日志**（`hooks/`）、**微信/WhatsApp sidecar 的 stdout/stderr**（`weixin_sidecar.*` / `whatsapp_sidecar.*`），以及 **Desktop（Electron）** 写入的 `desktop.log` / `backend.log` / `channel-wecom.log`，均默认使用该根目录（Desktop 由 `start_desktop.ps1` 设置 `AIA_RUNTIME_LOG_DIR` / `OCLAW_DESKTOP_LOG_ROOT`，或直接运行 Electron 时回落到 **`<仓库根>/data/logs/`**）。Wiki worker 若用 `start_wiki_worker.ps1` 后台启动，其 stdout/stderr 为 `wiki_worker.out.log` / `wiki_worker.err.log`。

## 目录布局（根目录下）

| 路径 | 说明 |
|------|------|
| `gateway.out.log` / `gateway.err.log` | `start_service` 重定向子进程的 stdout/stderr；裸 `print`、未走 `logging` 的输出等。**追加写，无应用内轮转**；生产可配合系统 logrotate。 |
| `channel_*.out.log` / `.err.log` | 同上，渠道名中的 `:` 会替换为 `_`。 |
| `app/oclaw.log` | **轮转**：应用与 uvicorn 主日志（`RotatingFileHandler`）。 |
| `app/uvicorn-access.log` | **轮转**：HTTP access（仅网关 uvicorn 模式）。 |
| `weixin_sidecar.log` / `weixin_sidecar.err.log` | `weixin_start.ps1` 重定向 sidecar 进程输出（原在 `data/channel_sidecar/.../logs`，已统一到运行日志根）。 |
| `whatsapp_sidecar.log` / `whatsapp_sidecar.err.log` | `whatsapp_start.ps1` 同上。 |
| `desktop.log` / `backend.log` / `channel-wecom.log` | Desktop Electron 内嵌网关与渠道子进程日志（`desktop/main.js`）。 |
| `wiki_worker.out.log` / `wiki_worker.err.log` | `start_wiki_worker.ps1` 后台模式重定向的 stdout/stderr（与运行日志根一致）。 |
| `hooks/commands.log`、`boot-md.log` | 默认在 **`{运行日志根}/hooks/`**（与网关同根）。若需恢复旧行为（`OCLAW_STATE_DIR` 或 `~/.oclaw/logs`），设置 **`OCLAW_HOOK_LOG_USE_STATE_DIR=1`**。 |

## 环境变量（摘要）

| 变量 | 作用 |
|------|------|
| `AIA_RUNTIME_LOG_DIR` | 上述根目录。 |
| `OCLAW_LOG_LEVEL` / `AIA_LOG_LEVEL` | 文件日志级别，默认 `INFO`（支持 `DEBUG`、`WARNING`、`ERROR`、`CRITICAL` 等）。 |
| `OCLAW_LOG_MAX_BYTES` | 单文件最大字节，默认 `20971520`（20 MiB）。 |
| `OCLAW_LOG_BACKUP_COUNT` | 轮转保留份数，默认 `5`。 |
| `AIA_LOG_TO_FILE` | 设为 `0` / `false` / `off` 等时**不写**轮转文件（pytest 也会自动跳过文件 handler）。 |
| `OCLAW_DESKTOP_LOG_ROOT` | 可选；Desktop 写入 `desktop.log` / `backend.log` 等的目录。未设置时读 `AIA_RUNTIME_LOG_DIR`；再未设置则用 **`<仓库根>/data/logs/`**（与 `desktop/main.js` 一致）。`start_desktop.ps1` 会将其设为与 `AIA_RUNTIME_LOG_DIR` 相同。 |
| `OCLAW_HOOK_LOG_USE_STATE_DIR` | 设为 `1` / `true` 时，内置钩子日志改写到 **`OCLAW_STATE_DIR`（或 `~/.oclaw`）下的 `logs/`**；未设置时默认 **`{运行日志根}/hooks/`**。 |

## 实现位置

- 根路径：[`svc/config/log_paths.py`](../svc/config/log_paths.py)（`oclaw_log_root`、`oclaw_hooks_log_dir`）
- 配置：[`svc/observability/logging_setup.py`](../svc/observability/logging_setup.py)
- 网关：[`interfaces/http/fastapi_app.py`](../interfaces/http/fastapi_app.py) 的 `main()` 在 `uvicorn.run(..., log_config=...)`
- PowerShell 解析与网关相同的根目录：[`runtime/operations/scripts/lib/ResolveRuntimeLogDir.ps1`](../runtime/operations/scripts/lib/ResolveRuntimeLogDir.ps1)（`Get-OclawRuntimeLogDir`）
- 企微 longconn / wiki worker：进程入口 `configure_oclaw_logging(...)`
