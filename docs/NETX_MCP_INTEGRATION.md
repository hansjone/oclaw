# netx MCP Integration

Wire **oclaw** (or any MCP host) to the standard **netx HTTP MCP** in `D:/project/chatgpt/netx`.

netx 侧通用安装/更新说明：`D:/project/chatgpt/netx/docs/MCP.md`。

Default path: **stdio MCP → netx REST API** (`NETX_API_URL`). Legacy inline HTTP tools in oclaw are opt-in via `OCLAW_NETX_BUILTIN_TOOLS=1`.

## 1) Start netx API

In `D:/project/chatgpt/netx`:

```powershell
python -m pip install -r requirements.txt
$env:NETX_DATABASE_URL = "postgresql+psycopg://netx:netx@127.0.0.1:5432/netx"
$env:NETX_HOST = "127.0.0.1"
$env:NETX_PORT = "8890"
python -m netx_api.main
```

Health check:

```powershell
curl http://127.0.0.1:8890/health
```

## 2) Install netx MCP in oclaw Admin

**推荐：直接粘贴与 Cursor 相同的 `mcpServers` JSON**（与 `netx/mcp.json` 一致），在 Admin → MCP → 安装 JSON 粘贴后安装，无需再手写 `entry_command` / `entry_args`：

```json
{
  "mcpServers": {
    "netx": {
      "command": "python",
      "args": ["-m", "netx_mcp"],
      "env": {
        "NETX_API_URL": "http://127.0.0.1:8890",
        "NETX_API_TOKEN": "",
        "NETX_LANG": "zh"
      }
    }
  }
}
```

oclaw 会把 `command` → `entry_command`、`args` → `entry_args`，`env` → 注册表 `env_schema`（含 default，运行时传给 MCP 子进程）；stdio 条目默认 `source_type=local`。与下文「install payload」等价。

本机默认 `http://127.0.0.1:8890` 时，`env` 可省略（`netx_mcp` 代码内也有相同默认）；远端 API 或 Token 时在 JSON 的 `env` 里写即可，不必再单独维护 `mcp_install_payload.json`。

也可用 oclaw 专用 install payload（字段展开版，便于脚本/文档引用）：

- `D:/project/chatgpt/netx/mcp_install_payload.json`

Equivalent manual values（与上面 `mcpServers` 同义）：

| Field | Value |
|-------|-------|
| `source_type` | `local` |
| `source_ref` | `netx-mcp-http` |
| `server_id` | **`netx`** |
| `entry_command` | `python` |
| `entry_args` | `["-m", "netx_mcp"]` |
| `timeout_s` | `120` |
| MCP env | `NETX_API_URL`（**可指向远端**）、可选 `NETX_API_TOKEN`、`NETX_LANG` |

**两件事情要分开：**

| 组件 | 跑在哪 | 配置 |
|------|--------|------|
| **netx REST API**（告警/网元数据） | 本机或远端服务器 | `NETX_API_URL`，例如 `http://10.0.0.5:8890` |
| **netx MCP 子进程**（stdio，给 oclaw 调工具） | **必须与 oclaw 同机**（或 oclaw 能 `python` 到的环境） | `pip install -e <netx>/packages/netx-mcp` 后 `python -m netx_mcp` |

远端只部署 **netx 服务** 时：把 `NETX_API_URL` 改成远端地址即可；**不需要** `NETX_REPO_ROOT`。

本机开发若未 `pip install`，可临时用脚本路径（二选一）：

```json
"entry_args": ["D:/project/chatgpt/netx/netx_api/mcp_server.py"]
```

或在 oclaw 机执行一次（推荐，与远端 API 无关）：

```powershell
pip install -e D:/project/chatgpt/netx/packages/netx-mcp
```

**注意**：`source_type=local` 表示跳过 npm/pypi 的「安装包」步骤，但 oclaw 机上仍须能 `import netx_mcp`（通过上面的 pip 安装）。

Then run **Health** → **Sync Tools**.

### Expected MCP tools (12)

| MCP tool | oclaw namespaced | Legacy builtin (if enabled) |
|----------|------------------|----------------------------|
| `queryUmeAlarms` | `mcp__netx__queryUmeAlarms` | `netx_query_ume_alarms` |
| `aggregateUmeAlarms` | `mcp__netx__aggregateUmeAlarms` | `netx_aggregate_ume_alarms` |
| `runUmeDiagnostics` | `mcp__netx__runUmeDiagnostics` | `netx_run_ume_diagnostics` |
| `queryUmeNeInventory` | `mcp__netx__queryUmeNeInventory` | `netx_query_ume_ne_inventory` |
| `getUmeNe` | `mcp__netx__getUmeNe` | `netx_get_ume_ne` |
| `queryUmeAlarmsRaw` | `mcp__netx__queryUmeAlarmsRaw` | `netx_query_ume_alarms_raw` |
| `aggregateUmeAlarmsRaw` | `mcp__netx__aggregateUmeAlarmsRaw` | `netx_aggregate_ume_alarms_raw` |
| `listUmeAlarmFields` | `mcp__netx__listUmeAlarmFields` | `netx_list_ume_alarm_fields` |
| `sqlQueryUme` | `mcp__netx__sqlQueryUme` | `netx_sql_query_ume` |
| `listManagedNe` | `mcp__netx__listManagedNe` | `netx_list_managed_ne` |
| `getManagedNe` | `mcp__netx__getManagedNe` | `netx_get_managed_ne` |
| `execManagedNe` | `mcp__netx__execManagedNe` | `netx_exec_managed_ne` |

**不暴露**（已废弃 Excel 导入批次链路）：`netx_query_alarms`、`netx_list_import_batches`、`netx_sql_query`（带 `batch_id`）等。

## 3) Bind to ops specialist

In Admin **MCP specialist binding**, include server **`netx`** for the ops workspace/specialist.

## 4) Dual-track: builtin vs MCP

| Setting | Effect |
|---------|--------|
| `OCLAW_NETX_BUILTIN_TOOLS=0` (default) | Only MCP tools (`mcp__netx__*`); no duplicate inline `netx_*` in catalog |
| `OCLAW_NETX_BUILTIN_TOOLS=1` | Registers legacy inline HTTP tools **and** MCP if installed — avoid binding both unless testing migration |

Runtime anchor inject (`OCLAW_OPS_NETX_CONTEXT_INJECT=1`) still works without builtin tools; it only needs netx API reachable at `NETX_API_URL` / `OCLAW_NETX_BASE_URL`.

## 5) Cursor / Claude Desktop

与 §2 相同：直接复制 `D:/project/chatgpt/netx/mcp.json` 到 Cursor 配置即可；oclaw Admin 粘贴同一份 JSON 安装。

## 6) External link in Admin

Admin sidebar **Open netx ops tool** → `http://127.0.0.1:5173/` (edit in `interfaces/admin/static/index.html` if host/port differs).

## 7) netx → oclaw AP analyze auth

`netx` can call:

- `POST /admin/api/ops-ai/analyze-sync`
- `GET /admin/api/ops-ai/health`

Shared token:

1. oclaw: `OCLAW_OPS_AI_SHARED_TOKEN=<token>`
2. netx: `NETX_OCLAW_ANALYZE_TOKEN=<token>`

Timeouts: set `NETX_OCLAW_ANALYZE_READ_TIMEOUT_SEC` (default `180`) in netx if analyze-sync is slow.

Integration status: `GET http://127.0.0.1:8890/v1/integrations/status`

## 8) Observe AP calls in oclaw

- `GET /admin/api/ops-ai/logs?limit=50&offset=0` (requires `admin:user:write`)
