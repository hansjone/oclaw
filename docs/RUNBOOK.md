# 运行手册（RUNBOOK）

本文档面向“日常运维与排障”场景，聚焦可直接执行的命令与操作顺序。

关联文档：

- trace 字段与阶段对照：`docs/oclaw-trace-taxonomy.md`
- skill 安装/执行排障：`docs/oclaw-skill-troubleshooting.md`

---

## 1. 统一入口（只保留最新）

所有运维命令统一通过 `scripts/`，不要再使用 `python -m oclaw.runtime.operations ...` 或历史 `.bat` 方式。

补充：工具脚本也统一放在 `scripts/`（例如 `seed_mcp_registry.py`、`ws_probe.py`）。

---

## 2. 首次初始化

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_venv.ps1
```

Linux/macOS:

```bash
./scripts/start_ops.sh
```

---

## 3. 配置企业微信（Bot 模式）

在网关启动后，统一在管理台完成通道配置，不再使用旧 CLI 命令入口。

---

## 4. 启停运行栈

启动：

`powershell -ExecutionPolicy Bypass -File .\scripts\start_all.ps1 -Background`

（含微信 sidecar）：

`powershell -ExecutionPolicy Bypass -File .\scripts\start_all.ps1 -Background -WithWeixin`

（含微信 sidecar + wiki worker）：

`powershell -ExecutionPolicy Bypass -File .\scripts\start_all.ps1 -Background -WithWeixin -WithWikiWorker`

查看状态：

`powershell -ExecutionPolicy Bypass -File .\scripts\status_all.ps1`

（含微信 sidecar）：

`powershell -ExecutionPolicy Bypass -File .\scripts\status_all.ps1 -WithWeixin`

（含微信 sidecar + wiki worker）：

`powershell -ExecutionPolicy Bypass -File .\scripts\status_all.ps1 -WithWeixin -WithWikiWorker`

停止：

`powershell -ExecutionPolicy Bypass -File .\scripts\stop_all.ps1`

（含微信 sidecar）：

`powershell -ExecutionPolicy Bypass -File .\scripts\stop_all.ps1 -WithWeixin`

（含微信 sidecar + wiki worker）：

`powershell -ExecutionPolicy Bypass -File .\scripts\stop_all.ps1 -WithWeixin -WithWikiWorker`

说明：

- `stack up` 不会启动 Streamlit
- 聊天页面统一使用 `http://127.0.0.1:8787/chat`
- `--with-ui` 为历史参数，不再生效

---

## 5. 仅启动网关

`powershell -ExecutionPolicy Bypass -File .\scripts\start_gateway.ps1`

---

## 6. 管理台与认证

先启动网关，再访问：

- `http://127.0.0.1:8787/admin`
- `http://127.0.0.1:8787/chat`

### 6.1 初始化管理员（幂等）

```bash
curl -X POST http://127.0.0.1:8787/admin/api/auth/bootstrap
```

### 6.2 登录获取 Bearer Token

```bash
curl -X POST http://127.0.0.1:8787/admin/api/auth/login \
  -H "content-type: application/json" \
  -d '{"tenant_id":"<tenant_id>","username":"administrator","password":"<pwd>","purpose":"console"}'
```

### 6.3 带 Token 调用受保护接口

```bash
curl http://127.0.0.1:8787/admin/api/users?tenant_id=<tenant_id> \
  -H "authorization: Bearer <token>"
```

RBAC 规则要点：

- `owner` 拥有完整管理权限
- 其它角色权限由 `role_permission` + `user_permission` 决定
- 跨租户写操作会被拒绝（`403`）

### 6.4 `/chat` 会话与用户隔离（排障）

Admin Chat 依赖表 **`ui_session_owner`**（`session_id` → `tenant_id` + `user_id`）判定「谁可见、谁可写」某条 `chat_session`。列表、读消息、流式回复、停止生成、导出等均经该归属校验。

**请勿依赖的历史行为（已移除）**

- 用户会话列表为空时，**不再**自动把库内所有「无 owner」会话划给该用户（否则多用户会互相看到对方会话）。
- 读取某 `session_id` 时，**不会**再「若无 owner 则绑定到当前请求用户」（否则谁先打开链接谁抢走归属）。

