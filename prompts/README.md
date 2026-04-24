---
title: prompts_scope_after_openclaw_migration
summary: Scope boundary for legacy and fallback prompts under oclaw/prompts.
read_when:
  - Maintaining prompt files under oclaw/prompts.
  - Distinguishing OpenClaw runtime prompts from non-OpenClaw prompts.
---

# `oclaw/prompts` Scope

OpenClaw runtime prompts have been migrated to `oclaw/prompts_openclaw`.

`oclaw/prompts` now keeps only:

- `fallback/*`: user-facing fallback/error templates.
- Non-OpenClaw shared templates still used by runtime components, such as:
  - `runtime/default_system.{zh,en}.md`
  - `tools/*`
  - `image/default_edit_prompt.zh.md`

Do not add new OpenClaw manager/router/specialist/runtime chain prompts here.
Use `oclaw/prompts_openclaw/*` instead.
