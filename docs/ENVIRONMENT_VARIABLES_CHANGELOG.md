# 环境变量变更台账（AIA）

用于记录每次版本发布中的环境变量变更，便于升级与回滚评估。

## 使用规则

- 每次发布前后都要补一条记录（即使“无变更”也要写）。
- 记录粒度：
  - 新增变量
  - 删除变量
  - 重命名（含兼容窗口）
  - 默认值变化
  - 语义变化（同名但行为变了）
- 变更后必须同步：
  - `oclaw/docs/ENVIRONMENT_VARIABLES.md`
  - `README.md` 示例
  - 示例 env 文件（如 `data/mcp_local.env.example`）

---

## 模板

```md
## YYYY-MM-DD / vX.Y.Z

### Added
- `AIA_XXX`
  - 默认值：
  - 用途：
  - 影响模块：

### Changed
- `AIA_YYY`
  - 变更前：
  - 变更后：
  - 影响：
  - 是否需要重启：是/否

### Deprecated
- `AIA_ZZZ`
  - 弃用原因：
  - 兼容截止版本：
  - 替代变量：

### Removed
- `AIA_OLD`
  - 删除原因：
  - 升级动作：

### Migration Checklist
- [ ] 已更新 `oclaw/docs/ENVIRONMENT_VARIABLES.md`
- [ ] 已更新 `README.md`
- [ ] 已更新示例 env 文件
- [ ] 已验证 Admin 配置页（如适用）
- [ ] 已执行编译/测试回归
```

---

## 2026-05-10 / Unreleased