**若升级后有人看不到旧会话**

说明这些 `chat_session` 从未写入 `ui_session_owner`（列表与读接口均只认该表）。处理方式（需在维护窗口评估数据归属）：

1. 自行 SQL 排查：`SELECT s.id, s.title, s.created_at FROM chat_session s LEFT JOIN ui_session_owner o ON o.session_id = s.id WHERE o.session_id IS NULL;` 确认归属后按需 `INSERT INTO ui_session_owner(session_id, tenant_id, user_id, created_at) VALUES (...)`。
2. 在 **Python 控制台** 仅在**确认整库孤儿会话均属同一用户**时，可显式调用 `SqliteStore.backfill_orphan_chat_sessions_for_user`（该方法会一次性把**当前仍无 owner 的全部**会话绑到传入的 `user_id`，**不适合多用户已混用生产库**）。
3. **`administrator`** 在 **`/chat` 侧边栏**与普通用户相同，只列出 **自己名下**（`ui_session_owner.user_id` = 管理员账号）的会话，**不会**把他人会话混进自己的列表。查看本租户全部会话请用 **审计 / Session Monitor** 或接口 **`GET /admin/api/chat/admin/sessions`**（需相应权限）。单会话消息读写在管理员仍可按租户校验（便于从监控打开指定 `session_id`）。

**浏览器端**

独立 `/chat` 页在检测到 **登录租户/用户** 与上次不一致时会丢弃 URL 中的 `?session_id=`，避免同一浏览器换账号后仍打开上一用户的深链。

**工作区 ``extra_roots``（与编排临时会话）**

管理台为用户配置的 ``user_workspace_path_allowlist.extra_roots`` 通过 ``ui_session_owner`` 解析到租户+用户。总控编排里专家步往往在**无 owner 的临时** ``chat_session`` 上落库中间消息：内置路径类工具会携带 **用户 UI 会话 id 作为 fallback**，仍按该用户策略合并 ``extra_roots``；MCP filesystem 启动参数本就按用户聊天 ``session_id``（policy）合并，二者现已对齐。

### 6.5 主库路径与「删掉的会话又回来了 / 新建用户不见了」

默认主库为 **`data/ai_ops.sqlite`**（未设置 ``OPS_ASSISTANT_DB_PATH`` 时）。历史上曾把库放在 **`../data/ai_ops.sqlite`** 或 **`oclaw/platform/data/ai_ops.sqlite`**；首次启动若检测到这些旧位置且新主库尚不存在，会把整库**复制**到 `data/ai_ops.sqlite`，并把旧路径下的附件**补拷**到 `data/attachments/`（不覆盖已有文件）。确认新主库生效后，本机可按需清理旧目录（避免磁盘上留着陈旧副本）。

历史上若旧库里的 ``chat_session`` **行数大于**当前主库，会用**整份旧库覆盖**主库。用户大量**删除会话**后主库行数变少，会误触发该逻辑，表现为：**已删会话从旧快照恢复**、**只在主库里出现的新用户/新数据被整库覆盖掉**。

**当前版本已关闭该自动覆盖**；仅当显式设置环境变量 **`OPS_LEGACY_DB_FORCE_PREMERGE=1`** 时才允许按旧规则合并（仍会先把当前主库备份到 ``data/_pre_merge_sqlite_<时间戳>/``）。

**排障建议**：确认所有网关/进程使用**同一** ``OPS_ASSISTANT_DB_PATH``（或统一依赖默认 ``data/ai_ops.sqlite``）；若曾出现覆盖，可在 ``data/_pre_merge_sqlite_*`` 中找回被备份出去的主库副本。

---

## 7. 常用脚本入口

Windows PowerShell:

- `powershell -ExecutionPolicy Bypass -File .\scripts\start_gateway.ps1`
- `powershell -ExecutionPolicy Bypass -File .\scripts\status_all.ps1`
- `powershell -ExecutionPolicy Bypass -File .\scripts\stop_gateway.ps1`
- （联动）`powershell -ExecutionPolicy Bypass -File .\scripts\start_all.ps1 -Background`
- （联动）`powershell -ExecutionPolicy Bypass -File .\scripts\stop_all.ps1`

Linux/macOS:

