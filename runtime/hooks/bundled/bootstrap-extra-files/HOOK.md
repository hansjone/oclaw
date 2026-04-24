---
name: bootstrap-extra-files
description: "Inject additional workspace bootstrap files via glob/path patterns"
metadata:
  oclaw:
    emoji: "📎"
    events: ["agent:bootstrap"]
---

# Bootstrap Extra Files Hook (Python)

On `agent:bootstrap`, expands extra file glob patterns and appends them to `event.context.bootstrapFiles`.

Config example (hook key `bootstrap-extra-files`):

```json
{
  "hooks": {
    "internal": {
      "entries": {
        "bootstrap-extra-files": {
          "enabled": true,
          "paths": ["packages/*/AGENTS.md", "packages/*/TOOLS.md"]
        }
      }
    }
  }
}
```

