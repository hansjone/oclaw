# Oclaw Migration Guide

This repository is migrating from legacy `oclaw/` runtime wiring to the new `oclaw/` architecture root.

## Current status
- `oclaw/` is the target root for new code.
- `oclaw/app_server/*` compatibility modules have been removed.
- Gateway dispatch now routes through shared `server_methods` handlers for both WS and HTTP method endpoints.

## Developer rules
- Add new business logic under `oclaw/` (interfaces/application/domain/infrastructure/shared).
- Avoid adding new core logic into legacy `oclaw/` modules.
- Keep `oclaw/` changes limited to re-export or compatibility adaptation.
- Before deleting compatibility modules, use:
  - `oclaw/docs/OCLAW_COMPAT_REMOVAL_CHECKLIST.md`

## Runtime notes
- Gateway HTTP method adapter: `POST /gateway/method`
- WS dispatch first resolves method handlers from shared dispatcher.
- Inbound payload use-case entrypoint: `oclaw.runtime.application.gateway.process_inbound_payload_usecase`
- HTTP app entrypoint moved to: `oclaw.interfaces.http.fastapi_app`
- WS entrypoint moved to: `oclaw.interfaces.ws.entrypoint`
- WS runtime bridge path: `oclaw.interfaces.ws.runtime`
- WS runtime implementation seam:
  - `oclaw/interfaces/ws/runtime_impl.py`
  - `runtime.py` points to this module as stable import surface.
- Server-method WS bridge extracted to:
  - `oclaw/interfaces/ws/server_methods_bridge.py`
  - legacy class now delegates dispatch/context construction to this bridge.
- Agent turn execution extracted to:
  - `oclaw/interfaces/ws/turn_runner.py`
  - legacy `run_agent_turn` now delegates to this module.
- WS request dispatch path is now single-source:
  - connected requests go through `server_methods` bridge first;
  - unknown methods return standardized invalid-request errors.
- Legacy WS `handle_*` and schema-specific validate helpers were removed from the class;
  runtime behavior now comes from dispatcher + bridge modules.
- WS schema access is now routed via:
  - `oclaw/interfaces/ws/ws_schema.py`
  - legacy gateway imports schema helpers through the oclaw namespace.
- WS schema implementation has been migrated to:
  - `oclaw/interfaces/ws/schema_impl.py`
  - no legacy `oclaw/app_server/ws_schema.py` dependency remains.
- WS auth + hello payload builders moved to:
  - `oclaw/interfaces/ws/auth_and_hello.py`
  - legacy gateway delegates `resolve_ws_auth` and `build_hello_ok`.
- WS frame/event emit helpers moved to:
  - `oclaw/interfaces/ws/events.py`
  - legacy gateway delegates `send_res/send_event/emit_*`.
- WS runtime helpers moved to:
  - `oclaw/interfaces/ws/runtime_helpers.py`
  - legacy gateway delegates `_recv_frame` and `_handle_connect`.
- WS main loop + close behavior moved to:
  - `oclaw/interfaces/ws/runtime_loop.py`
  - legacy gateway delegates `run()` and `_close_ws()`.
- WS connected-request dispatch moved to:
  - `oclaw/interfaces/ws/runtime_dispatch.py`
  - legacy gateway delegates `_dispatch_connected()`.

## Extension source policy
- Primary source: `oclaw/extensions/`
- Legacy root `extensions/` has been merged into `oclaw/extensions/` and removed.

## Prompt and skills policy
- Role context is loaded from `oclaw/runtime/workspaces/*`.
- Skills root priority:
  1. `AIA_SKILLS_ROOT`
  2. `oclaw/runtime/skills`
  3. `skills/` (legacy fallback)