- `./scripts/start_ops.sh`
- `./scripts/status_ops.sh`
- `./scripts/stop_ops.sh`

---

## 8. MCP 运维流程（管理台）

推荐顺序：

1. `Install`（或 `Reinstall`）
2. `Health`
3. `Sync Tools`
4. `Check Installed`（批量体检）

若失败，重点看错误码：

- `mcp_runtime_timeout`
- `mcp_runtime_protocol_mismatch`
- `mcp_runtime_bad_json`
- `mcp_tools_list_invalid`

详细开发与接入参考：`docs/MCP_LOCAL_SERVER.md`

---

## 9. 向量记忆配置（可选）

可通过环境变量或管理台配置：

- `MEMORY_VECTOR_ENABLED` (`0/1`)
- `MEMORY_VECTOR_BACKEND` (`sqlite` / `chroma` / `qdrant`)
- `MEMORY_VECTOR_TOPK`（默认 `5`）
- `MEMORY_WRITE_ENABLED` (`0/1`)
- `MEMORY_WRITE_MIN_CONFIDENCE`（默认 `0.75`）

故障降级策略：

- 向量后端不可用时，读写回退到 SQLite 向量实现
- 关闭写入时，不影响聊天主流程

---

## 10. 常见故障速查

### 10.1 管理台无法登录

- 是否设置 `AIA_ASSISTANT_PASSWORD`
- 是否重启服务并让新环境变量生效

### 10.2 MCP 显示可用但工具数为 0

- 先执行 `Health`
- 再执行 `Sync Tools`
- 再执行 `Check Installed`

### 10.3 Check Installed 全红

- 检查 server 是否输出标准 JSON-RPC（stdout）
- 日志必须写 stderr，避免协议污染
- 确认 `entry_command/entry_args` 正确

### 10.4 微信能收不能回 / 回不去

按顺序检查：

1) 网关是否健康（`/health` 必须快速返回）  
2) sidecar 是否运行（`weixin_status.ps1`）  
3) sidecar 日志是否有 `sendmessage` 失败提示（`weixin_sidecar.err.log`）

如果 8787 端口被僵尸进程占用，先执行：

- `powershell -ExecutionPolicy Bypass -File .\scripts\stop_gateway.ps1 -Force`
- `powershell -ExecutionPolicy Bypass -File .\scripts\start_gateway.ps1`
- `powershell -ExecutionPolicy Bypass -File .\scripts\weixin_stop.ps1 -Force`
- `powershell -ExecutionPolicy Bypass -File .\scripts\weixin_start.ps1`

---

## 11. 个人微信（官方 ClawBot）接入

说明：本项目采用「A 模式」接入。微信插件由本地 sidecar 运行，直接调用本地 Python gateway。

前置条件：

- 微信端已开通并启用 ClawBot 插件
- 当前目录为 `D:/project/chatgpt/oclaw`
- 已安装 Node.js（建议 22+）与 npm
- 网关可访问：`http://127.0.0.1:8787/health`

### 11.1 安装 sidecar 依赖

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\weixin_install.ps1
```

安装目录：

- `data/channel_sidecar/oclaw-weixin/`

### 11.2 扫码登录（获取 bot token）

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\weixin_login.ps1
```

登录态写入：

- `data/channel_sidecar/oclaw-weixin/state/oclaw-weixin/accounts/*.json`
- `data/channel_sidecar/oclaw-weixin/state/oclaw-weixin/accounts.json`

### 11.3 启动微信 sidecar

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\weixin_start.ps1
```

查看状态：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\weixin_status.ps1
```

