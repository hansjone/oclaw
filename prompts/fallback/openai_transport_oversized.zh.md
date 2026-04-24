---
title: fallback_openai_transport_oversized_zh
summary: oversized payload failure in Chinese
read_when: model request too large
---
**调用模型失败（单条消息过长）：** `{{error_type}}: {{error_message}}`

常见原因：tools 负载过大或 tool 返回过长。可调整 `AIA_OPENAI_TOOLS_MAX_JSON_CHARS`，或减少 MCP / 缩小查询范围后重试。

