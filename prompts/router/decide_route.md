---
title: oclaw_router_decide_route
summary: LLM JSON routing prompt for sync vs async oclaw turns (Chinese only).
read_when: AIA_OCLAW_ROUTER_MODE=llm_json
---
# 路由决策（结构化输出）

你需要判断当前用户输入应采用哪种执行模式：

- `sync_direct`：当前请求内直接回复（默认）。
- `async_task`：明确是多步骤后台流程（例如“总结并发送”）、或输入极大且带附件。

## 输入
- 用户文本：
```
{{user_text}}
```
- 是否有附件：`{{has_attachments}}`

## 输出（严格）
只返回一行 JSON，不要 Markdown、不要解释：

`{"mode":"sync_direct"|"async_task","reason":"<简短原因>"}`

默认倾向 `sync_direct`，只有明确需要异步才选 `async_task`。
