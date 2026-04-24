# OCLAW Compat Layer Removal Checklist

Use this checklist to verify readiness and post-delete safety for `oclaw/app_server/*` compatibility-module removal.

## Import graph checks
- [x] `rg "src\.app_server\."` has no runtime/code matches (tests excluded or updated).
- [x] CLI/runtime startup paths import from `oclaw.interfaces.*` only.
- [x] WebSocket entrypoint imports resolve through `oclaw.interfaces.ws.*`.

## Behavior parity checks
- [x] HTTP gateway smoke tests pass (`/health`, `/inbound`, `/gateway/method`, `/ws` handshake).
- [x] WS request/response contract remains unchanged for:
  - [x] `connect`
  - [x] `chat.send/chat.history/chat.abort`
  - [x] `sessions.*`
  - [x] `agent.run/agent.wait`
- [x] Plugin bootstrap still loads expected extension set.

## Prompt/skill checks
- [x] Runtime role context still loads from `oclaw/agent/*`.
- [x] Skill root priority still effective:
  - [x] `AIA_SKILLS_ROOT`
  - [x] `oclaw/skills`
  - [x] `skills/` fallback

## Extension policy checks
- [x] Primary extension source remains `oclaw/extensions/`.
- [x] Legacy root `extensions/` has been fully merged and removed.
- [x] Duplicate plugin-id diagnostics still emitted as expected.

## Final cleanup
- [x] Delete compatibility files under `oclaw/app_server/*` only after all checks are green.
- [x] Remove stale docs/comments referring to old primary entrypoints.
- [x] Re-run lint and targeted compile checks after deletion.

