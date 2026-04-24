---
name: boot-md
description: "Run BOOT.md on gateway startup"
metadata:
  oclaw:
    emoji: "🚀"
    events: ["gateway:startup"]
---

# Boot Checklist Hook (Python)

On `gateway:startup`, looks for `BOOT.md` under common workspace roots and records a run log.

