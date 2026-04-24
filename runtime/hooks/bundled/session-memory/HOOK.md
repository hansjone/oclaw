---
name: session-memory
description: "Save session context to memory when /new or /reset command is issued"
metadata:
  oclaw:
    emoji: "💾"
    events: ["command:new", "command:reset"]
---

# Session Memory Hook (Python)

On `command:new` / `command:reset`, exports the latest N messages of the session into
`<workspace>/memory/YYYY-MM-DD-<slug>.md`.

Notes:
- This Python port reads messages from SQLite (`SqliteStore`) instead of workspace session transcript files.

