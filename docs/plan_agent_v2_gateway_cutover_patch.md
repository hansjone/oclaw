# Plan Agent V2 Gateway Cutover Draft

## Purpose
- Provide a minimal, reviewable gateway cutover sketch without changing production routing yet.
- Keep existing `runtime/gateway.py` behavior unchanged until explicit cutover approval.

## Draft Helper
- New module:
  - `runtime/plan_agent_v2_gateway_cutover.py`
- Entrypoint:
  - `maybe_handle_expert_turn_v2_draft(...)`

## Draft Behavior
- If v2 shadow is not selected:
  - returns `handled=False`, gateway should continue legacy flow.
- If decision is `enter_plan` or `stay_plan`:
  - returns `handled=True` with an `OclawGatewayResult` built from v2 shadow compatibility mapper.
- If decision is `run_agent`:
  - returns `handled=False` and provides `system_prompt_override`.
  - gateway would continue legacy execution path but with injected approved-plan context.

## Why This Is Safe
- No import or call-site changes in `runtime/gateway.py` yet.
- Feature remains effectively dormant unless future cutover patch wires this helper.
- Existing tests continue to validate legacy and shadow independently.

## Future Minimal Cutover (single commit)
- In `OclawGateway.handle_turn(...)` expert path, add one early branch:
  1) call `maybe_handle_expert_turn_v2_draft(...)`
  2) if `handled=True`, return result immediately
  3) else continue existing flow; if `system_prompt_override` exists, use it as specialist system prompt

## Rollback
- Revert only the gateway wiring commit.
- Keep shadow modules and tests as dormant assets.

