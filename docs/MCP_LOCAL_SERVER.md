# 本地 MCP 工具开发与接入指南（stdio / JSON-RPC）

本文档用于指导你在本地编写 MCP Server，并接入当前系统的 MCP 市场。

当前系统对 MCP 的主流程已统一为标准协议：

- `initialize`
- `notifications/initialized`
- `tools/list`
- `tools/call`

> 兼容说明：系统内部仍保留对旧 `op` 风格消息的回退兼容，但不建议新工具继续使用旧协议。

---

## 1. 你要实现什么

你写的本地工具不是直接写成 `ToolSpec`，而是写成一个 **MCP Server 子进程**，通过标准输入输出（stdio）和系统通信。

系统会：

1. 启动你的进程（`entry_command + entry_args`）
2. 发送 `initialize`
3. 接收 `tools/list`
4. 在用户调用时发送 `tools/call`

---

## 2. 最小可运行示例（Python）

保存为 `mcp_echo_server.py`：

```python
from __future__ import annotations

import json
import sys
from typing import Any


def ok(rid: Any, result: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": rid, "result": result}, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def err(rid: Any, code: int, message: str) -> None:
    sys.stdout.write(
        json.dumps(
            {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}},
            ensure_ascii=False,
        )
        + "\n"
    )
    sys.stdout.flush()


for raw in sys.stdin:
    raw = raw.strip()
    if not raw:
        continue

    try:
        req = json.loads(raw)
    except Exception:
        continue

    rid = req.get("id")
    method = str(req.get("method") or "")
    params = req.get("params") if isinstance(req.get("params"), dict) else {}

    if method == "initialize":
        ok(
            rid,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "echo-mcp", "version": "0.1.0"},
            },
        )
        continue

    if method == "notifications/initialized":
        # 通知类消息不需要返回
        continue

    if method == "tools/list":
        ok(
            rid,
            {
                "tools": [
                    {
                        "name": "echo",
                        "description": "回显输入文本。",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string", "description": "要回显的文本"}
                            },
                            "required": ["text"],
                            "additionalProperties": False,
                        },
                    }
                ]
            },
        )
        continue

    if method == "tools/call":
        tool_name = str(params.get("name") or "")
        arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}

        if tool_name != "echo":
            err(rid, -32601, f"unknown tool: {tool_name}")
            continue

        text = str(arguments.get("text") or "")
        ok(rid, {"content": [{"type": "text", "text": text}]})
        continue

    err(rid, -32601, f"method not found: {method}")
```

---

## 3. 在管理台中接入

### 3.0 已安装 MCP 从库里消失时（换库 / 表被清空）

`mcp_server_registry` 存在默认 SQLite（见 `data/ai_ops.sqlite`）中。若列表变成 0 条，可在仓库根执行 **`python scripts/seed_mcp_registry.py`**，从 **`data/mcp_registry.seed.json`** 写回示例条目（含 `local-echo` 与 `mcp-context7`，可按需编辑该 JSON 再执行）。写回后在管理台对各服务执行 **Health** → **Sync Tools**；若曾换过 `OPS_ASSISTANT_DB_PATH`，请确认网关与脚本指向**同一**库文件。

### 3.1 表单安装（推荐）

在 MCP 页面填：

- `source_type`: 可自定义用于记录（如 `pypi`）
- `source_ref`: 自定义来源标识（如 `local-echo`）
- `entry_command`: `python`
- `entry_args`: `D:/path/to/mcp_echo_server.py`

然后执行：

1. `Install`
2. `Health`
3. `Sync Tools`

工具数量 > 0 即接通成功。

### 3.2 Cursor JSON 安装

在 Plugins **【2】从 Cursor JSON 安装** 粘贴与 Cursor `mcp.json` 相同的文档（仅支持 `mcpServers`，不再兼容旧的 `servers[]` / 表单字段）：

```json
{
  "mcpServers": {
    "local-echo": {
      "command": "python",
      "args": ["__REPO_ROOT__/examples/mcp_echo_server.py"]
    },
    "remote-demo": {
      "url": "https://example.com/mcp",
      "headers": { "Authorization": "Bearer ${API_KEY}" }
    }
  }
}
```

- stdio：`command` / `args` / `env`
- 远程：仅 `url`（可带 `headers`）时由服务端归一成 `npx -y mcp-remote …` 桥接
- `__REPO_ROOT__/…` 在安装时展开为仓库根路径

