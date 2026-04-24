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

## 2026-04-21 / Unreleased

### Added
- `AIA_PROMPT_FRONTMATTER_STRICT`（默认 `0`）：强制 YAML frontmatter。
- `AIA_SKILLS_PROMPT_IN_SYSTEM`（默认 `1`）：oclaw 风格 `<available_skills>` 注入 system prompt。
- `AIA_SKILLS_PROMPT_MAX_CHARS`（默认 `18000`）：技能目录块字符预算。
- 依赖：`PyYAML`（`requirements.txt`）。

### Changed
- `oclaw/prompts/loader.py` 与 `oclaw/openclaw_runtime/skills.py` 统一使用 YAML 解析 frontmatter（失败时默认回落旧行解析，除非开启 STRICT）。

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
  - `oclaw/platform/llm/OPENCLAW_MIT_LICENSE.txt`（oclaw 启发实现之 MIT 署名）

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
- `AIA_OPENCLAW_ALLOW_LEGACY_FALLBACK`
  - 默认值：`0`
  - 用途：oclaw runtime 失败时是否允许回退到 legacy `run_turn`
  - 影响模块：`oclaw/openclaw_runtime/gateway.py`, `oclaw/agents/specialist_agent.py`

### Changed
- `AIA_TURN_MAX_*`（tool workers/rounds/context）
  - 变更前：由 legacy turn runner 读取（历史文件名可能为 `agent_core.py`）
  - 变更后：由 oclaw runtime 读取并生效（`oclaw/openclaw_runtime/gateway.py`）
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
  - 影响模块：`oclaw/openclaw_runtime/gateway.py`, `oclaw/openclaw_runtime/direct_loop.py`, `oclaw/openclaw_runtime/router.py`, `oclaw/openclaw_runtime/worker.py`, `oclaw/platform/persistence/sqlite_store.py`
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
- `AIA_OPENCLAW_RETRYABLE_ERROR_CODES`
  - 默认值：`provider_timeout,provider_rate_limited,provider_temporary_error,provider_unavailable,context_overflow,tool_execution_failed`
  - 用途：控制 Agent Core run 外环可重试错误白名单
  - 影响模块：`oclaw/openclaw_runtime/agent_core_run.py`, `oclaw/admin/routes.py`, `oclaw/admin/static/app.js`

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
- `AIA_OPENCLAW_RETRYABLE_ERROR_CODES` 已接入 Admin「Tool Policy」页读写链路。
  - 影响模块：`oclaw/admin/routes.py`, `oclaw/admin/static/app.js`
- `AIA_OPENCLAW_RETRYABLE_ERROR_CODES` 保存时增加未知 code 过滤与告警返回（`unknown_retryable_error_codes`）。
  - 影响模块：`oclaw/admin/routes.py`, `oclaw/admin/static/app.js`, `oclaw/openclaw_runtime/agent_core_run.py`
- `AIA_OPENCLAW_RETRYABLE_ERROR_CODES` 新增严格模式：可配置为未知 code 直接拒绝保存（400）。
  - 影响模块：`oclaw/admin/routes.py`, `oclaw/admin/static/app.js`

### Added
- `AIA_OPENCLAW_RETRY_CODES_STRICT_MODE`
  - 默认值：`0`
  - 用途：控制 Admin 保存 retry code 时对未知值的处理（过滤告警 / 拒绝）
  - 影响模块：`oclaw/admin/routes.py`, `oclaw/admin/static/app.js`
