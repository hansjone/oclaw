# 环境变量总览（AIA）

本项目统一使用 `AIA_*` 前缀环境变量。本文档是唯一维护入口，用于说明变量用途、默认值与生效位置。
发布级变更记录见：`oclaw/docs/ENVIRONMENT_VARIABLES_CHANGELOG.md`。

## 维护规则

- 新增环境变量时，必须同步更新本文档。
- 变量命名统一：`AIA_<模块>_<含义>`。
- 若变量已可在 Admin 配置，优先使用 Admin，环境变量作为启动默认值/兜底。
- 删除变量时，请同时更新：
  - 本文档
  - `README.md` 的示例
  - 示例环境文件（如 `data/mcp_local.env.example`）

## 核心与调度

- `AIA_ASSISTANT_MODE`
  - 默认：空（代码内决定默认模式）
  - 作用：助手模式选择
  - 生效：`oclaw/platform/llm/chat_models.py`, `oclaw/runtime/agents/factory.py`

- `AIA_MANAGER_DECISION_MODE`
  - 默认：空
  - 作用：**Legacy（已断开）**：旧 manager 决策模式（如 `rule`）
  - 说明：oclaw runtime 默认不再走 `CompositeOpsAgent` 的 manager 决策；该变量仅保留以便后续接回 legacy
  - 生效：`oclaw/runtime/agents/manager_agent.py`（仅 legacy 链路）

- `AIA_TURN_MAX_TOOL_WORKERS`
  - 默认：`8`
  - 作用：单轮工具并发上限
  - 生效：`oclaw/oclaw_runtime/gateway.py`, `oclaw/oclaw_runtime/direct_loop.py`

- `AIA_TURN_MAX_TOOL_ROUNDS`
  - 默认：`8`
  - 作用：工具循环轮次上限
  - 生效：`oclaw/oclaw_runtime/gateway.py`, `oclaw/oclaw_runtime/direct_loop.py`

- `AIA_TURN_MAX_CONTEXT_MESSAGES`
  - 默认：`80`
  - 作用：上下文消息上限
  - 生效：`oclaw/oclaw_runtime/gateway.py`, `oclaw/oclaw_runtime/direct_loop.py`

- oclaw async queue/worker（`router -> oclaw_task -> worker`）
  - 当前版本无独立环境变量；复用以上 `AIA_TURN_MAX_*` 配置控制 direct loop 执行上限
  - 生效：`oclaw/oclaw_runtime/gateway.py`, `oclaw/oclaw_runtime/worker.py`

- `AIA_PROMPT_FRONTMATTER_STRICT`
  - 默认：`0`
  - 作用：`1` 时 `SKILL.md` / `runtime/workspaces/_system/**/*.md` 的 frontmatter 必须为可解析 YAML；解析失败直接报错（不回落旧版行解析）
  - 生效：`oclaw/runtime/prompt_templates/frontmatter.py`, `oclaw/runtime/prompt_templates/loader.py`, `oclaw/runtime/skills.py`

- `AIA_SKILLS_PROMPT_IN_SYSTEM`
  - 默认：`1`（开启；仅当技能运行时启用）
  - 作用：是否在 system prompt 末尾附加 oclaw 风格的 `<available_skills>` 目录块（与原生 `tools` 并存）
  - 说明：设为 `0` 可关闭以降低 token；Admin `AIA_SKILL_RUNTIME_ENABLED` 关闭时本块不生成
  - 生效：`oclaw/oclaw_runtime/skills_prompt.py`, `oclaw/oclaw_runtime/direct_loop.py`

- `AIA_SKILLS_PROMPT_MAX_CHARS`
  - 默认：`18000`
  - 作用：技能目录 XML 块最大字符数（超出则从列表尾部丢弃条目）
  - 生效：`oclaw/oclaw_runtime/skills_prompt.py`

- `AIA_SKILL_DISABLED_NAMES`
  - 默认：空数组（`[]`）
  - 作用：按技能名禁用模型可见/可执行技能（JSON 数组字符串，例如 `["skill_a","skill_b"]`）
  - 说明：禁用后同时影响 manifest/prompt 渲染与 direct loop 工具暴露
  - 生效：`oclaw/oclaw_runtime/skills.py`, `oclaw/oclaw_runtime/skills_prompt.py`, `oclaw/oclaw_runtime/skill_installer.py`

- `AIA_SKILL_AUTO_INSTALL_ENABLED`
  - 默认：`1`
  - 作用：是否允许自动安装 skill（admin auto-install / retry-install(auto)）
  - 说明：关闭后返回 `auto_install_disabled`，并标记为不可重试
  - 生效：`oclaw/oclaw_runtime/skill_installer.py`, `oclaw/interfaces/admin/skills_api.py`

