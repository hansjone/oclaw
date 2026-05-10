# 视频生成专家（Chat UI）专用链路

本文描述 **Admin `/chat` 选择「视频」专家**（工作区 id **`video`**）时的端到端路径。与图片专家类似，这是一条 **与通用 Responses / 主对话工具环路隔离** 的分支：在 `skill_binding_role == "video"` 时 **Early Return**，不进入常规 `run_oclaw_direct_loop` 多轮工具循环。

参考 API 形态：阿里云 Model Studio **Wan**（DashScope 异步：同一 `POST …/video-synthesis` → `GET …/api/v1/tasks/{task_id}`）。**文生视频**仅 `input.prompt`；**图生视频**额外设置 `input.img_url`（公网 HTTPS 或 `data:image/...;base64,...` 首帧），需使用 **i2v** 模型（如 `wan2.6-i2v-flash`，以控制台为准）。区域化的 **`base_url` 必须与 API Key 区域一致**。控制台 API 入口示例：[百炼控制台](https://bailian.console.aliyun.com/)。

---

## 1. 触发条件与隔离边界

| 条件 | 说明 |
|------|------|
| UI / Gateway | 用户选择专家 **`video`**，请求携带 `skill_binding_role` 为 **`video`**。 |
| 入口守卫 | `runtime/direct_loop.py` 中 **`_maybe_video_specialist_legacy_gateway_turn`**：仅当 `skill_binding_role.lower() == "video"` 且未设置禁用开关时执行。 |
| 禁用开关 | `AIA_VIDEO_SPECIALIST_DISABLE_LEGACY_GATEWAY_LANE=1`：关闭本 Early Return，视频专家改走与普通会话相同的模型/传输栈。 |

实现集中在 **`platform/llm/video_generation_client.py`**（HTTP + 轮询 + 附件落地），避免在 `openai_responses` 中分叉。

---

## 2. 运行时数据流（网关 → 落库）

1. **`run_oclaw_direct_loop`** 在用户消息落库后，在图片专家分支之后调用 **`_maybe_video_specialist_legacy_gateway_turn`**。
2. **Prompt**：使用本轮用户文本；若为空则使用 **`VIDEO_SPECIALIST_DEFAULT_PROMPT_ZH`**（`video_generation_client`）。图生视频时 `prompt` 仍建议填写（描述期望动态与镜头）。
3. **首帧图**：与图片专家相同，使用 **`collect_legacy_lane_images_with_session_fallback`**（`image_legacy_client`）从**本轮附件**或（未关闭 **`AIA_IMAGE_SPECIALIST_SESSION_IMAGE_FALLBACK`** 时）**会话历史**中取 **1 张**图，转为 URL / data URL 后写入 **`input.img_url`**。无图则走纯文生视频。
4. **鉴权与根 URL**：优先使用会话所选模型的 **`model` / `base_url` / `api_key`**；缺省字段由 **`AIA_VIDEO_EXPERT_*`** 环境变量补全。若 `base_url` 指向 **`compatible-mode/v1`**，实现会剥离该后缀以拼接原生 DashScope 路径。
5. **调用**：`send_video_generation_request` — `POST .../video-synthesis`（`X-DashScope-Async: enable`），再轮询 **`GET .../api/v1/tasks/{task_id}`** 直至 `SUCCEEDED` / 失败 / 超时。
6. **输出**：成功时从 `output.video_url` 下载为本地 blob，产出 **`video_ref`**；下载失败时退化为仅带 **`url`** 的 `video_ref` 行（前端仍可尝试外链播放）。
7. **占位文案**：`legacy_video_assistant_body_with_placeholder` 与图片专家对称（仅附件、无正文时插入中英文短句）。
8. **编排**：`runtime/agents/specialist_agent.py` 在 `step.specialist == "video"` 时调用同一客户端（按父任务附件 + 父会话历史解析首帧），保证综合模式子专家与专家模式行为一致。

---

## 3. 执行器与工具面

- **`runtime/agents/factory.py`**：`video` 与 `image` 一样使用 **不可能工具名 allowlist**，避免默认工具注册混入。
- **`runtime/gateway.py`**：综合模式 Manager 白名单包含 **`video`**，否则子专家选择会被回退。

---

## 4. 鉴权与附件（ACL）

与 **`image_ref`** 相同，助手消息上的 **`video_ref`** 依赖 **`attachment_acl`** 才能在严格模式下通过下载接口访问；落库时由 `SqliteStore.add_message` 链路处理。参见 **`docs/attachment-acl.md`**。

---

## 5. 前端

- **`interfaces/admin/static/chat.js`**：`specialistLabel` 对 **`video`** 显示短标签；`video_ref` 卡片在可用 blob URL 或外链 URL 时附加 **`<video controls>`** 便于预览。

---

## 6. 环境变量（索引）

详见 **`docs/ENVIRONMENT_VARIABLES.md`** 中 **`AIA_VIDEO_EXPERT_*`** 与 **`DASHSCOPE_VIDEO_*`** 小节。

---

## 7. 测试

- **`tests/test_video_generation_client.py`**：提交 / 轮询 HTTP 形态的单元测试（mock `httpx`）。

---

## 8. 变更原则

1. 默认只改 **`video_generation_client.py`**、`direct_loop` 的 **`_maybe_video_specialist_*`**、`specialist_agent` 视频分支、`factory` / `gateway` 白名单、**`chat.js`** 附件展示、本文与 **`ENVIRONMENT_VARIABLES.md`**。
2. 勿在通用 **`openai_responses`** 中为视频专家单独绕路，除非产品明确要求统一传输。
