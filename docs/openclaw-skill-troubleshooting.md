# oclaw Skill 排障手册

本文用于排查 oclaw skill 在安装、暴露、执行、记忆回写四个阶段的问题。

## 1) 安装接口返回字段

`/admin/api/skills/install*`、`/admin/api/skills/auto-install`、`/admin/api/skills/retry-install` 统一返回：

- `ok`: 是否成功
- `result.detail`: 原始细节文本
- `result.error_code`: 归一化错误码
- `result.retryable`: 是否建议重试

## 2) 常见 `error_code` 与处理建议

| `error_code` | 含义 | `retryable` | 建议 |
| --- | --- | --- | --- |
| `ok` | 安装/创建成功 | `false` | 无 |
| `transport_or_extract_error` | 下载失败或解压异常 | `true` | 检查网络、URL、压缩包完整性后重试 |
| `invalid_archive` | 压缩包不合法（空包/过大/类型不支持） | `false` | 修正包格式或来源 |
| `invalid_skill_package` | 缺 `SKILL.md` 或包含不安全路径/文件 | `false` | 修正技能包结构和内容 |
| `already_exists` | 目标技能目录已存在 | `false` | 使用 overwrite 或换名 |
| `runtime_error` | 自动安装中途异常并已回滚 | `true` | 看 detail 定位异常后重试 |
| `unknown` | 未归类错误 | `false` | 结合 detail 和 trace 排查 |

## 3) 按 `trace_id` 排障路径

推荐按下列顺序查询同一个 `trace_id`：

1. `openclaw_gateway`
   - `skill_manifest`
   - `router_decision`
2. `openclaw_agent_core`
   - `run_started`
   - `attempt_started`
3. `openclaw_direct_loop`
   - `tool_wire_filter`
   - `tool_result_context_guard`
4. `openclaw_skill_executor`
   - `skill_selected`
   - `skill_executed`
5. `openclaw_agent_core`
   - `after_turn_memory`
   - `attempt_finished`
   - `run_finished`

可快速判断问题落在哪一段：安装未生效、工具未暴露、工具执行失败、结果被截断、记忆未写入。

## 4) 快速检查项

- `AIA_SKILL_RUNTIME_ENABLED` 是否开启
- `AIA_SKILLS_PROMPT_IN_SYSTEM` 是否开启
- `AIA_SKILL_DISABLED_NAMES` 是否误禁用了目标 skill
- `AIA_SKILL_AUTO_INSTALL_ENABLED` 是否关闭
- 目标 skill 的 `SKILL.md` 是否包含合法 frontmatter（尤其 `metadata.openclaw.install`）

## 5) 典型故障定位

- **症状：skill 在 prompt 中看不到**
  - 查 `skill_manifest.skills_total` 与 `hidden_total`
  - 查 `AIA_SKILL_DISABLED_NAMES`
  - 查 wire policy 是否过滤（`tool_wire_filter.hidden_*`）

- **症状：skill 可见但执行失败**
  - 查 `skill_executed.ok=false` 与 `error_code`
  - 查 `attempt_finished.error_code` 是否被归类为可重试错误

- **症状：有回复但记忆未入库**
  - 查 `after_turn_memory`
  - 若无该事件，先看 attempt 是否成功
  - 若有该事件仍无记录，检查记忆写入阈值与 writer 配置

## 6) Admin 接口字段对照（速查）

以下接口都返回统一结构：`{ ok, result: { detail, error_code, retryable } }`。

| 接口 | 用途 | 常见请求字段 | 关键返回字段 |
| --- | --- | --- | --- |
| `POST /admin/api/skills/install` | 从本地目录安装 | `source_dir`, `overwrite` | `result.error_code`, `result.retryable` |
| `POST /admin/api/skills/install-registry` | 从 registry 压缩包安装 | `archive_url`, `overwrite` | `result.error_code`, `result.retryable` |
| `POST /admin/api/skills/auto-install` | 依据描述自动安装 | `name`, `description` | `result.error_code`, `result.retryable` |
| `POST /admin/api/skills/retry-install` | 对失败记录重试安装 | `install_id` | `result.error_code`, `result.retryable` |

排障时建议优先读取：

- `result.error_code`：确定是否是包格式、下载链路、运行时异常
- `result.retryable`：决定是否直接重试，还是先改包/改配置
- `result.detail`：补充上下文（具体 URL、异常片段、回滚原因）

## 7) 值班排障最短路径

1. 在 Admin 安装结果中先看 `result.error_code` 与 `result.retryable`
2. 按 `trace_id` 检索 `skill_manifest -> skill_executed -> after_turn_memory`
3. 若 `retryable=true`，修复网络/瞬时问题后执行 `/retry-install`
4. 若 `retryable=false`，优先修正技能包内容或运行时开关再重试

## 8) Relay 文件指针排障（新增）

当技能/专家输出文件引用时，优先检查：

- 入站消息 `attachments[]` 是否包含 `type=relay_pointer` 与 `pointer_uri`
- `metadata.relay_share_envelope.attachments.pointers[]` 是否存在且数量匹配
- `gateway_received` trace 中：
  - `relay_pointer_count`
  - `relay_envelope_present`
  - `relay_envelope_pointer_count`

常见问题：

- **有附件但 pointer 计数为 0**
  - 附件对象缺少 `pointer_uri`，或字段名不符合协议
- **envelope 存在但 pointer 数量为 0**
  - `relay_share_envelope.attachments.pointers` 结构错误（非数组/元素非对象）
- **LLM 无法使用共享文件**
  - 确认消息构建阶段将 pointer 作为文本元信息注入，而不是直接传大文件内容

- **ACP 子任务立即失败（无模型执行）**
  - 常见 `error_code`：`relay_envelope_invalid`、`relay_envelope_unsupported_version`
  - 语义：输入契约错误，固定 `retryable=false`，应先修 payload 再重试
