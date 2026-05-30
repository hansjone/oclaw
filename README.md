# Oclaw Architecture Root

This repository is fully consolidated under `oclaw/`.

## 开箱即用（从零跑起来）

面向第一次在本机跑通 **网关 + Admin + Chat** 的最短路径（Windows）。不需要微信/WhatsApp 也能先调试界面与模型。

### 前置条件

- **系统**：Windows 10/11，PowerShell
- **Python**：3.11+（脚本会在仓库根创建 `.venv`，后续命令始终用该环境）
- **Node.js**：22+（官方微信插件 / 部分 sidecar 需要；若暂时只用浏览器访问 Admin/Chat，可先只准备 Python，按需再装 Node）
- **npm**：随 Node 安装（同上，按需）

### 环境与密钥（推荐先做）

1. **进程环境文件**：从模板复制一份，按需填写端口、密钥等（勿提交真实密钥文件）。

   ```powershell
   copy _local\system.env.example _local\system.env
   ```

   网关入口会加载 `_local/system.env`；已在系统或启动脚本里 export 的变量优先级更高。

2. **LLM**：可在 **Admin** 后台配置 Provider / 模型与密钥；也可在 `_local/system.env` 里设置 `OPENAI_API_KEY`、`OPENAI_BASE_URL` 等兜底。完整清单见 `docs/ENVIRONMENT_VARIABLES.md`。

3. **助手主库（PostgreSQL，可选）**：默认使用本地 SQLite；若要将助手持久化迁到 PostgreSQL 或从零搭 PG，步骤与脚本说明见 `docs/ASSISTANT_PG_MIGRATION.md`（环境变量仍以 `docs/ENVIRONMENT_VARIABLES.md` 为准）。

4. **日志**：运行与轮转日志目录、排障时查看哪些文件，见 `docs/LOGGING.md`。

### 命令（仓库根目录执行）

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_venv.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start_gateway.ps1 -SkipInstall -Background
```

或使用 **一键后台启动全栈**（未安装的微信/WhatsApp sidecar 会告警并跳过，不阻塞 Admin/Chat）：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_all.ps1 -Background
```

### 打开页面

- Admin：`http://127.0.0.1:8787/admin`
- Chat：`http://127.0.0.1:8787/chat`

### 常见问题

- **8787 端口占用 / 重启不生效**：`powershell -ExecutionPolicy Bypass -File .\scripts\stop_gateway.ps1 -Force` 后再启动。
- **更细的从零教程**：`docs/RUNBOOK.md` →「开源快速安装（从零到跑起来）」。
- **WhatsApp 安装与启停**：见 `docs/RUNBOOK.md` →「4.2 WhatsApp（实验接入）」。
- **更换品牌 Logo（外部优先）**：见 `docs/BRANDING.md`（将资源放到 `_local/branding/`）。

### 可选：运维专家（network_ops）与 netx

若要在 ops 专家模式下调 **netx** 告警库，需单独启动 netx 服务，并在 Admin 安装 **netx MCP**（`server_id=netx`，env `NETX_API_URL`）。说明见 `docs/NETX_MCP_INTEGRATION.md`。迁移期可选 `OCLAW_NETX_BUILTIN_TOOLS=1` 启用旧 inline 工具。

### 可选：股票分析专家（A股/港股，信号建议）

已新增 `stock` 专家工作区（只做分析，不下单）。建议配合 Tushare MCP 使用：

