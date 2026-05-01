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

### 3.2 JSON 安装

**单条**（在 Plugins **「3」MCP 安装** 的 **Install from JSON** 中粘贴，或作 array 的其中一个元素）：

```json
{
  "source_type": "pypi",
  "source_ref": "local-echo",
  "server_id": "local-echo",
  "version": "",
  "entry_command": "python",
  "entry_args": ["D:/project/chatgpt/examples/mcp_echo_server.py"],
  "required_permissions": [],
  "risk_level": "low",
  "enabled": true,
  "timeout_s": 30
}
```

**批量**：以下三种写法 **`Install from JSON`** 都支持，会**逐条** preflight + install（任一条失败会记结果并继续下一条，最后看结果 JSON）：

1. **数组**：`[ { 上面一条的字段… }, { … } ]`
2. **对象包一层 `servers`**（与 `data/mcp_registry.seed.json`、导出文件一致）：
   ```json
   {
     "servers": [
       { "source_type": "npm", "source_ref": "@upstash/context7-mcp", "server_id": "mcp-context7", "version": "", "entry_command": "npx", "entry_args": ["-y", "@upstash/context7-mcp"], "env_schema": {}, "required_permissions": [], "risk_level": "medium", "enabled": true, "timeout_s": 60, "dry_run": false }
     ]
   }
   ```
3. **带 `payload` 的单条**（如 `examples/mcp_install_context7.json`）：
   ```json
   { "payload": { "source_type": "npm", "source_ref": "…", "server_id": "…" } }
   ```

路径占位符 `__REPO_ROOT__/…` 在**管理台安装 / preflight** 中会与 `scripts/seed_mcp_registry.py` 一样展开为仓库根下的绝对路径（如 `mcp-echo` 的脚本路径、filesystem 的目录根、sqlite 的库文件路径）。若不用占位符，可直接写本机绝对路径。

**导出与自动备份**

- 在 **【4】已安装 MCP 服务** 使用 **Export JSON (download)**，可下载当前库中**全部**已安装 MCP 的可重装 JSON（`servers` 包 + `exported_at`）。
- 每次 **安装、重装、卸载且删除库记录、Delete** 成功后，会刷新 **`oclaw/_local/mcp_registry_migrated.json`**（与导出内容同结构，便于换库/换机后把文件粘回 **Install from JSON** 或 `python scripts/seed_mcp_registry.py path/to/file.json` 注意 seed 会跑 npm/pypi 安装步骤，与 `dry_run` 等字段一致）。该文件建议加入 `.gitignore`（如未忽略），避免本机差异被误提交；密钥仍放在 `oclaw/_local/mcp_local.env` 等环境变量，不在此 JSON 中。

### 3.3 MCP 工具线侧策略（上送压缩与惩罚）

在管理台 **Plugins（插件）** 页中的 **「线侧策略」** 折叠区块（**【6】全局参数**、**【7】已安装工具**）可配置发往 LLM 的 OpenAI 格式 `tools[]` 的**分层压缩**、**全局闲置惩罚**，以及**按完整工具名** `mcp__{server_id}__{tool_name}` 的策略（与模型 `base_url` 解耦时，将 **wire_policy** 设为 `always`）。**【7】** 中每个工具的等级为**数字输入框**（任意整数 1–9998；留空表示未配置；0 与留空语义不同，见下表）。

**【7】表格筛选与专家列（管理台）**

- 表头**第二行**为各列筛选输入（子串匹配，不区分大小写）：`server`、`tool`、`wire_name`、**专家**、`count`（上下界）、`last_ts`、惩罚/解封说明、策略**等级**（上下界）。分页条数按**筛选后**结果计算。
- **专家**列由本页当前 **MCP 专家绑定草稿**（`mapping`）与后端返回的 `available_specialists` 合并推导：某 `server_id` 出现在哪些专家的绑定列表中，即显示为逗号分隔的专家 id；可按专家子串筛选。勾选「仅已勾选」时只显示当前勾选的行（勾选集合在筛选、翻页间保留）。
- 同页 **【8】专家 MCP 绑定看板（自动）**：按当前草稿与**已安装 MCP** 各服务的 `tools` 列表，汇总每个专家绑定的 **MCP 个数** 与 **tool 条数**（各已绑定 server 的 `tools` 长度之和）；专家集合随 `available_specialists` 与 `mapping` 中的键自动扩展，无需写死。
- **【9】MCP 专家绑定（编辑）** 为原绑定编辑区（勾选、反向视图、保存）；与【8】看板联动，改绑定后看板即时刷新（无需单独保存看板）。

**持久化（SQLite `app_setting`）**

| 键 | 含义 |
| --- | --- |
| `mcp_tool_wire_admin_config` | JSON：全局参数 + `wire_policy`（`inherit` / `always` / `never`）、`penalty_disable` 等 |
| `mcp_tool_wire_tool_policies` | JSON：`{ "mcp__sid__tool": 等级 }` |
| `mcp_tool_wire_penalty_state` | JSON：各工具惩罚状态机（`phase`、`omit_until`、`wave_ts`、`kind`），由运行时维护，一般无需手改 |

**`wire_policy`**

- `inherit`：与原先一致，默认在 DashScope 兼容 URL 上启用线侧策略；其它环境变量 `OPS_MCP_WIRE_*` 仍可作为默认值来源。
- `always`：**不依赖 URL**，始终启用分层与惩罚逻辑（适合非 DashScope 网关也要控 payload）。
- `never`：关闭分层/惩罚逻辑；**等级 `9999` 永久封禁仍会过滤该工具**（不上送）。