### Added
- `AIA_IMAGE_EXPERT_API_KEY`、`AIA_IMAGE_EXPERT_BASE_URL`、`AIA_IMAGE_EXPERT_MODEL`、`AIA_IMAGE_EXPERT_CHAT_ENDPOINT`：图片专家（`send_legacy_image_messages`）专线，与 **`AIA_OCR_*`** 互不继承。
- `AIA_IMAGE_EXPERT_REQUEST_EXTRA`：图片专家顶层 JSON；旧名 **`AIA_LEGACY_IMAGE_REQUEST_EXTRA`** 仍作别名可读。
- `DASHSCOPE_IMAGE_*`（零散变量）：由 `image_legacy_client` 映射为请求体顶层字段。
- **`AIA_OCR_*`**（四项）：仅存 **`query_image_attachment` / OCR 降级** 链路；已与图片专家链路拆分。
- `AIA_MCP_ENV_ALLOWLIST_EXTRA`（兼容 `OPS_MCP_ENV_ALLOWLIST_EXTRA`）：在默认主表或 `AIA_MCP_ENV_ALLOWLIST` 替换表之后追加 MCP 子进程可透传的变量名，合并去重，避免为单个 MCP 手抄整份默认名单。
- 内置 MCP 环境透传默认名单增加 `TRILIUM_API_URL`、`TRILIUM_API_TOKEN`、`PERMISSIONS`、`VERBOSE`（[triliumnext-mcp](https://github.com/tan-yong-sheng/triliumnext-mcp)）。

### Changed
- `mcp_env.mcp_env_allowlist_keys()`：除「`AIA_MCP_ENV_ALLOWLIST` 非空则整表替换内置默认」外，`EXTRA` 始终追加到当前主表之后。
- `send_ocr_image_messages` 未配 `AIA_OCR_MODEL`（且未传 `model`）失败；图片专家 **`send_legacy_image_messages`** 首选 **用户所选会话/专家绑定的模型的 `model`/`base_url`/`api_key`**，缺省时再回落 **`AIA_IMAGE_EXPERT_*`**（不读取 `AIA_OCR_*`）；服务端若模型不支持看图则直接报错，不做备用 payload。

### Removed（OCR 通道）
- `AIA_IMAGE_BASE_URL` / `AIA_IMAGE_API_KEY` / `AIA_IMAGE_MODEL` / `AIA_IMAGE_CHAT_ENDPOINT` **不再**作为看图/OCR 通道的环境变量读取（须改用 `AIA_OCR_*`）。与附件回放相关的 `AIA_IMAGE_TOOL_RESULT_REPLAY_CAP_CHARS` 等 **不受影响**。
- 先前文档中的 `AIA_IMAGE_RETRIES` 等重试变量 **从未**由当前 OCR/legacy 客户端使用，示例 env 中已去除占位。

---

## 2026-04-26 / Unreleased

### Added
- `AIA_IMAGE_TOOL_RESULT_REPLAY_CAP_CHARS`
  - 默认值：`4000`
  - 用途：限制历史轮次中 `query_image_attachment`（OCR/描述）结果回放到模型上下文时的字符上限
  - 影响模块：`oclaw/runtime/direct_loop.py`, `oclaw/interfaces/admin/chat_api.py`, `oclaw/interfaces/admin/static/app.js`
- `AIA_VIDEO_TOOL_RESULT_REPLAY_CAP_CHARS`
  - 默认值：`4000`
  - 用途：限制历史轮次中 `query_video_attachment`（`task=transcript`）结果回放到模型上下文时的字符上限
  - 影响模块：`oclaw/runtime/direct_loop.py`, `oclaw/interfaces/admin/chat_api.py`, `oclaw/interfaces/admin/static/app.js`

### Changed
- Admin「附件」设置页新增 `image_result_replay_cap_chars` 可视化配置，并写入 `oclaw.json`：
  - 路径：`plugins.entries.memory-wiki.auto.attachments.tabular.image_result_replay_cap_chars`
  - 范围：`600..30000`
  - 是否需要重启：否（新 turn 读取时生效）
- Admin「附件」设置页新增视频相关配置，并写入 `oclaw.json`：
  - `video_result_replay_cap_chars`（范围 `600..30000`）
  - `video_transcript_chunk_size`（范围 `1..8000`）
  - `video_transcript_chunk_overlap`（范围 `1..4000`）
  - 路径：`plugins.entries.memory-wiki.auto.attachments.tabular`
  - 是否需要重启：否（新 turn 读取时生效）
- Admin「附件」设置页新增压缩包统一预算配置，并写入 `oclaw.json`：
  - `archive_max_depth`（默认 `2`）
  - `archive_max_file_count`（默认 `200`）
  - `archive_max_entry_bytes`（默认 `10485760`）
  - `archive_max_total_uncompressed_bytes`（默认 `52428800`）
  - 统一错误码：`archive_unsupported_format`, `archive_path_traversal`, `archive_max_depth_exceeded`, `archive_max_file_count_exceeded`, `archive_max_entry_bytes_exceeded`, `archive_max_total_uncompressed_bytes_exceeded`, `archive_link_entry_forbidden`, `archive_special_entry_forbidden`, `archive_parse_failed`
  - 路径：`plugins.entries.memory-wiki.auto.attachments.tabular`
  - 影响模块：`oclaw/platform/files/archive_processor.py`, `oclaw/platform/files/file_attachments.py`
  - 是否需要重启：否（新 turn 读取时生效）

### Migration Checklist
- [x] 已更新 `oclaw/docs/ENVIRONMENT_VARIABLES.md`
- [x] 已更新 `README.md`
- [x] 已更新示例 env 文件
- [x] 已验证 Admin 配置页（如适用）
- [x] 已执行编译/测试回归

---

## 2026-04-21 / Unreleased

### Added
- `AIA_PROMPT_FRONTMATTER_STRICT`（默认 `0`）：强制 YAML frontmatter。
- `AIA_SKILLS_PROMPT_IN_SYSTEM`（默认 `1`）：oclaw 风格 `<available_skills>` 注入 system prompt。
- `AIA_SKILLS_PROMPT_MAX_CHARS`（默认 `18000`）：技能目录块字符预算。
- 依赖：`PyYAML`（`requirements.txt`）。

### Changed
- `runtime/prompt_templates/loader.py` 与 `runtime/skills.py` 统一使用 YAML 解析 frontmatter（失败时默认回落旧行解析，除非开启 STRICT）。（历史：`oclaw/prompts/` 已迁至 `runtime/workspaces/_system/` + `runtime/prompt_templates/`。）

---

## 2026-04-19 / Unreleased

### Added
- `oclaw/docs/ENVIRONMENT_VARIABLES.md`（变量总览基线文档）
- `oclaw/docs/ENVIRONMENT_VARIABLES_CHANGELOG.md`（本台账）
- OpenAI 兼容 replay 相关（见 `oclaw/docs/ENVIRONMENT_VARIABLES.md`「LLM 传输与 replay」）：
  - `AIA_REPLAY_POLICY_ENABLED`（默认 `1`）
  - `AIA_REPLAY_REPAIR_TOOL_PAIRING`（默认 `1`）
  - `AIA_TOOL_CALL_ID_MAX_LEN`（默认 `40`）
  - `AIA_PROMPT_TOOL_FALLBACK`（默认 `1`）
  - `oclaw/platform/llm/OCLAW_MIT_LICENSE.txt`（oclaw 启发实现之 MIT 署名）

### Changed
- 变量前缀统一为 `AIA_*`，项目内不再使用 `OPS_*` / `AI_OPS_*`。
- `README.md` 与 `data/mcp_local.env.example` 示例变量已同步为 `AIA_*`。
- 环境变量维护流程已文档化：后续变量改动需同时更新
  - `oclaw/docs/ENVIRONMENT_VARIABLES.md`（当前生效基线）
  - `oclaw/docs/ENVIRONMENT_VARIABLES_CHANGELOG.md`（版本变更历史）
  - `README.md` / 示例 env（用户可见配置入口）

### Removed
- 代码中的 `OPS_*` / `AI_OPS_*` 引用（已清理完成）。

### Migration Checklist
- [x] 已更新 `oclaw/docs/ENVIRONMENT_VARIABLES.md`
- [x] 已更新 `README.md`
- [x] 已更新示例 env 文件
- [x] 已验证 Admin 配置页（如适用）
- [x] 已执行编译/测试回归

---

## 2026-04-20 / Unreleased

### Added
- `AIA_OCLAW_ALLOW_LEGACY_FALLBACK`
  - 默认值：`0`
  - 用途：oclaw runtime 失败时是否允许回退到 legacy `run_turn`
  - 影响模块：`oclaw/oclaw_runtime/gateway.py`, `oclaw/runtime/agents/specialist_agent.py`

### Changed
- `AIA_TURN_MAX_*`（tool workers/rounds/context）
  - 变更前：由 legacy turn runner 读取（历史文件名可能为 `agent_core.py`）
  - 变更后：由 oclaw runtime 读取并生效（`oclaw/oclaw_runtime/gateway.py`）
  - 是否需要重启：是（读取自 settings/db/env 的时机取决于运行方式）

### Deprecated
- `AIA_MANAGER_DECISION_MODE`, `AIA_TOOL_ENFORCED_RETRY_MODE`, `AIA_TOOL_LOOP_STATE_MACHINE`, `AIA_TOOL_SIGNATURE_BUDGET`, `AIA_DISABLE_TOOL_CONFIRM`
  - 弃用原因：oclaw runtime 已断开 legacy manager/runner/tool-policy 链路（代码保留，默认不生效）
  - 兼容截止版本：待定
  - 替代变量：无（后续如需恢复 legacy 将重新定义接入点）

### Migration Checklist
- [x] 已更新 `oclaw/docs/ENVIRONMENT_VARIABLES.md`
- [x] 已更新 `README.md`
- [x] 已更新示例 env 文件
- [x] 已验证 Admin 配置页（如适用）
- [x] 已执行编译/测试回归

---

## 2026-04-20 / Unreleased (oclaw MVP 补齐)

### Changed
- 无新增环境变量；oclaw runtime 在现有变量下补齐了 memory stage、router sync/async 分流、sqlite task queue、worker 执行链路。
  - 影响模块：`oclaw/oclaw_runtime/gateway.py`, `oclaw/oclaw_runtime/direct_loop.py`, `oclaw/oclaw_runtime/router.py`, `oclaw/oclaw_runtime/worker.py`, `oclaw/platform/persistence/sqlite_store.py`
  - 是否需要重启：是（升级代码后建议重启进程以启动 worker 与新路由逻辑）

### Migration Checklist
- [x] 已更新 `oclaw/docs/ENVIRONMENT_VARIABLES.md`
- [x] 已更新 `README.md`
- [x] 已更新示例 env 文件
- [x] 已验证 Admin 配置页（如适用）
- [ ] 已执行编译/测试回归

---

## 2026-04-20 / Unreleased (AgentCore Retry Matrix)

### Added
- `AIA_OCLAW_RETRYABLE_ERROR_CODES`
  - 默认值：`provider_timeout,provider_rate_limited,provider_temporary_error,provider_unavailable,context_overflow,tool_execution_failed`
  - 用途：控制 Agent Core run 外环可重试错误白名单
  - 影响模块：`oclaw/oclaw_runtime/agent_core_run.py`, `oclaw/interfaces/admin/routes.py`, `oclaw/interfaces/admin/static/app.js`

### Changed
- Agent Core 重试策略从“status=retry 即重试”升级为“retry + error_code 命中白名单才重试”。
  - 是否需要重启：是（新策略读取设置后在进程内生效）

### Migration Checklist
- [x] 已更新 `oclaw/docs/ENVIRONMENT_VARIABLES.md`
- [x] 已更新 `README.md`
- [x] 已更新示例 env 文件
- [x] 已验证 Admin 配置页（如适用）
- [x] 已执行编译/测试回归

### Changed
- `AIA_OCLAW_RETRYABLE_ERROR_CODES` 已接入 Admin「Tool Policy」页读写链路。
  - 影响模块：`oclaw/interfaces/admin/routes.py`, `oclaw/interfaces/admin/static/app.js`
- `AIA_OCLAW_RETRYABLE_ERROR_CODES` 保存时增加未知 code 过滤与告警返回（`unknown_retryable_error_codes`）。
  - 影响模块：`oclaw/interfaces/admin/routes.py`, `oclaw/interfaces/admin/static/app.js`, `oclaw/oclaw_runtime/agent_core_run.py`
- `AIA_OCLAW_RETRYABLE_ERROR_CODES` 新增严格模式：可配置为未知 code 直接拒绝保存（400）。
  - 影响模块：`oclaw/interfaces/admin/routes.py`, `oclaw/interfaces/admin/static/app.js`

### Added
- `AIA_OCLAW_RETRY_CODES_STRICT_MODE`
  - 默认值：`0`
  - 用途：控制 Admin 保存 retry code 时对未知值的处理（过滤告警 / 拒绝）
  - 影响模块：`oclaw/interfaces/admin/routes.py`, `oclaw/interfaces/admin/static/app.js`