**导出与自动备份**

- **Export JSON** 下载当前全部已安装 MCP 的 Cursor `mcpServers` 快照。
- 安装 / 改配置 / 卸载删记录后刷新 **`oclaw/_local/mcp_registry_migrated.json`**（同结构）。可用 `python -m runtime.operations.scripts.seed_mcp_registry path/to/file.json` 灌库。密钥仍放 `oclaw/_local/mcp_local.env`。

### 3.3 MCP 工具可见性（仅绑定）

线侧「打压」策略（分层压缩 / 闲置惩罚 / 9999 永禁 / role_mode）**已移除**。

发给 LLM 的 MCP 工具范围只由 **专家 ↔ MCP server 绑定** 决定：

- 管理台 Plugins：**【6】专家 MCP 绑定看板**、**【7】MCP 专家绑定（编辑）**
- 持久化键：`mcp_specialist_server_binding`（及粗粒度兜底 `mcp_allowed_specialists` / `AIA_MCP_SPECIALISTS`）
- 语义：绑定 JSON **已有条目**时，某专家**缺键 / null / `[]`** → 该专家 **不挂任何 MCP**；仅当绑定未配置或为 `{}` 时才回退粗粒度 allowlist（可见全部已启用 MCP）
- 运行时：`materialize_mcp_tools_for_specialist`；上送前仅做 schema complete 与可选 JSON 体积压缩（`prepare_openai_tools_for_llm_api`）

---

## 4. 专家分配（谁能用这个工具）

当前系统支持“按专家组”分配 MCP 工具可见性：

- 在 MCP 页面 `MCP specialists` 勾选可用专家
- 保存后立即生效（持久化在数据库）

注意：当前是“专家级分配”，不是“单工具级分配”。

---

## 5. 编写规范（强烈建议）

1. **stdout 只输出 JSON-RPC 响应行**  
   日志请写到 `stderr`，否则容易触发 `protocol_mismatch`。

2. **`tools/list` 返回稳定 schema**  
   建议所有参数都写明 `type` 与 `required`，并设 `additionalProperties: false`。

3. **`tools/call` 出错要可解释**  
   优先通过 JSON-RPC `error` 返回明确错误信息。

4. **避免长时间阻塞**  
   长任务应拆分或优化，否则会出现 `mcp_runtime_timeout`。

---

## 6. 常见错误与排查

- `mcp_runtime_timeout`  
  含义：子进程超时未返回。  
  排查：先本地单独运行 server，确认单次调用耗时；必要时调大 `timeout_s`。

- `mcp_runtime_protocol_mismatch`  
  含义：收到的不是 JSON-RPC 响应。  
  排查：检查是否把日志打印到了 stdout。

- `mcp_runtime_bad_json`  
  含义：输出不是合法 JSON。  
  排查：检查编码、换行、对象结构。

- `mcp_tools_list_invalid`  
  含义：`tools/list` 返回结构不符合预期。  
  排查：确认返回 `result.tools` 为数组，元素包含 `name`、`inputSchema`。

---

## 7. 建议开发流程

1. 本地先用脚本手动跑通 JSON-RPC
2. 管理台安装（建议先 `dry_run`）
3. 执行 `Health`、`Sync Tools`
4. 在 `Check Installed` 做批量体检
5. 按专家映射开放给目标专家

---

## 8. 与原有内置工具关系

MCP 工具是增量能力，不会替代原有内置工具体系。  
最终都走统一 `ToolExecutor` 执行链（策略、超时、审计一致）。

# Local MCP Server Guide (stdio)

## Goal

Write local tools as a **standard MCP server over stdio (JSON-RPC)**, then connect them from Admin → Plugins → Install from Cursor JSON.

This project now uses MCP standard flow in runtime:

- `initialize`
- `notifications/initialized`
- `tools/list`
- `tools/call`

Legacy custom `op` messages are only compatibility fallback.

---

## Minimal Python MCP Server

Save as `mcp_echo_server.py`:

```python
from __future__ import annotations

import json
import sys
from typing import Any


def _ok(rid: Any, result: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": rid, "result": result}, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _err(rid: Any, code: int, message: str) -> None:
    sys.stdout.write(
        json.dumps(
            {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}},
            ensure_ascii=False,
        )
        + "\n"
    )
    sys.stdout.flush()


for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        req = json.loads(line)
    except Exception:
        continue
    rid = req.get("id")
    method = str(req.get("method") or "")
    params = req.get("params") if isinstance(req.get("params"), dict) else {}

    if method == "initialize":
        _ok(rid, {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "echo-mcp", "version": "0.1.0"}})
        continue

    if method == "notifications/initialized":
        # Notification has no response.
        continue

    if method == "tools/list":
        _ok(
            rid,
            {
                "tools": [
                    {
                        "name": "echo",
                        "description": "Echo input text.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"text": {"type": "string"}},
                            "required": ["text"],
                            "additionalProperties": False,
                        },
                    }
                ]
            },
        )
        continue

    if method == "tools/call":
        name = str(params.get("name") or "")
        args = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        if name != "echo":
            _err(rid, -32601, f"unknown tool: {name}")
            continue
        text = str(args.get("text") or "")
        _ok(rid, {"content": [{"type": "text", "text": text}]})
        continue

    _err(rid, -32601, f"method not found: {method}")
```

Run manually (sanity check):

```bash
python mcp_echo_server.py
```

Then send one JSON-RPC request line from stdin to verify.

---

## Install in Admin (Cursor JSON)

Paste Cursor `mcpServers` JSON in **Plugins → Install from Cursor JSON**. There is no MCP Market UI; edit installed servers via the Edit action (same Cursor entry shape).

For a local Python script:

```json
{
  "mcpServers": {
    "local-echo": {
      "command": "python",
      "args": ["D:/project/chatgpt/examples/mcp_echo_server.py"]
    }
  }
}
```

After install:

1. `Health`
2. `Sync Tools`
3. Verify tool count > 0

---

## @modelcontextprotocol/server-filesystem 与网关工作区

官方 **`@modelcontextprotocol/server-filesystem`** 只在**进程启动时**把命令行里列出的目录当作可访问根；多装一个路径就要多传一个 argv，否则 `list_directory` 等工具无法列出该目录。

本仓库在启动该 MCP 时会**自动合并**与内置工作区一致的路径来源，并**去重后追加**到 `entry_command` + `entry_args` 之后（不改变你在管理台填写的主根，只追加额外根）：

| 来源 | 说明 |
| --- | --- |
| `OPS_WORKSPACE_EXTRA_ROOTS` | 环境变量，`\|` 分隔 |
| `OPS_MCP_FILESYSTEM_EXTRA_ROOTS` | 环境变量或 SQLite `settings` 表同名键，仅影响该 MCP |
| Admin「工作区路径」 | **当前用户聊天会话**（`ui_session_owner` 绑定的 `session_id`）对应账号的 `extra_roots`（`\|` 拆分）；不会合并其他用户。若 `ui_session_owner` 行缺失，会从请求里携带的 `tenant_id` / `user_id`（`metadata`）**再拉一份**同一条 allowlist，与内置 `resolve_workspace_path` 及 MCP 追加 argv 对齐。 |
| Windows 路径 | 在网关侧与 MCP argv 中会对路径作规范化；若仍报「无权限」或子进程报路径不在根下，可对比管理台中保存的「绝对路径」与资源管理器里实际盘符/大小写是否一致，修改工作区后对该 MCP **Health → Sync Tools**。 |

**与 `allow_any_path` 的关系**：管理台里的 **`allow_any_path` 只影响网关内置工具**（走 `resolve_workspace_path` 的读文件、glob、`run_command` 等），相当于在 Python 侧跳过「必须在 workspace 根或 `extra_roots` 下」的检查。官方 **`server-filesystem` 不认这个字段**：子进程只认启动时写在 argv 里的**具体目录列表**，没有「允许任意路径」的等价开关，因此单靠 `allow_any_path: true` **不会**把 `D:\download` 等路径自动加进 MCP。要让 MCP 列到这些目录，请把它们写进 **`extra_roots`**（或 `OPS_WORKSPACE_EXTRA_ROOTS` / `OPS_MCP_FILESYSTEM_EXTRA_ROOTS`），再 **Health → Sync Tools**。

**运维注意**：同一网关进程内，不同用户对话会各自 materialize 一套 MCP 工具绑定（argv 含该用户 `extra_roots` + 全局 env）。管理台 **Health / Sync Tools** 无用户会话上下文，此时仅合并 **环境变量与 settings**，不含任一用户的 DB `extra_roots`。

修改环境或 DB 后，请对相应 MCP 执行 **`Health` → `Sync Tools`**（或重启网关），以便新进程带上更新后的 argv。

