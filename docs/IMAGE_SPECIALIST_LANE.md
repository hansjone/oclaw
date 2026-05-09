# 图片专家（Chat UI）专用链路

本文描述 **Admin `/chat` 选择「图片」专家** 时的端到端路径。这是一条 **与通用 Responses / 主对话模型环路隔离** 的特殊分支：仅在 `skill_binding_role == "image"` 时进入，其它专家或综合模式不受影响。

> 与本文无关：`docs/GATEWAY_IMAGE_GENERATE.md`（网关 RPC `image.generate`）、OCR 工具使用的 `image_ocr_client` 等。

---

## 1. 触发条件与隔离边界

| 条件 | 说明 |
|------|------|
| UI / Gateway | 用户在前端选择专家 **`image`**，请求体携带 `skill_binding_role`（或等价字段）为 **`image`**。 |
| 入口守卫 | `runtime/direct_loop.py` 中 **`_maybe_image_specialist_legacy_gateway_turn`**：仅当 `skill_binding_role.lower() == "image"` 且未设置禁用开关时执行；否则返回 `None`，后续仍走常规 `run_oclaw_direct_loop`。 |
| 禁用开关 | `AIA_IMAGE_SPECIALIST_DISABLE_LEGACY_GATEWAY_LANE=1`：关闭本 Early Return，图片专家改走与普通会话相同的模型/传输栈（用于调试或迁移）。 |

**不要在本链路外混用**：DashScope 形态的多模态 HTTP、`qwen-image*` 的空兼容响应回退等，均封装在 `platform/llm/image_legacy_client.py` 与 `image_http_common.py`，避免改到 `openai_responses` 的通用逻辑。

---

## 2. 运行时数据流（网关 → 落库）

1. **`run_oclaw_direct_loop`** 在用户消息落库后立刻调用 **`_maybe_image_specialist_legacy_gateway_turn`**。
2. **输入附件**：`collect_legacy_lane_images_from_attachments` 将 UI 附件规范为 `data:` URL 或 HTTP URL（`image_ref` / `input_image` / `image_url` 等）。
3. **无图**：直接写入一条 `assistant` / `assistant_text` 提示语并返回，不调用上游。
4. **有图**：调用 **`send_legacy_image_messages`**（`/chat/completions` 兼容路径，非 Responses API）。
5. **输出解析**：**`legacy_image_turn_bundle`**  
   - 文本可为空；若有生成图则 **`materialize_legacy_response_output_attachments`** 写入本地 blob，产出 **`image_ref`**（或退化为 **`image_url`**）。
6. **占位文案**：成功但只有图、无模型正文时，由 **`legacy_image_assistant_body_with_placeholder`**（`image_legacy_client`）写入中英文占位句；网关与 `specialist_agent` 共用，避免两处字符串分叉。
7. **持久化**：**`store.add_message(role=assistant, event_type=assistant_text, attachments=…)`** —— 附件以 JSON 形式挂在助手消息上，而非 tool 行。

---

## 3. 与其它入口的差异

| 场景 | 模块 | 说明 |
|------|------|------|
| Chat 网关 + 图片专家 | `direct_loop._maybe_image_specialist_legacy_gateway_turn` | 上文主路径；Early Return，不进主 LLM 循环。 |
| Specialist 编排临时会话 | `runtime/agents/specialist_agent.py` | 同样调用 `send_legacy_image_messages` / `legacy_image_turn_bundle`，逻辑对齐但不经过同一 Early Return。 |

两处共用 **`platform/llm/image_legacy_client.py`**，避免分叉实现。

---

## 4. 鉴权与下载（严格 ACL）

助手消息上的 **`image_ref`** 需在 **`attachment_acl`** 中有记录，才能在 **`AIA_ATTACHMENT_ACL_STRICT=1`** 下通过 **`GET /admin/api/chat/attachments/{id}`**。

- **`SqliteStore.add_message`** 会在落库后根据会话 **`ui_session_owner`** 对引用型附件执行 **`link_attachment_acl`**（与 tool 结果路径一致）。
- 历史数据可用 **`POST /admin/api/chat/admin/attachments/acl/backfill`**（管理员）补齐。详见 **`docs/attachment-acl.md`**。

---

## 5. WebSocket 收口与前端展示

- **`interfaces/ws/turn_runner.py`**：`final_msg` 从最近一条非空助手消息组装；**`_persisted_chat_attachments_nonempty`** 需识别 **JSON 数组或单个 JSON 对象**，否则纯附件回合会选错行。
- **`interfaces/admin/static/chat.js`**：聚合气泡 **`_buildAggregatedAssistantBubble`** 须对 **`assistant_text`** 片段调用 **`renderAttachmentsEl`**（不仅 `tool_result`），否则会出现「只有配文、无图」的现象。

---

## 6. 环境变量（索引）

详细列表与默认值以 **`docs/ENVIRONMENT_VARIABLES.md`** 为准。与本链路相关的典型前缀：

- **`AIA_IMAGE_EXPERT_*`** / **`AIA_IMAGE_SPECIALIST_*`**：图片专家 HTTP 基址、端点、模型、请求扩展等（与 **`AIA_OCR_*`** 分离）。
- **`AIA_IMAGE_SPECIALIST_DISABLE_LEGACY_GATEWAY_LANE`**：禁用网关侧 legacy 专用线。
- **`AIA_ATTACHMENT_ACL_STRICT`**：附件下载是否仅信任 ACL。

---

## 7. 测试与回归

- **`tests/test_image_legacy_gateway_lane.py`**：legacy 解析与规范化。
- **`tests/test_attachment_acl_backfill.py`**：严格 ACL 下助手附件与 ACL 写入。
- 修改 **`chat.js`** 聚合或 **`turn_runner`** final 消息逻辑后，应用图片专家跑一轮 **生成图 + 刷新历史** 做冒烟。

---

## 8. 变更原则（避免波及其它链路）

1. **默认改动范围**：`image_legacy_client.py`、`image_http_common.py`、`direct_loop` 中 **`_maybe_image_specialist_*` 函数体**、`specialist_agent` 中与 legacy image 调用相邻代码、`turn_runner` / `chat.js` 中与 **assistant + attachments** 展示相邻逻辑。
2. **勿在** `openai_responses.py` **中为图片专家单独分支**，除非明确要做「非 legacy」通用能力。
3. 新增开关优先 **`AIA_IMAGE_*` / `AIA_IMAGE_SPECIALIST_*`**，勿复用 OCR 变量。
4. UI 层附件渲染：**assistant_text 与 tool_result** 对称处理引用型附件，避免只修一端。
