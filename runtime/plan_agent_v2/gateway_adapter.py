from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .adapter import PlanAgentV2Decision, evaluate_for_expert_mode
from .switch import should_route_to_v2
from runtime.types import StandardMessage


@dataclass(frozen=True)
class GatewayPlanV2AdapterOutput:
    used_v2: bool
    decision: PlanAgentV2Decision | None


def evaluate_gateway_expert_turn_shadow(
    *,
    store: Any,
    msg: StandardMessage,
    lang: str,
    interaction_mode: str,
    requested_specialist: str,
    execution_mode: str = "",
    base_system_prompt: str,
    force_flag: bool = False,
    trace_id: str | None = None,
    parent_span_id: str | None = None,
) -> GatewayPlanV2AdapterOutput:
    if not should_route_to_v2(store=store, interaction_mode=interaction_mode, force_flag=force_flag):
        return GatewayPlanV2AdapterOutput(used_v2=False, decision=None)
    meta = msg.metadata if isinstance(msg.metadata, dict) else {}
    if "plan_agent_version" in meta:
        if str(meta.get("plan_agent_version") or "").strip().lower() != "v2":
            return GatewayPlanV2AdapterOutput(used_v2=False, decision=None)
    eff_mode = str(execution_mode or "").strip().lower()
    if eff_mode not in {"agent", "plan"}:
        eff_mode = "plan" if force_flag else "agent"
    dec = evaluate_for_expert_mode(
        store=store,
        session_id=str(msg.session_id or ""),
        lang=lang,
        requested_specialist=requested_specialist,
        user_text=str(msg.text or ""),
        execution_mode=eff_mode,
        base_system_prompt=base_system_prompt,
        trace_id=trace_id,
        parent_span_id=parent_span_id,
    )
    return GatewayPlanV2AdapterOutput(used_v2=True, decision=dec)


__all__ = ["GatewayPlanV2AdapterOutput", "evaluate_gateway_expert_turn_shadow"]