---

## Tool Result Format Recommendations

For `tools/call` result:

- success: return `{"content":[{"type":"text","text":"..."}]}`  
- failure: return JSON-RPC `error` or `result` with `isError=true`

Keep responses deterministic and JSON-serializable.

---

## Common Errors

- `mcp_runtime_timeout`  
  Server did not answer in time. Check blocking calls, raise `timeout_s`, or optimize startup.

- `mcp_runtime_protocol_mismatch`  
  Output is not JSON-RPC response line. Ensure stdout only emits JSON-RPC lines (move logs to stderr).

- `mcp_runtime_bad_json`  
  Response line is malformed JSON. Validate serialization and newline framing.

- `mcp_tools_list_invalid`  
  `tools/list` did not return valid `tools` array.

---

## 通识工具库与 Cursor / Claude Code / oclaw（能力对齐说明）

**已能覆盖的常见编码助手能力**：仓库读写与搜索（内置 workspace + MCP filesystem）、Git 本地与 GitHub 远端、网页抓取与浏览器自动化（fetch / playwright）、会话库 SQLite、日历与时间、PDF、顺序思考与 memory MCP 等。

**单靠 MCP 无法等价的部分**：IDE 内 LSP 实时红线（Cursor 编辑器集成）、oclaw 式 **ACP 外接** Claude Code/Codex 子进程（需单独编排/通道产品化）。

### Context7（库文档时效）

- **作用**：按库名/版本拉取较新的官方文档片段，减少「API 记错版本」类幻觉。  
- **安装**：`python scripts/install_mcp_context7.py`，或管理台 `POST /admin/api/mcp/install` 使用 [`examples/mcp_install_context7.json`](../examples/mcp_install_context7.json) 中的 `payload`。
- **密钥**：在 **`oclaw/_local/mcp_local.env`**（推荐）或 `data/mcp_local.env`（兼容）设置 `CONTEXT7_API_KEY`（见 [context7.com/dashboard](https://context7.com/dashboard)）。两处都存在时**同键以 `oclaw/_local/mcp_local.env` 为准**（覆盖 `data` 中的同键）。**写入任一合并 `mcp_local.env` 的键会自动传入 MCP 子进程**；若密钥只配在宿主/Docker 环境、不进文件，才依赖内置或自定义的 `AIA_MCP_ENV_ALLOWLIST` 补充名单。  
- **装完后**：`Health` → `Sync Tools` → 将 `mcp-context7` 加入通识 specialist 的 MCP 绑定（若脚本已成功 Sync，会自动追加）。

### Bailian WebSearch（DashScope）

- **密钥**：在 `oclaw/_local/mcp_local.env`（推荐）设置 `DASHSCOPE_API_KEY=...`。
- **关键注意**：密钥写在 **`mcp_local.env` 里即可传入 MCP**。若 **`DASHSCOPE_API_KEY` 只存在于宿主环境**、未写入 `mcp_local.env`，须确保其出现在 **`AIA_MCP_ENV_ALLOWLIST` 默认或自定义补充名单**中（或用 **`AIA_MCP_ENV_ALLOWLIST_EXTRA`** 追加）。常见表现是：
  - `error_code: mcp_runtime_empty_response`
  - `error: empty_response`
- **排查顺序**：
  1. 确认 `mcp_local.env` 已写 `DASHSCOPE_API_KEY`
  2. 确认 allowlist 包含 `DASHSCOPE_API_KEY`
  3. 在 Admin 对该 MCP 执行 `Health` → `Sync Tools`
  4. 确认该 MCP 已绑定到当前会话使用的 specialist（不只是 `generalist`）

### 通识侧终端能力（`run_command`）

与 Claude Code「在仓库里跑命令」类似的能力来自内置 **`run_command`**，但通识 lane 需同时满足：

1. 环境 **`OPS_ENABLE_RUN_COMMAND=1`**（见 `oclaw/tools/catalog.py` 与 `oclaw/tools/experts/workspace/shell_tools.py` 门控）。  
2. 仅在 **可信仓库 / 内网** 开启；否则易误执行高危命令。

### Postgres / Linear / Slack / Sentry 等

按实际业务栈再装对应 MCP 即可；无相关系统则不必安装，避免工具膨胀与误选。

---

## Multi-specialist Assignment

MCP tools are assigned in Admin UI by specialist mapping.  
Only selected specialists can see/use MCP tools at runtime.

