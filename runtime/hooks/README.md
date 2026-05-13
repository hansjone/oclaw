## `oclaw/runtime/hooks`

Python hooks runtime and bundled hook packages (parity target: OpenClaw `src/hooks`).

### What you get

- **In-process hook bus**: register on `type` or `type:action`, sync/async handlers, isolated failures.
- **Directory discovery**: `HOOK.md` + **one** handler file per hook directory (first match in priority order, see `workspace._handler_candidates`).
- **Config gating**: `hooks.internal.enabled` and `hooks.internal.entries.<hookKey>.enabled`.
- **Source precedence**: bundled / managed / workspace / plugin collision resolution (`policy`).
- **Eligibility**: OS / bins / env / config paths; optional **remote** context from message metadata (`eligibility_from_metadata` + `config.should_include_hook`).

### Handler entry priority

First existing file under the hook directory wins:

`handler.py` → `index.py` → `handler.ts` → `index.ts` → `handler.mts` → `index.mts` → `handler.cts` → `index.cts` → `handler.mjs` → `index.mjs` → `handler.cjs` → `index.cjs` → `handler.sh` → `index.sh` → `handler.bash` → `index.bash`

### Hook layout

Put hooks in any of:

- **Bundled**: shipped with runtime (`runtime_hooks_bundled_root()`)
- **Managed**: `~/.oclaw/hooks/<hookName>/`
- **Workspace**: `<workspace>/hooks/<hookName>/`
- **Plugin**: `.openclaw/extensions/<id>/.codex-plugin/plugin.json` → `hooks` paths
- **Extra dirs**: `hooks.internal.load.extraDirs` plus skill-side `.../hooks` dirs merged at runtime init

Each hook directory needs `HOOK.md` (YAML frontmatter with `metadata.oclaw.events`) plus one handler file as above.

### Session-bootstrap integration (verified)

`session-bootstrap` is wired into the hooks runtime and loads on `agent:bootstrap`.

- Hook package path: `skills/session-bootstrap/hooks/runtime/`
- Manifest: `HOOK.md` (`metadata.oclaw.events: ["agent:bootstrap"]`)
- Handler: `handler.py` (`handle(event)`)
- Runtime source type: `oclaw-managed` (skill `hooks/` dirs are merged into `hooks.internal.load.extraDirs`)

#### End-to-end effect

1. Runtime discovers the skill hook directory.
2. Loader registers `session-bootstrap` on `agent:bootstrap`.
3. Bootstrap event triggers `handle(event)`.
4. Handler injects virtual `SESSION_BOOTSTRAP.md` into `event.context.bootstrapFiles`.
5. Agent bootstrap context consumes that file for continuity (identity + recent memory + wiki signals).

Current wiki inputs used by `session-bootstrap` include:

- `data/wiki/core/*.md` (auto-discovered, sorted by filename; extensible for OSS contributors)
- `data/wiki/experts/<role>/*.md` (role-scoped rules, loaded when current `agentId` matches `<role>`)
- `data/wiki/improvement/learnings.md`
- `data/wiki/improvement/errors.md`
- `data/wiki/improvement/feature-requests.md`

For open-source extensibility, contributors only need to add new Markdown files under `data/wiki/core/` (for example `tone-style.md`), and bootstrap will include them automatically.
For role-specific behavior, contributors can add files under `data/wiki/experts/<role>/` (for example `experts/generalist/style.md`).

#### Quick check

```bash
python -m runtime.operations hooks info session-bootstrap --workspace "D:/project/chatgpt/oclaw" --json
```

Expected key fields: `enabled_by_config=true`, `eligible=true`, `loadable=true`.

### Remote eligibility on inbound messages

Callers (e.g. gateway) may attach JSON metadata:

```json
{
  "hookEligibility": {
    "remote": {
      "platforms": ["linux"],
      "binsPresent": ["git", "node"],
      "note": "remote agent capabilities"
    }
  }
}
```

Parsed by `hook_eligibility_from_message_metadata` and passed into `initialize_hooks_runtime(..., eligibility=...)`. **Note:** hook runtime initializes once per process; the first successful init wins (see `hooks_runtime.initialize_hooks_runtime`).

### TS parity matrix (OpenClaw `src/hooks`)

Legend: **Done** / **Partial** / **TODO**

| Area | Status |
|------|--------|
| internal-hooks bus (`register` / `trigger` / `type` + `type:action`) | Done |
| loader (`.py` import + TS/JS/shell runners, `hookMode` / `nodeScript`) | Done |
| path boundary (`handlerPath` under `baseDir`) | Done |
| frontmatter + `metadata.oclaw` | Done |
| invocation + config enable gate | Done |
| policy / source precedence | Done |
| runtime eligibility (`os` / `requires` / env / config) | Done |
| remote eligibility (`platforms` / `hasBin` / `hasAnyBin`) — filter API + gateway metadata wiring | Done |
| package.json `openclaw.hooks` / `oclaw.hooks` | Done |
| plugin hook dirs (`.codex-plugin` + `hooks`) | Done |
| legacy `hooks.internal.handlers` | Done |
| `hooks list/check/info` CLI (`python -m runtime.operations hooks …`) | Done |
| `hooks enable` / `hooks disable` (config file patch) | Done |
| install / update hook packs (npm/git; TS `install.ts` / `update.ts`) | Partial (`hooks install` / `hooks update` print deprecation + manual/OpenClaw guidance; no npm/git runner) |
| gmail watcher family | Partial (config gates + ``initialize_hooks_runtime`` → ``start_gmail_watcher_with_logs``; ``gog``/API loop not ported). Set ``OCLAW_SKIP_GMAIL_WATCHER=1`` (or ``OPENCLAW_SKIP_GMAIL_WATCHER``) to no-op. |
| fire-and-forget / message-hook mappers | TODO |

### Minimal self-test

From the repository root (see `tests/conftest.py` for `sys.path` layout):

```bash
python runtime/hooks/_selftest.py
```

or run hook discovery / parity tests:

```bash
pytest tests/test_oclaw_hooks_bundled_parity.py tests/test_oclaw_hooks_runtime.py -q
```

### Operations CLI (from parent of this repo on `sys.path`, see `tests/conftest.py`)

```bash
python -m runtime.operations hooks list
python -m runtime.operations hooks list --eligible --verbose
python -m runtime.operations hooks check --json
python -m runtime.operations hooks info session-memory --workspace /path/to/workspace
python -m runtime.operations hooks enable session-memory --workspace /path/to/workspace
python -m runtime.operations hooks disable command-logger --workspace /path/to/workspace
python -m runtime.operations hooks install ./path-or-npm-spec   # deprecated, exit 2 + hints
python -m runtime.operations hooks update --dry-run             # deprecated, exit 2 + hints
```

Uses the same merged config as the agent runtime (including skill `hooks/` extra dirs via `merge_skill_hook_extra_dirs_into_config`).

**Enable** matches OpenClaw semantics: the hook must satisfy **requirements** (bins/os/env/config) if its config entry were turned on; **plugin** hooks cannot be toggled from this CLI. Writes go to **`OCLAW_CONFIG_PATH`** (optional, relative paths resolved under `PROJECT_ROOT`) or **`oclaw/oclaw.json`** by default.