- `AIA_OCLAW_RETRYABLE_ERROR_CODES`
  - 默认：`provider_timeout,provider_rate_limited,provider_temporary_error,provider_unavailable,context_overflow,tool_execution_failed`
  - 作用：Agent Core run 外环的错误重试白名单（逗号分隔）
  - 说明：仅当 attempt 返回 `status=retry` 且 `error_code` 命中该白名单时才进入下一次 attempt；未知 code 默认在 Admin 保存时会被过滤并告警
  - 补充：`relay_envelope_invalid`、`relay_envelope_unsupported_version` 属于输入契约错误，运行时固定按 non-retryable 处理（即使被误加入白名单也不会进入重试链）
  - 生效：`oclaw/oclaw_runtime/agent_core_run.py`

- `AIA_OCLAW_ROUTER_MODE`
  - 默认：`rule`
  - 取值：`rule`（启发式）或 `llm_json`（由当前 executor 的 `model.chat` 产出 `{mode,reason}` JSON；解析失败则回落 `rule`）
  - 说明：亦可通过同名环境变量覆盖；提示词见 `runtime/workspaces/_system/router/decide_route.md`
  - 生效：`oclaw/oclaw_runtime/router.py`, `oclaw/oclaw_runtime/gateway.py`

- oclaw trace 字段与 `event_type` ↔ `oc_stage` 对照见 `oclaw/docs/oclaw-trace-taxonomy.md`
- Skill 安装错误码与重试建议、trace 排障路径见 `oclaw/docs/oclaw-skill-troubleshooting.md`
- Relay 文件指针（含 ACP 父子 run）错误码与排障见 `oclaw/docs/oclaw-skill-troubleshooting.md` 的“Relay 文件指针排障”

- `AIA_OCLAW_RETRY_CODES_STRICT_MODE`
  - 默认：`0`
  - 作用：控制 Admin 保存 `AIA_OCLAW_RETRYABLE_ERROR_CODES` 时的未知 code 行为
  - 说明：`0`=过滤并告警；`1`=直接拒绝保存（HTTP 400）
  - 生效：`oclaw/interfaces/admin/routes.py`, `oclaw/interfaces/admin/static/app.js`

- `AIA_TOOL_ENFORCED_RETRY_MODE`
  - 默认：`first_round_only`
  - 作用：**Legacy（已断开）**：工具必需场景下的强制重试策略
  - 生效：仅 legacy 链路（保留占位，暂不影响 oclaw）

- `AIA_TOOL_LOOP_STATE_MACHINE`
  - 默认：`1`
  - 作用：**Legacy（已断开）**：工具循环状态机开关
  - 生效：仅 legacy 链路（保留占位，暂不影响 oclaw）

- `AIA_TOOL_SIGNATURE_BUDGET`
  - 默认：`2`
  - 作用：**Legacy（已断开）**：同签名工具调用预算
  - 生效：仅 legacy 链路（保留占位，暂不影响 oclaw）

- `AIA_OCLAW_ALLOW_LEGACY_FALLBACK`
  - 默认：`0`（关闭）
  - 作用：oclaw 执行失败时，是否允许回退到 legacy `executor.run_turn(...)`
  - 说明：默认 fail-closed（不回退），避免无意中触发旧 manager/runner
  - 生效：`oclaw/oclaw_runtime/gateway.py`, `oclaw/runtime/agents/specialist_agent.py`

## LLM 传输与 replay（OpenAI 兼容）

思路参考 oclaw（MIT）对 `openai-completions` 的 transcript 策略：在请求前修复/规范化 `tool_calls[].id` 与 `role=tool` 的 `tool_call_id`，减少网关 400（空 id、断链、非法字符）。

- `AIA_REPLAY_POLICY_ENABLED`
  - 默认：`1`（启用）
  - 作用：是否启用发送前 replay 规范化（修复孤儿 tool 引用 + 重写 tool id）
  - 生效：`oclaw/platform/llm/replay_policy.py`, `oclaw/platform/llm/chat_models.py`

- `AIA_REPLAY_REPAIR_TOOL_PAIRING`
  - 默认：`1`
  - 作用：是否先剥离「assistant 中不存在的 tool_call_id」的 tool 消息上的 id（再执行 id 重写）
  - 生效：`oclaw/platform/llm/replay_policy.py`

- `AIA_TOOL_CALL_ID_MAX_LEN`
  - 默认：`40`
  - 作用：重写后的 tool_call_id 最大长度（适配多数 OpenAI 兼容网关）
  - 生效：`oclaw/platform/llm/tool_call_id.py`

- `AIA_PROMPT_TOOL_FALLBACK`
  - 默认：`1`
  - 作用：原生 tools 失败并进入 prompt-tool 降级时，是否向 system 注入 tools JSON；设为 `0` 则仅剥离 tool 结构、不注入工具清单
  - 生效：`oclaw/platform/llm/chat_models.py`

- `AIA_NATIVE_TOOLS_DENYLIST_HOSTS`
  - 默认：空（无静态名单；另有进程内按错误动态记录的 `(host, model)` 缓存）
  - 作用：可选的 host 子串黑名单，强制走 prompt-tool 模式
  - 生效：`oclaw/platform/llm/chat_models.py`

