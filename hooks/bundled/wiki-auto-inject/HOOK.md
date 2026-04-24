---
name: wiki-auto-inject
description: "Inject wiki context before model prompt build"
metadata:
  openclaw:
    emoji: "📚"
    events: ["llm:before_prompt_build"]
---

# Wiki Auto Inject Hook

Builds a compact wiki context block and prepends it to system prompt via
`event.context.prepend_system_context`.
