## `oclaw/hooks`

Unified Python hooks runtime and hook packages.

### What you get

- **In-process hook bus**: register on `type` or `type:action`, sync/async handlers, isolated failures.
- **Directory discovery**: finds hooks by `HOOK.md + handler.py` (or `index.py`).
- **Config gating**: supports `hooks.internal.enabled` and `hooks.internal.entries.<hookKey>.enabled`.
- **Source precedence**: bundled / managed / workspace collision resolution.

### Hook layout

Put hooks in any of:

- **Bundled**: `oclaw/hooks/bundled/<hookName>/`
- **Managed**: `~/.oclaw/hooks/<hookName>/`
- **Workspace**: `<workspace>/hooks/<hookName>/` (explicit opt-in by default)

Each hook directory must contain:

- `HOOK.md` with YAML frontmatter including `metadata.oclaw.events`
- `handler.py` (or `index.py`) exporting a callable `handle(event)`

### Minimal self-test

```bash
python "oclaw/hooks/_selftest.py"
```