- `AIA_TOOL_FUNCTION_STRICT`
  - 默认：未设置即 **开启**（在发往 OpenAI 兼容 **`/chat/completions`** 的请求里，为每个 **`tools[].function`** 写入 **`strict: true`**）
  - 作用：设为 `0` / `false` / `no` / `off`（大小写不敏感）时关闭，避免少数网关因未知字段校验失败返回 400
  - 说明：与具体模型无关；若使用 DeepSeek 文档中的 **strict（Beta）工具模式**，还需 **`/beta`** base URL 与符合规范的 JSON Schema，参见 [DeepSeek Tool Calls](https://api-docs.deepseek.com/zh-cn/guides/tool_calls)
  - 示例：`_local/system.env.example`
  - 生效：`svc/llm/transports/openai_chat_completions.py`

## 工具执行与安全

- `AIA_DISABLE_TOOL_CONFIRM`
  - 默认：`0`
  - 作用：**Legacy（已断开）**：是否禁用高风险工具确认
  - 说明：oclaw 工具执行已移除执行时确认策略；该变量保留以便后续接回 legacy
  - 生效：仅 legacy 链路（保留占位）

- `AIA_ENABLE_MCP_TOOLS`
  - 默认：`1`
  - 作用：启用 MCP 工具
  - 生效：`oclaw/tools/catalog.py`

- `AIA_ENABLE_PLUGIN_TOOLS`
  - 默认：`0`
  - 作用：启用插件工具
  - 生效：`oclaw/tools/catalog.py`

- `AIA_ENABLE_RUN_COMMAND`
  - 默认：`0`
  - 作用：允许高风险 `run_command` 工具
  - 生效：`oclaw/tools/catalog.py`, `oclaw/tools/experts/workspace/shell_tools.py`

- `AIA_TOOL_LLM_MESSAGE_MAX_CHARS`
  - 默认：`0`（不限制）
  - 作用：工具结果写回 LLM 的消息长度上限
  - 说明：`0` 表示不做限制（不推荐，可能触发部分网关的单条消息上限 400）
  - 生效：`oclaw/runtime/chat/tool_runtime.py`
  - 观测：管理端聊天流 `tool_use_result` 事件会携带 `llm_wire.{truncated_for_llm,max_chars,result_bytes,result_for_llm_bytes,truncate_ms}`

- `AIA_TOOL_LOG_MAX_CHARS`
  - 默认：`200000`
  - 作用：`tool_log` 中 args/result 截断上限
  - 生效：`oclaw/platform/persistence/sqlite_store.py`

- `AIA_MAX_ATTACHMENT_BYTES`
  - 默认：`26214400`（25MB）
  - 作用：工具结果/MCP payload 中嵌入式 base64 内容落盘为 `attachment_id` 时的单附件最大字节数（超限则不落盘，降级为 `*_ref` 元信息并标记 `attachment_too_large`）
  - 取值：`0` 表示不限制（不推荐）
  - 生效：`oclaw/runtime/chat/media_redact.py`

- `AIA_ATTACHMENT_ACL_STRICT`
  - 默认：`0`
  - 作用：附件下载鉴权是否严格依赖 `attachment_acl`
  - 说明：
    - `0`：优先走 `attachment_acl`，缺失时仍允许回退扫描历史 `chat_message.attachments`（兼容旧数据）
    - `1`：**严格模式**，只允许 `attachment_acl`（以及用户头像 `avatar_attachment_id`）命中的附件被下载
  - 上线建议：先执行 Admin “ACL 回填”，再开启 strict
  - 生效：`oclaw/interfaces/admin/chat_api.py`

- `AIA_IMAGE_TOOL_RESULT_REPLAY_CAP_CHARS`
  - 默认：`4000`
  - 作用：限制历史轮次中 `query_image_attachment`（OCR/描述）结果回放到模型上下文时的 `text` 长度上限
  - 范围：`600..30000`
  - 优先级：DB setting（同名） > 环境变量 > `oclaw.json`(`plugins.entries.memory-wiki.auto.attachments.tabular.image_result_replay_cap_chars`) > 默认值
  - 生效：`oclaw/runtime/direct_loop.py`

- `AIA_VIDEO_TOOL_RESULT_REPLAY_CAP_CHARS`
  - 默认：`4000`
  - 作用：限制历史轮次中 `query_video_attachment`（`task=transcript`）结果回放到模型上下文时的 `text` 长度上限
  - 范围：`600..30000`
  - 优先级：DB setting（同名） > 环境变量 > `oclaw.json`(`plugins.entries.memory-wiki.auto.attachments.tabular.video_result_replay_cap_chars`) > 默认值
  - 生效：`oclaw/runtime/direct_loop.py`

- `video_transcript_chunk_size` / `video_transcript_chunk_overlap`（`oclaw.json` 配置项）
  - 默认：`1600` / `200`
  - 作用：`query_video_attachment(task=transcript)` 落库转写文本时的默认分块参数（可被工具入参覆盖）
  - 范围：`size: 1..8000`，`overlap: 1..4000`（实际使用会约束 overlap < size）
  - 路径：`plugins.entries.memory-wiki.auto.attachments.tabular`
  - 生效：`oclaw/runtime/tools/experts/generalist/video_query.py`

- `archive_max_depth` / `archive_max_file_count` / `archive_max_entry_bytes` / `archive_max_total_uncompressed_bytes`（`oclaw.json` 配置项）
  - 默认：`2` / `200` / `10485760` / `52428800`
  - 作用：统一 `archive_processor`（zip/tar/tgz/gz）安全预算：限制嵌套深度、文件数量、单文件解压大小、总解压大小
  - 路径：`plugins.entries.memory-wiki.auto.attachments.tabular`
  - 生效：`oclaw/platform/files/archive_processor.py`, `oclaw/platform/files/file_attachments.py`
  - 错误码（工具/上下文可见）：`archive_unsupported_format`, `archive_path_traversal`, `archive_max_depth_exceeded`, `archive_max_file_count_exceeded`, `archive_max_entry_bytes_exceeded`, `archive_max_total_uncompressed_bytes_exceeded`, `archive_link_entry_forbidden`, `archive_special_entry_forbidden`, `archive_parse_failed`

## MCP 与工具线侧

- `AIA_MCP_SPECIALISTS`
  - 默认：`generalist`
  - 作用：允许使用 MCP 的 specialist 列表
  - 生效：`oclaw/tools/mcp/adapter.py`

- `AIA_MCP_ENV_ALLOWLIST`
  - 默认：未设置时使用内置补充名单（仅用于**未**出现在 `mcp_local.env` 里、但要从宿主环境透传的变量名，见 `mcp_env._DEFAULT_ALLOWLIST`）
  - 作用：**`oclaw/_local/mcp_local.env`（及合并路径）里声明且非空的键**会由 `McpProcessRuntime` 直接传入 MCP，与本项无关；若**非空**设置本项，则整表替换该「补充」默认（不影響 mcp_local 文件中的键）
  - 生效：`oclaw/runtime/operations/mcp_env.py`、`oclaw/runtime/tools/mcp/runtime.py`

- `AIA_MCP_ENV_ALLOWLIST_EXTRA`（兼容 `OPS_MCP_ENV_ALLOWLIST_EXTRA`）
  - 默认：空
  - 作用：在「补充主列表」（内置默认，或 `AIA_MCP_ENV_ALLOWLIST` 替换后的列表）之后追加变量名，合并去重；适用于密钥只写在 Docker `-e` / 系统环境、不进 `mcp_local.env` 的情况
  - 生效：`oclaw/runtime/operations/mcp_env.py`

- `AIA_MCP_FILESYSTEM_EXTRA_ROOTS`
  - 默认：空
  - 作用：追加给 filesystem MCP 的根目录
  - 生效：`oclaw/tools/mcp/filesystem_argv.py`

- `AIA_MCP_WIRE_USAGE_POLICY`
  - 默认：空（按 base_url 继承）
  - 作用：是否启用 MCP 工具线侧分层策略
  - 生效：`oclaw/platform/llm/tool_wire_policy.py`

- `AIA_MCP_WIRE_PENALTY_DISABLE`
  - 默认：`0`
  - 作用：禁用线侧陈旧惩罚
  - 生效：`oclaw/platform/llm/tool_wire_policy.py`

- `AIA_MCP_WIRE_TOP_N_FULL`
  - 默认：`20`
  - 作用：全量上送工具数量
  - 生效：`oclaw/platform/llm/tool_wire_policy.py`

- `AIA_MCP_WIRE_STALE_HOURS`
  - 默认：`3`
  - 作用：陈旧判定小时阈值
  - 生效：`oclaw/platform/llm/tool_wire_policy.py`

- `AIA_MCP_WIRE_PENALTY_MINUTES`
  - 默认：`30`
  - 作用：惩罚窗口分钟数
  - 生效：`oclaw/platform/llm/tool_wire_policy.py`

- `AIA_MCP_WIRE_MEDIUM_RANK_START`
  - 默认：`21`
  - 作用：中等层起始排名
  - 生效：`oclaw/platform/llm/tool_wire_policy.py`

- `AIA_MCP_WIRE_MEDIUM_RANK_END`
  - 默认：`50`
  - 作用：中等层结束排名
  - 生效：`oclaw/platform/llm/tool_wire_policy.py`

- `AIA_MCP_WIRE_MEDIUM_DESC_CHARS`
  - 默认：`520`
  - 作用：中等层描述截断长度
  - 生效：`oclaw/platform/llm/tool_wire_policy.py`

- `AIA_MCP_WIRE_MINIMAL_DESC_CAP`
  - 默认：`80`
  - 作用：最小层描述长度
  - 生效：`oclaw/platform/llm/tool_wire_policy.py`

## LLM 工具载荷与模型兼容

- `AIA_OPENAI_TOOLS_MAX_JSON_CHARS`
  - 默认：空（按代码内部策略）
  - 作用：OpenAI tools payload JSON 上限
  - 生效：`oclaw/platform/llm/chat_models.py`

- `AIA_SHRINK_OPENAI_TOOLS`
  - 默认：`0`
  - 作用：强制启用 tools payload 压缩
  - 生效：`oclaw/platform/llm/chat_models.py`

- `AIA_SHRINK_OPENAI_TOOLS_MAX_JSON`
  - 默认：`28000`
  - 作用：压缩目标上限
  - 生效：`oclaw/platform/llm/chat_models.py`

- `AIA_GEMINI_OPENAI_NONSTREAM_TOOLS`
  - 默认：`0`
  - 作用：Gemini OpenAI 兼容下 tools 非流式开关
  - 生效：`oclaw/platform/llm/chat_models.py`

## OCR / 看图工具与降级专线（``AIA_OCR_*``）

仅用于：**`query_image_attachment`**、OpenAI-compatible **`send_ocr_image_messages`**、以及 **`openai_chat_completions`** 在纯文本模型上的多模态→OCR 降级。规范为 OpenAI **`image_url` + `messages`** Chat Completions 形态。**与下方「图片专家」专线互相独立**（不配齐不会自动复用另一端）。

- `AIA_OCR_BASE_URL`
  - 默认：无（必填，否则工具判为未配置）
  - 作用：OCR / 看图工具网关根地址（实际请求为 `BASE_URL` + `CHAT_ENDPOINT`）
  - 生效：`oclaw/platform/llm/image_ocr_client.py`

- `AIA_OCR_API_KEY`
  - 默认：无（必填）
  - 作用：上述网关 Bearer API Key
  - 生效：`oclaw/platform/llm/image_ocr_client.py`

- `AIA_OCR_MODEL`
  - 默认：无（必填，**不提供默认模型 id**）
  - 作用：支持 OCR/描述的 vision 模型 id
  - 生效：`oclaw/platform/llm/image_ocr_client.py`

- `AIA_OCR_CHAT_ENDPOINT`
  - 默认：`/chat/completions`
  - 作用：相对 `AIA_OCR_BASE_URL` 的路径
  - 生效：`oclaw/platform/llm/image_ocr_client.py`

**动态参数：** 调用 `send_ocr_image_messages` 时传入 `base_url` / `api_key` / `model` 优先于上述环境变量；`vision_llm_backend_status` 仅检查 `AIA_OCR_*` 是否在未显式传参时可用。

---

## 图片专家专线（``AIA_IMAGE_EXPERT_*``）

**路由 specialist=`image`** 时由 **`send_legacy_image_messages`** 调用。**`compatible-mode/v1` + `/chat/completions`** 与 OpenAI 视觉接口一致：每条 `content[]` 必须含 **`type`**（默认使用 `image_url` + `text`）。若网关只吃 DashScope 无 `type` 的 `{"image"}`/`{"text}`，再设 **`AIA_IMAGE_EXPERT_COMPAT_USE_DASHSCOPE_NATIVE_BLOCKS=1`**。**不使用 `AIA_OCR_*`**。

- `AIA_IMAGE_EXPERT_COMPAT_USE_DASHSCOPE_NATIVE_BLOCKS`
  - 默认：未设置（等价关闭）
  - 作用：设为 `1` 时，在 **`compatible-mode`** Base URL 上仍发送 DashScope 文档形态（无 `type` 的 `image`/`text` 块）。仅当你的兼容网关明确支持该形态时使用；否则会遇到上游 `missing_required_parameter … content[n].type`。
  - 生效：`oclaw/platform/llm/image_legacy_client.py`

- `AIA_IMAGE_EXPERT_MAX_INPUT_IMAGES`
  - 默认：`8`（上限 `12`）
  - 作用：单轮发往模型的输入图数量上限（与 `collect_legacy_lane_images_from_attachments` / `send_legacy_image_messages` 裁剪一致）。
  - 生效：`oclaw/platform/llm/image_legacy_client.py`

- `AIA_IMAGE_SPECIALIST_SESSION_IMAGE_FALLBACK`
  - 默认：未设置（启用）
  - 作用：设为 `0` / `false` / `off` 时，**关闭** Chat 图片专家在多轮对话中「本轮无新图」时从会话历史继承图片（否则会在助手产出图与用户上传图之间回退）。关闭后与旧行为一致：无附件即提示不上图。
  - 生效：`oclaw/platform/llm/image_legacy_client.py`（经 `runtime/direct_loop.py` 的 `_maybe_image_specialist_legacy_gateway_turn` 调用）

- `AIA_IMAGE_SPECIALIST_FALLBACK_SCAN_MESSAGES`
  - 默认：`400`
  - 作用：历史回退时最多加载的最近消息条数（与 `SqliteStore.get_messages` 上限一致范围内）。
  - 生效：`oclaw/platform/llm/image_legacy_client.py`

- `AIA_IMAGE_EXPERT_BASE_URL`
  - 默认：无（必填，除非在代码中为 `send_legacy_image_messages(..., base_url=...)` 传入）
  - 作用：图片专家 HTTP 网关根路径（兼容 OpenAI multimodal 时常见 `https://dashscope.aliyuncs.com/compatible-mode/v1` 等）。
  - 生效：`oclaw/platform/llm/image_legacy_client.py`

- `AIA_IMAGE_EXPERT_API_KEY`
  - 默认：无（必填，除非显式传 `api_key`）
  - 作用：Bearer API Key（可与百炼「图片/多模态」文档中的 Key 一致；与 OCR Key **可不同**）。
  - 生效：`oclaw/platform/llm/image_legacy_client.py`

- `AIA_IMAGE_EXPERT_MODEL`
  - 默认：无（在用户界面已选会话模型时，`send_legacy_image_messages` **优先使用该模型的 `model` id**；仅当会话未带模型信息时才读本变量作补全）。
  - 作用：无 UI 会话模型/`model=` 可传时的专家默认模型 id（与 OCR 所用 VL **无需相同**）。
  - 生效：`oclaw/platform/llm/image_legacy_client.py`

- `AIA_IMAGE_EXPERT_CHAT_ENDPOINT`
  - 默认：`/chat/completions`
  - 作用：相对 `AIA_IMAGE_EXPERT_BASE_URL` 的路径。
  - 生效：`oclaw/platform/llm/image_legacy_client.py`

- `AIA_IMAGE_EXPERT_REQUEST_EXTRA`
  - 默认：无
  - 别名：`AIA_LEGACY_IMAGE_REQUEST_EXTRA`（旧名仍可读）。
  - 作用：发往图片专家请求的**顶层附加 JSON**。顶层 `model` / `messages` 仍由运行时代码覆盖。
  - 生效：`oclaw/platform/llm/image_legacy_client.py`

- `DASHSCOPE_IMAGE_STREAM` / `DASHSCOPE_IMAGE_N` / `DASHSCOPE_IMAGE_WATERMARK` / `DASHSCOPE_IMAGE_NEGATIVE_PROMPT` / `DASHSCOPE_IMAGE_PROMPT_EXTEND` / `DASHSCOPE_IMAGE_SIZE`
  - 默认：均未设置则不附加对应字段。
  - 作用：与 SDK 示例关键词对齐的零散变量；可被 `AIA_IMAGE_EXPERT_REQUEST_EXTRA`（或别名 JSON）中与同名键覆盖。
  - 生效：`oclaw/platform/llm/image_legacy_client.py`

> **说明：** 历史上曾使用 `AIA_IMAGE_BASE_URL` / `AIA_IMAGE_API_KEY` / `AIA_IMAGE_MODEL` / `AIA_IMAGE_CHAT_ENDPOINT` 作为同一路由；当前实现 **不再读取** 上述变量作 OCR 通道配置，请统一改为 `AIA_OCR_*`。（`AIA_IMAGE_TOOL_RESULT_REPLAY_CAP_CHARS` 等为 **另一用途**，与 OCR 网关无关，仍保留原名。）

---

## 视频生成专家专线（``AIA_VIDEO_EXPERT_*``）

**路由 specialist=`video`** 时由 **`send_video_generation_request`** 调用百炼 / DashScope **异步文生视频** HTTP（``POST .../video-synthesis`` + ``GET .../api/v1/tasks/{task_id}``）。**区域**：北京 ``https://dashscope.aliyuncs.com``、新加坡 ``https://dashscope-intl.aliyuncs.com``、美东 ``https://dashscope-us.aliyuncs.com`` 等须与 API Key 一致。说明全文见 ``docs/VIDEO_SPECIALIST_LANE.md``。

- `AIA_VIDEO_SPECIALIST_DISABLE_LEGACY_GATEWAY_LANE`
  - 默认：未设置（关闭等价于 **启用** 专用 Early Return）
  - 作用：设为 `1` / `true` / `yes` / `on` 时，网关 **不再** 走专用视频 HTTP 线，改与普通 Chat 相同的模型环路。
  - 生效：`runtime/direct_loop.py`

- `AIA_VIDEO_EXPERT_BASE_URL`
  - 默认：无（必填，除非在调用处传入 `base_url`）
  - 作用：DashScope 根 URL（可为 ``compatible-mode/v1`` 前缀，实现会剥离后拼接原生路径）。
  - 生效：`oclaw/platform/llm/video_generation_client.py`

- `AIA_VIDEO_EXPERT_API_KEY`
  - 默认：无（必填，除非显式传 `api_key`）
  - 作用：``Authorization: Bearer`` API Key。
  - 生效：`oclaw/platform/llm/video_generation_client.py`

- `AIA_VIDEO_EXPERT_MODEL`
  - 默认：无（会话所选模型的 `model` 字段优先；无则读本变量）
  - 作用：Wan 模型 id：**文生视频**用 t2v 系列（如 ``wan2.2-t2v-plus``）；**图生视频**（消息带首帧图时自动传 ``input.img_url``）须用 **i2v** 系列（如 ``wan2.6-i2v-flash``，以控制台为准）。
  - 生效：`oclaw/platform/llm/video_generation_client.py`

- `AIA_VIDEO_EXPERT_SYNTHESIS_PATH`
  - 默认：`api/v1/services/aigc/video-generation/video-synthesis`
  - 作用：相对 `AIA_VIDEO_EXPERT_BASE_URL` 剥离 compatible 后缀后的根路径拼接用。
  - 生效：`oclaw/platform/llm/video_generation_client.py`

- `AIA_VIDEO_EXPERT_POLL_INTERVAL_SEC`
  - 默认：`15`（限制在约 `3`～`120` 秒）
  - 作用：轮询任务状态间隔。
  - 生效：`oclaw/platform/llm/video_generation_client.py`

- `AIA_VIDEO_EXPERT_MAX_WAIT_SEC`
  - 默认：`900`（限制在约 `30`～`3600` 秒）
  - 作用：自提交任务起的最大等待时间；超时返回错误。
  - 生效：`oclaw/platform/llm/video_generation_client.py`

- `AIA_VIDEO_EXPERT_PARAMETERS_EXTRA`
  - 默认：无
  - 作用：JSON 对象，**浅合并**到请求体 `parameters`（后写入，故与 `DASHSCOPE_VIDEO_*` 同名键时 **以该 JSON 为准**）。
  - 生效：`oclaw/platform/llm/video_generation_client.py`

- `AIA_VIDEO_EXPERT_INPUT_EXTRA`
  - 默认：无
  - 作用：JSON 对象，合并到请求体 `input`（`prompt` 仍由运行时代码写入并覆盖同名键）。
  - 生效：`oclaw/platform/llm/video_generation_client.py`

- `AIA_VIDEO_EXPERT_DEBUG_PRINT_PAYLOAD`
  - 默认：未设置
  - 作用：设为 `1` 时在 stderr 打印提交 URL 与 JSON 请求体（勿在生产长期开启）。
  - 生效：`oclaw/platform/llm/video_generation_client.py`

- `DASHSCOPE_VIDEO_SIZE` / `DASHSCOPE_VIDEO_DURATION` / `DASHSCOPE_VIDEO_PROMPT_EXTEND` / `DASHSCOPE_VIDEO_NEGATIVE_PROMPT` / `DASHSCOPE_VIDEO_AUDIO_URL` / `DASHSCOPE_VIDEO_SHOT_TYPE` / `DASHSCOPE_VIDEO_WATERMARK` / `DASHSCOPE_VIDEO_SEED`
  - 默认：均未设置则不附加对应字段。
  - 作用：与官方示例字段对齐的便捷变量；细粒度控制可改用 `AIA_VIDEO_EXPERT_PARAMETERS_EXTRA` / `AIA_VIDEO_EXPERT_INPUT_EXTRA`。
  - 生效：`oclaw/platform/llm/video_generation_client.py`

## Memory / RAG

- `AIA_RAG_MODE`
  - 默认：`keyword`
  - 作用：RAG 模式（`keyword`/`vector`）
  - 生效：`oclaw/orchestration/memory.py`

- `AIA_RAG_EMBEDDING_MODE`
  - 默认：空（优先 OpenAI，失败回退 hash）
  - 作用：embedding 模式（如 `hash`）
  - 生效：`oclaw/platform/embeddings/embedding_client.py`

- `AIA_MEMORY_EPISODIC_TTL_DAYS`
  - 默认：`90`
  - 作用：episodic memory 过期天数
  - 生效：`oclaw/orchestration/memory.py`

## 工作区路径策略

- `AIA_WORKSPACE_ROOT`
  - 默认：项目根
  - 作用：工作区主根路径
  - 生效：`oclaw/tools/experts/workspace/workspace_base.py`, `oclaw/tools/workspace_indexer.py`

- `AIA_WORKSPACE_EXTRA_ROOTS`
  - 默认：空
  - 作用：额外可访问根路径（`|` 分隔）
  - 生效：`oclaw/tools/experts/workspace/workspace_base.py`, `oclaw/tools/mcp/filesystem_argv.py`

- `AIA_WORKSPACE_ALLOW_ANY_PATH`
  - 默认：`0`
  - 作用：是否放开内置工具路径限制（高风险）
  - 生效：`oclaw/tools/experts/workspace/workspace_base.py`

## 网关与运行

- `AIA_ASSISTANT_GATEWAY_HOST`
  - 默认：`0.0.0.0`
  - 作用：网关监听地址
  - 生效：`oclaw/app_server/fastapi_main.py`, `oclaw/runtime/operations/main.py`

- `AIA_ASSISTANT_GATEWAY_PORT`
  - 默认：`8787`
  - 作用：网关监听端口
  - 生效：`oclaw/app_server/fastapi_main.py`, `oclaw/runtime/operations/main.py`

- `OCLAW_UVICORN_WS_MAX_SIZE`
  - 默认：未设置时由 `interfaces.http.fastapi_app:main` 使用与 `MAX_PAYLOAD_BYTES`（约 25MB）相同的值传入 uvicorn `ws_max_size`
  - 作用：**uvicorn 对 WebSocket 单帧的字节上限**（与 hello 里 `maxPayload` 应对齐）。uvicorn 自带默认约 **16MB**；两张高清图经 base64 塞进一条 `chat.send` 常超过 16MB，服务端直接断连，浏览器侧表现为 **`ws_closed`** / 请求失败
  - 说明：若用命令行 `uvicorn ...` 启动而未走 `fastapi_app.main()`，需自行加 `--ws-max-size` 或设置本变量（取决于你的启动入口是否读取）
  - 生效：`oclaw/interfaces/http/fastapi_app.py`

- `AIA_RUNTIME_LOG_DIR`
  - 默认：空（使用内部默认目录）
  - 作用：运行日志目录
  - 生效：`oclaw/runtime/operations/runtime.py`

- `AIA_SSE_QUEUE_MAXSIZE`
  - 默认：`2000`
  - 作用：SSE 事件队列上限
  - 生效：`oclaw/interfaces/admin/chat_api.py`

- `OCLAW_WS_REQUIRE_AUTH`
  - 默认：`1`
  - 作用：WebSocket 握手是否强制鉴权；开启时 `connect` 必须携带并通过 token 校验
  - 生效：`oclaw/interfaces/ws/common.py`, `oclaw/interfaces/ws/runtime_helpers.py`

- `OCLAW_WS_ALLOWED_ORIGINS`
  - 默认：空（回落为 same-host 校验）
  - 作用：WebSocket 握手 Origin 白名单（逗号分隔）
  - 生效：`oclaw/interfaces/ws/common.py`, `oclaw/interfaces/ws/runtime_impl.py`

- `OCLAW_WS_RATE_LIMIT_WINDOW_MS`
  - 默认：`60000`
  - 作用：WebSocket 请求限流窗口（毫秒）
  - 生效：`oclaw/interfaces/ws/common.py`, `oclaw/interfaces/ws/runtime_impl.py`

- `OCLAW_WS_RATE_LIMIT_CONN_PER_WINDOW`
  - 默认：`120`
  - 作用：单连接在限流窗口内可处理请求上限
  - 生效：`oclaw/interfaces/ws/common.py`, `oclaw/interfaces/ws/runtime_impl.py`

- `OCLAW_WS_RATE_LIMIT_IP_PER_WINDOW`
  - 默认：`240`
  - 作用：单 IP 在限流窗口内可处理请求上限
  - 生效：`oclaw/interfaces/ws/common.py`, `oclaw/interfaces/ws/runtime_impl.py`

- `OCLAW_WS_RATE_LIMIT_USER_PER_WINDOW`
  - 默认：`360`
  - 作用：单用户在限流窗口内可处理请求上限
  - 生效：`oclaw/interfaces/ws/common.py`, `oclaw/interfaces/ws/runtime_impl.py`

- `OCLAW_WS_SEND_QUEUE_MAX_MESSAGES`
  - 默认：`256`
  - 作用：每连接发送队列最大消息数（背压阈值）
  - 生效：`oclaw/interfaces/ws/common.py`, `oclaw/interfaces/ws/runtime_impl.py`, `oclaw/interfaces/ws/events.py`

- `OCLAW_WS_SEND_QUEUE_MAX_BYTES`
  - 默认：`52428800`（与 `MAX_BUFFERED_BYTES` 一致）
  - 作用：每连接发送队列最大字节数（背压阈值）
  - 生效：`oclaw/interfaces/ws/common.py`, `oclaw/interfaces/ws/runtime_impl.py`, `oclaw/interfaces/ws/events.py`

- `OCLAW_WS_EVENT_REPLAY_MAX`
  - 默认：`256`
  - 作用：每用户最近事件回放缓冲上限（用于 `connect.params.lastSeq` 断线补偿）
  - 生效：`oclaw/interfaces/ws/common.py`, `oclaw/interfaces/ws/runtime_impl.py`, `oclaw/interfaces/ws/runtime_helpers.py`

## WeCom 长连接

- `AIA_WECOM_LONGCONN_WORKERS`
  - 默认：`2`
  - 作用：入站处理 worker 数
  - 生效：`oclaw/interfaces/channels/wecom/longconn_runner.py`

- `AIA_WECOM_LONGCONN_INBOUND_QUEUE_MAXSIZE`
  - 默认：`200`
  - 作用：入站队列长度上限
  - 生效：`oclaw/interfaces/channels/wecom/longconn_runner.py`

## 安全与密钥

- `AIA_ASSISTANT_PASSWORD`
  - 默认：空（必须配置）
  - 作用：管理台管理员密码（bootstrap/login）
  - 生效：`oclaw/platform/config/passwords.py`, `oclaw/interfaces/admin/routes.py`

- `AIA_ASSISTANT_MASTER_KEY`
  - 默认：空
  - 作用：密钥加密（Fernet）主密钥
  - 生效：`oclaw/platform/persistence/sqlite_store.py`, `oclaw/interfaces/admin/routes.py`

## 存储与迁移

- `AIA_ASSISTANT_DB_PATH`
  - 默认：`data/ai_ops.sqlite`
  - 作用：SQLite 路径
  - 生效：`oclaw/platform/config/paths.py`

- `AIA_ASSISTANT_PREMERGE_BACKUP_KEEP`
  - 默认：`3`
  - 作用：预迁移备份保留数量
  - 生效：`oclaw/platform/config/paths.py`

- `AIA_LEGACY_DB_FORCE_PREMERGE`
  - 默认：`0`
  - 作用：是否强制 legacy DB 覆盖（谨慎使用）
  - 生效：`oclaw/platform/config/paths.py`
