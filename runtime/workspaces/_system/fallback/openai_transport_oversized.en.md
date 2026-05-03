---
title: fallback_openai_transport_oversized_en
summary: oversized payload failure in English
read_when: model request too large
---
**Model request failed (message too large):** `{{error_type}}: {{error_message}}`

Common causes: oversized tools schema or large tool results in history. Tune `AIA_OPENAI_TOOLS_MAX_JSON_CHARS`, reduce MCP tools, or narrow the query.

