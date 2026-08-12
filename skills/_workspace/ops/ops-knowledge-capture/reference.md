# Ops knowledge capture — quick reference

## Wiki paths (relative to `wiki_root` = `data/wiki`)

| File | Purpose |
|------|---------|
| `experts/ops/site-aliases.md` | Nickname / area word → `host_name` |
| `experts/ops/report-conventions.md` | Reply language, Result/Evidence, xlsx habits |
| `experts/ops/field-cli-corrections.md` | Vendor CLI prefer/fallback after field proof |

If missing, create with `memory_wiki_apply` `action=write` using the stubs below.

## Emphasis → layer (short)

```
以后/记住/always/别再  + 绰号     → Wiki site-aliases
以后/记住/always       + 格式/语言 → Wiki report-conventions
纠正/别用错命令        + CLI      → Wiki field-cli-corrections
稳定工具流程 ≥2        → propose playbook edit
单次故障闭环           → IP KB 07 draft (ask first)
协议规律/基线          → IP KB 01–06 (user ask or multi-case distill)
告警表/CLI dump/密钥   → NEVER
```

## Stub: site-aliases.md

```markdown
# Ops site aliases

> Field nicknames and area words → real `host_name`. Search before inventing.

## [Knowledge] Index
- Confidence: high
- Source: seed
- First-Seen: 2026-08-12
- Applies-To: WhatsApp field ops

Append new rows under **Aliases**; keep one fact per block.

### Aliases

| Nickname / area word | host_name (or prefix) | Notes |
|----------------------|-------------------------|-------|
| _(example)_ SEMBAWA | PLG-SMW-EN1-… | confirm via inventory |
```

## Stub: report-conventions.md

```markdown
# Ops report conventions

## [Knowledge] Default field reply shell
- Confidence: high
- Source: ROLE_SYSTEM
- First-Seen: 2026-08-12
- Applies-To: WhatsApp lang=en

Use Result / Evidence / Next; host_name only; no CJK in user-visible English sessions.

### Team overrides

_(append user-emphasized format rules here)_
```

## Stub: field-cli-corrections.md

```markdown
# Ops field CLI corrections

> Prefer/fallback after live verification. One failure → switch command, do not blind-retry.

## [Knowledge] ZTE optical brief
- Confidence: high
- Source: field playbook
- First-Seen: 2026-08-12
- Applies-To: ZXR10 / ZTE EN

Prefer `show opticalinfo brief`; fallback `show optical brief`; narrow with `| begin <if>`.

### More corrections

_(append vendor/platform corrections here)_
```

## Example capture (WA)

User: `remember SEMBAWA is PLG-SMW-EN1-ABC`

1. `memory_wiki_search` query=`SEMBAWA`
2. No hit → `memory_wiki_apply` append to `experts/ops/site-aliases.md`
3. Final reply still answers the ops ask; optional `Next: alias saved`

## Example non-capture

User: `fiber cut BPP` → only ume playbook; **do not** write alarm counts to wiki.
