---
title: prompts_scope_after_oclaw_migration
summary: Scope boundary for legacy and fallback prompts under oclaw/prompts.
read_when:
  - Maintaining prompt files under oclaw/prompts.
  - Distinguishing Oclaw runtime prompts from non-Oclaw prompts.
---

# `oclaw/prompts` Scope

Oclaw runtime prompts have been migrated to `oclaw/prompts_runtime`.

`oclaw/prompts` now keeps only:

- `fallback/*`: user-facing fallback/error templates.
- Non-Oclaw shared templates still used by runtime components, such as:
  - `runtime/default_system.{zh,en}.md`
  - `tools/*`
  - `image/default_edit_prompt.zh.md`

Do not add new Oclaw manager/router/specialist/runtime chain prompts here.
Use `oclaw/prompts_runtime/*` instead.
