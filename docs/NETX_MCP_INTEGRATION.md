# netx MCP Integration (same-host)

This guide wires `oclaw` to the independent ops tool in:

- `D:/project/chatgpt/netx`

Assumption: `oclaw` and `netx` run on the same host.

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

## 2) Register netx MCP in oclaw Admin

Use MCP install payload from:

- `D:/project/chatgpt/netx/mcp_install_payload.json`

Equivalent manual values:

- `source_type`: `local`
- `source_ref`: `netx-local-mcp`
- `server_id`: `netx-local`
- `entry_command`: `python`
- `entry_args`: `["D:/project/chatgpt/netx/netx_api/mcp_server.py"]`
- `timeout_s`: `30`

Then run:

1. `Health`
2. `Sync Tools`

Expected tools:

- `queryAlarms`
- `aggregateAlarms`
- `getImportBatch`
- `runDiagnostics`

## 3) Bind to ops specialist

In MCP specialist binding, include `netx-local` for your ops specialist/workspace.

## 4) Use from chat

After binding, model can call namespaced tools like:

- `mcp__netx-local__queryAlarms`
- `mcp__netx-local__aggregateAlarms`
- `mcp__netx-local__getImportBatch`
- `mcp__netx-local__runDiagnostics`

## 5) External link in Admin

`oclaw` admin sidebar includes an external link:

- `Open netx ops tool` -> `http://127.0.0.1:5173/`

If your netx host/port differs, update the link in:

- `interfaces/admin/static/index.html`

## 6) netx -> oclaw AP analyze auth

`netx` can call:

- `POST /admin/api/ops-ai/analyze-sync`
- `GET /admin/api/ops-ai/health`

Recommended auth:

1. Set shared token in `oclaw` runtime env:
   - `OCLAW_OPS_AI_SHARED_TOKEN=<your_token>`
2. Set same token in `netx`:
   - `NETX_OCLAW_ANALYZE_TOKEN=<your_token>`

Then `netx /v1/ap/analyze` can invoke `oclaw` synchronously.

**Timeouts:** `netx` → `oclaw` uses HTTP; `analyze-sync` often exceeds old ~35s limits. In netx set `NETX_OCLAW_ANALYZE_READ_TIMEOUT_SEC` (default `180` in `netx_api/config.py`) if you still see read timeouts on slow models or multi-tool turns.

Integration health in netx:

- `GET http://127.0.0.1:8890/v1/integrations/status`

## 7) Observe AP calls in oclaw

Recent ops-ai analyze calls can be fetched from:

- `GET /admin/api/ops-ai/logs?limit=50&offset=0`

Permission: `admin:user:write` (same as admin audit access).