停止：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\weixin_stop.ps1
```

日志文件：

- `data/channel_sidecar/oclaw-weixin/logs/weixin_sidecar.log`
- `data/channel_sidecar/oclaw-weixin/logs/weixin_sidecar.err.log`

### 11.4 当前行为说明

- 微信回复为“整段返回”，非逐 token 流式
- 发送前会清理推理/工具痕迹（如 `<redacted_thinking>...</redacted_thinking>`）
- 发送前会处理文本换行（含字面量 `\n`）

---

## 12. LLM 回放策略（reasoning / content / tool）

适用范围：`oclaw` 运行时构建“下一轮发给模型”的消息序列。

### 12.1 设计原则

- `content` 与 `reasoning` 分离：正文走 `assistant_text`，推理走独立 `reasoning` 事件。
- 默认不回放推理文本：回放只包含正文 + tool（及必要的配对字段）。
- 历史兼容：旧数据中若正文含 `<think>...</think>` 或 `<redacted_thinking>...</redacted_thinking>`，在回放构建时会剥离。

### 12.2 工具回放分层

- 最近 3 轮工具调用保留全量结果。
- 更早工具结果降级为摘要（保留 `tool_call_id` 配对信息，避免网关拒绝）。
- 单条内容仍受现有超长截断限制。

### 12.3 推理签名白名单（provider 兼容）

只针对“签名元字段”而非推理文本。用于部分 provider 在工具连续调用时保持上下文连续性。

环境变量：`AIA_REPLAY_REASONING_SIGNATURE_POLICY`

- `auto`（默认）：仅在白名单 provider 路径回放签名元字段（当前包含 Gemini 路径）。
- `on`：所有模型都回放签名元字段（调试/兼容兜底）。
- `off`：完全不回放签名元字段（最严格模式）。

推荐：

- 常规生产：保持默认 `auto`。
- 若遇到特定模型 tool-loop 连续性问题：临时设为 `on` 验证，再收敛到最小白名单。

### 12.4 `.env` 最小配置示例

```bash
# 工具回放：最近 3 轮全量（默认 3，可按需调整）
AIA_REPLAY_TOOL_FULL_ROUNDS=3

# 推理签名回放策略：auto / on / off
# 生产建议 auto：仅白名单 provider 回放签名元字段
AIA_REPLAY_REASONING_SIGNATURE_POLICY=auto
```

---

## 13. memory-wiki 插件启用与排障

### 13.1 启用配置（oclaw/oclaw.json）

将 `memory-wiki` 放入启用列表，并建议把 memory slot 指向它：

```json
{
  "plugins": {
    "enabled": ["memory-wiki"],
    "slots": {
      "memory": "memory-wiki"
    },
    "entries": {
      "memory-wiki": {
        "wiki_root": "oclaw/docs/memory-system/wiki",
        "max_search_results": 20,
        "max_get_lines": 800,
        "auto": {
          "enabled": true,
          "inject": {
            "max_chars": 1800,
            "top_k": 6
          },
          "worker": {
            "enabled": true
          },
          "topic_routing": {
            "rules": [
              {
                "topic": "network",
                "keywords": ["vlan", "router", "switch", "network", "dns", "gateway"]
              },
              {
                "topic": "devops",
                "keywords": ["deploy", "k8s", "kubernetes", "docker", "ci", "ops"]
              },
              {
                "topic": "engineering",
                "keywords": ["bug", "fix", "todo", "feature", "refactor", "test"]
              }
            ]
          }
        }
      }
    }
  }
}
```

### 13.2 会话可用工具（预期）

- `wiki_status`
- `wiki_get`
- `wiki_search`
- `wiki_lint`
- `wiki_apply`

### 13.3 常见故障

- `invalid_arguments`：参数缺失或 `path` 非 `.md` / 越界到 wiki 根目录外。
- `wiki_not_found`：目标文件不存在（`wiki_get` / `wiki_apply delete`）。
- `invalid_action`：`wiki_apply` 的 `action` 仅支持 `write|append|delete`。
- `wiki_runtime_error`：运行期异常（编码、权限、IO），先检查路径权限与文件占用。

### 13.4 回退方案

- 临时禁用 wiki 插件：从 `plugins.enabled` 移除 `memory-wiki` 后重启 gateway。
- 或仅关闭 memory slot：`plugins.slots.memory` 设为 `"none"`（保留插件安装但不作为 memory 槽位）。

### 13.5 自动化链路自检（smoke test）

在 `gateway + wiki worker` 运行时，执行：

```powershell
python .\scripts\wiki_auto_smoke_test.py
```

该脚本会：

- 投递一条 `wiki_capture` 任务到 `oclaw_task`
- 轮询任务状态直到 `done/failed/timeout`
- 输出当前写入产物状态（`merged-turns.md`、`topic-index.json`、`index.json`、`LINT_REPORT.md`）

---