**按工具等级（`mcp_tool_wire_tool_policies`）**

| 配置 | 库中是否存在键 | 行为 |
| --- | --- | --- |
| **未配置**（管理台留空 / `GET` 中 `policy_level` 为 `null`、`policy_in_db` 为 `false`） | 否 | **自动走全局**：参与用量排名与分层压缩；适用**全局**闲置小时与罚时长；可被 **Top N 全量**豁免全局闲置惩罚。新安装 MCP 在 **Sync Tools** 后出现新 `wire_name`，默认即为此状态，无需手工登记。 |
| **显式 `0`** | 是 | **不参与**全局闲置 omission；仍参与用量分层。与「未配置」不同。 |
| **显式 `1`～`9998`** | 是 | 与 Top N **无关**：距上次成功调用超过 **N×10 分钟** 视为闲置，进入罚时 **N×10 分钟** 的上送 omission；罚满后需再次闲置达到阈值才会再罚（状态与 `last_ts` / `kind` 对齐）。 |
| **显式 `9999`** | 是 | **永久**从线侧 `tools[]` 中移除（彻底封禁）。 |

**生效优先级（同一工具上的概念顺序，便于排障）**

1. **`9999` 永久封禁**（若已写入 `mcp_tool_wire_tool_policies`）：在组装 `tools[]` 的较早阶段即剔除，不进入后续分层与动态惩罚状态机。  
2. **显式 `1`～`9998`**：走按工具闲置/罚分钟逻辑，**不享受** Top N 对「全局惩罚」的豁免。  
3. **显式 `0`**：跳过全局闲置 omission，仍走压缩档位。  
4. **未配置**：走全局线侧逻辑（含全局闲置与 Top N 豁免等），由 `prepare_openai_tools_for_llm_api` 与 `mcp_tool_wire_admin_config` / 环境变量共同决定。

`wire_policy=never` 时关闭分层与动态惩罚，但 **`9999` 仍会过滤** 对应工具。

全局闲置小时、罚时长（分钟）、Top N 全量、medium 档位等，在 **【6】** 中可调；未写入 `app_setting` 的项继续沿用环境变量（见仓库根 `data/mcp_local.env.example` 中 `OPS_MCP_WIRE_*`）。

**Admin HTTP API**（需 `admin:tenant:write`，与 MCP 安装类接口一致）

- `GET /admin/api/mcp/tool-wire` — 返回合并后的 `config`、当前 `policies`、`penalty_state`，以及已安装 MCP 工具列表（每条含 `policy_level`：`null` 表示未在库中配置，`policy_in_db` 标明是否持久化过）及惩罚/解封说明。
- `POST /admin/api/mcp/tool-wire/config` — 保存全局参数（部分字段可增量合并）。
- `POST /admin/api/mcp/tool-wire/policies` — body：`{ "policies": { "mcp__...": 整数等级 }, "clears": ["mcp__...", ...]（可选） }`。先按 `clears` 从已存策略中**删除键**（用于管理台留空后恢复「未配置」），再合并 `policies`。
- `POST /admin/api/mcp/tool-wire/policies/batch` — body：`{ "level": 等级, "wire_names": ["mcp__...", ...] }`，批量写入策略。

实现代码：`oclaw/platform/llm/tool_wire_policy.py`；在发 Chat Completions 前由 `prepare_openai_tools_for_llm_api` 应用。

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

Write local tools as a **standard MCP server over stdio (JSON-RPC)**, then connect them from Admin MCP Market.

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

## Install in Admin MCP Market

For local Python script:

- `source_type`: `pypi` (or any source type you use for bookkeeping)
- `source_ref`: custom label (for example `local-echo`)
- `entry_command`: `python`
- `entry_args`: `<absolute-or-relative-path-to-script>`

Example JSON install payload:

```json
{
  "source_type": "pypi",
  "source_ref": "local-echo",
  "server_id": "local-echo",
  "version": "",
  "entry_command": "python",
  "entry_args": ["D:/project/chatgpt/examples/mcp_echo_server.py"],
  "required_permissions": [],
  "risk_level": "low",
  "enabled": true,
  "timeout_s": 30
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
- **密钥**：在 **`oclaw/_local/mcp_local.env`**（推荐）或 `data/mcp_local.env`（兼容）设置 `CONTEXT7_API_KEY`（见 [context7.com/dashboard](https://context7.com/dashboard)）。两处都存在时**同键以 `oclaw/_local/mcp_local.env` 为准**（覆盖 `data` 中的同键）。未自定义 `OPS_MCP_ENV_ALLOWLIST` 时，网关默认 allowlist 已包含 `CONTEXT7_API_KEY`（见 `oclaw/runtime/operations/mcp_env.py`）；若你自定义了 allowlist，请手动追加该键。  
- **装完后**：`Health` → `Sync Tools` → 将 `mcp-context7` 加入通识 specialist 的 MCP 绑定（若脚本已成功 Sync，会自动追加）。

### Bailian WebSearch（DashScope）

- **密钥**：在 `oclaw/_local/mcp_local.env`（推荐）设置 `DASHSCOPE_API_KEY=...`。
- **关键注意**：如果你自定义了 `AIA_MCP_ENV_ALLOWLIST` / `OPS_MCP_ENV_ALLOWLIST`，必须显式包含 `DASHSCOPE_API_KEY`，否则 MCP 子进程拿不到该密钥，常见表现是：
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

