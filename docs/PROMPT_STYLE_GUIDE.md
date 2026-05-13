# Prompt Style Guide

## Goal
- System/builtin model-facing prompt templates live under `runtime/workspaces/_system/`; role-specific copy lives under `runtime/workspaces/<role>/` (e.g. `ROLE_SYSTEM.md`). Load via `runtime.prompt_templates`.
- Business code must inject variables only; no long inline prompt strings.

## Template Contract
- File format: `.md` with frontmatter.
- Required frontmatter keys: `title`, `summary`, `read_when`.
- Variables use `{{var_name}}`.
- Missing variables must fail in strict mode.

## Required Section Order
1. Identity and objective
2. Input constraints
3. Execution rules
4. Output format
5. Safety and prohibitions
6. Optional runtime context blocks

## Rules
- Use imperative instructions: must / must not / only when.
- Keep deterministic section ordering for cache stability.
- Prefer machine-parseable blocks for injected context.
- Do not embed raw JSON protocol examples unless needed.
- Keep bilingual copies as separate template files when wording diverges.

