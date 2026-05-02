# Plan Agent V2 (Shadow) Design

## Goal
- Build a complete plan/agent pipeline in shadow mode first.
- Keep legacy runtime path unchanged until final one-shot cutover.
- Support instant rollback via a single feature switch.

## Scope
- Target only `interaction_mode=expert`.
- `interaction_mode=comprehensive` remains on legacy path.
- Current implementation is dry-run/shadow ready, not wired into gateway production flow.

## Runtime Components
- Package root: `runtime/plan_agent_v2/`
  - `models.py`: state model (`PlanAgentStateV2`)
  - `state_store.py`: session state persistence
  - `manager.py`: plan lifecycle (`enter/confirm/exit`)
  - `tool_policy.py`: plan-mode tool filtering policy
  - `prompt_injector.py`: plan-mode and approved-plan prompt injection
  - `tool_specs.py`: shadow plan tools (`enter_plan_mode_v2`, `exit_plan_mode_v2`)
  - `switch.py`: feature switch and routing predicate
  - `adapter.py`: expert-mode plan decision logic
  - `gateway_adapter.py`: gateway-side shadow adapter
  - `trace.py`: plan events trace helper
  - `compat.py`: legacy result-shape compatibility helpers

## Legacy Compatibility
- Flat module paths are still available and now forward to package modules:
  - `runtime/plan_agent_v2_*.py` -> `runtime/plan_agent_v2/*`
- This prevents existing imports from breaking during migration.

## Session State Contract
- Stored under key:
  - `AIA_PLAN_AGENT_V2_STATE:<session_id>`
- Serialized JSON fields:
  - `mode`: `normal|plan`
  - `owner_specialist`
  - `plan_id`
  - `plan_path`
  - `plan_content`
  - `plan_confirmed`
  - `entered_at_ms`
  - `updated_at_ms`

## Feature Switches
- `AIA_EXPERT_PLAN_AGENT_V2_ENABLED`
  - default: off
  - effect: allow expert path to route to shadow v2 when wired
- `AIA_EXPERT_PLAN_FILE_DIR`
  - optional plan file root override
- `AIA_EXPERT_PLAN_CONFIRM_STRATEGY`
  - `strict` (default): confirmation in `plan` mode is blocked until user switches to `agent`
  - `auto`: confirmation in `plan` mode auto-switches to execution
  - `off`: disable confirmation-mode gate (same confirm behavior as `auto`)

## Admin API Mode Fields
- `GET /admin/api/chat/sessions/{session_id}/mode`
  - now returns `confirm_strategy` together with `interaction_mode/specialist/memory_mode/execution_mode`.
- `POST /admin/api/chat/sessions/{session_id}/mode`
  - accepts optional `confirm_strategy` (`strict|auto|off`)
  - persists per-user and per-session mode settings
  - mirrors to runtime key `AIA_EXPERT_PLAN_CONFIRM_STRATEGY` for immediate effect in expert v2 turns

## Routing Contract (Shadow)
- Predicate:
  - `should_route_to_v2(store, interaction_mode, force_flag=False)`
- Rules:
  - non-expert mode: always false
  - expert + `force_flag=True`: true
  - expert + feature on: true
  - otherwise: false

## Adapter Outputs
- `evaluate_for_expert_mode(...)` returns:
  - `action`: `enter_plan|stay_plan|run_agent`
  - `reply_text`
  - `plan_state`
  - `system_prompt_override` (set on `run_agent`)

## Trace Events
- Emitted by `emit_plan_agent_v2_trace(...)`:
  - `plan_mode_entered`
  - `plan_mode_active`
  - `plan_mode_confirmed`

## Tests
- Shadow core tests:
  - `tests/test_plan_agent_v2_shadow.py`
- Gateway dry-run comparison tests:
  - `tests/test_plan_agent_v2_gateway_dryrun.py`

## Cutover Plan (Later, Not Yet Applied)
- Add one gateway branch:
  - if `should_route_to_v2(...)` then call `evaluate_gateway_expert_turn_shadow(...)`
  - else keep legacy path
- Keep cutover in one commit for easy rollback.

## Rollback
- Runtime rollback:
  - set `AIA_EXPERT_PLAN_AGENT_V2_ENABLED=false`
- Code rollback:
  - revert only gateway branch commit; shadow modules can remain dormant.