1. 在 Tushare 平台获取 MCP 配置（见官方文档：[Tushare MCP 配置与使用](https://tushare.pro/document/1?doc_id=463)）。
2. 在 oclaw 管理台导入 MCP JSON（支持 `mcpServers` 结构），启用后执行 Health / Sync Tools。
3. 在聊天里路由到 `stock` 专家，按信号模板输出“买入/卖出/观望”建议。

说明：
- 当前方案不接券商账户、不执行下单。
- 输出包含数据来源与时间戳，并附“非投资建议”声明。

### 外部贡献

若仓库对外开源并接受 Pull Request，协作方式与合并前自检见根目录 `CONTRIBUTING.md`。

---

## Quickstart (Open Source)

### Prerequisites
- Python 3.11+
- Node.js 22+ (required by the official Weixin plugin)

### Recommended first run (env file)

```powershell
copy _local\system.env.example _local\system.env
```

Edit `_local/system.env` as needed. Gateway loads this file at startup.

### 1) Bootstrap venv (Windows)

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_venv.ps1
```

### 2) Start gateway (background)

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_gateway.ps1 -SkipInstall -Background
```

Open:
- Admin: `http://127.0.0.1:8787/admin`
- Chat:  `http://127.0.0.1:8787/chat`

If port 8787 is stuck/occupied, force-stop:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop_gateway.ps1 -Force
```

### 3) Weixin (Personal WeChat): install → login → start

```powershell
powershell -ExecutionPolicy Bypass -File .\runtime\operations\scripts\weixin_install.ps1
powershell -ExecutionPolicy Bypass -File .\runtime\operations\scripts\weixin_login.ps1
powershell -ExecutionPolicy Bypass -File .\runtime\operations\scripts\weixin_start.ps1
```

Notes:
- `weixin_install.ps1` does **not** require global `openclaw` CLI installation; runtime deps are installed locally in sidecar workspace.
- `.\scripts\start_all.ps1 -Background` now skips missing Weixin/WhatsApp sidecars gracefully (warn + continue), so Admin/Chat can still boot on fresh installs.
- Admin supports channel dispatch controls for Weixin/WhatsApp (bind specialist / comprehensive), with default `generalist`.

Full runbook (recommended): see `docs/RUNBOOK.md` → “开源快速安装（从零到跑起来）”.
WhatsApp install/start guide: see `docs/RUNBOOK.md` → “4.2 WhatsApp（实验接入）”.

Minimal onboarding guide: `docs/OPEN_SOURCE_QUICKSTART.md`.
Branding guide (external-first assets under `_local/branding`): `docs/BRANDING.md`.
Assistant main store: SQLite by default; optional PostgreSQL setup and SQLite→PG cutover: `docs/ASSISTANT_PG_MIGRATION.md`.
Runtime logging layout and troubleshooting: `docs/LOGGING.md`.

Chinese zero-to-running checklist: see **开箱即用（从零跑起来）** at the top of this README.

## Layers
- `runtime/`: core execution loop, routing, skill runtime, hook runtime
- `interfaces/`: transport adapters (HTTP/WS)
- `gateway/`: method handlers and protocol bridging
- `application/`: use-cases and orchestration services
- `infrastructure/`: runtime-facing integrations/adapters
- `svc/`: shared platform capabilities (llm, persistence, config, files)
- `tools/`: tool registry, MCP adapters, public/system tools
- `skills/`: installable skills and runtime manifests

## Naming Rule
- Use `oclaw` consistently in paths, symbols, and docs.
- Avoid introducing legacy aliases or old naming variants.

## Attachment Replay Config
- Attachment-related limits are configured in `oclaw.json` under:
  - `plugins.entries.memory-wiki.auto.attachments.tabular`
- Replay limits:
  - `image_result_replay_cap_chars` (default `4000`, range `600..30000`)
  - `video_result_replay_cap_chars` (default `4000`, range `600..30000`)
  - Used to cap historical `query_image_attachment` / `query_video_attachment(task=transcript)` text replay in model context.
- Video transcript chunk defaults:
  - `video_transcript_chunk_size` (default `1600`)
  - `video_transcript_chunk_overlap` (default `200`)
- Unified archive budget defaults (zip/tar/tgz/gz):
  - `archive_max_depth` (default `2`)
  - `archive_max_file_count` (default `200`)
  - `archive_max_entry_bytes` (default `10485760`)
  - `archive_max_total_uncompressed_bytes` (default `52428800`)
  - Archive parse errors now expose stable `error_code` values (for UI mapping and retries).
- Effective priority for replay-cap values:
  - DB setting `AIA_IMAGE_TOOL_RESULT_REPLAY_CAP_CHARS`
  - DB setting `AIA_VIDEO_TOOL_RESULT_REPLAY_CAP_CHARS`
  - Environment variable `AIA_IMAGE_TOOL_RESULT_REPLAY_CAP_CHARS`
  - Environment variable `AIA_VIDEO_TOOL_RESULT_REPLAY_CAP_CHARS`
  - `oclaw.json` value
  - Built-in default

See `docs/ENVIRONMENT_VARIABLES.md` for full runtime variable reference.
PostgreSQL assistant-store migration (schema, data import, cutover): `docs/ASSISTANT_PG_MIGRATION.md`.
Logging directories and rotating files: `docs/LOGGING.md`.

## License and security

- License: [MIT](LICENSE). Third-party subtrees may carry their own license files; those terms apply to the respective files only.
- Vulnerability reporting: [SECURITY.md](SECURITY.md).

