from __future__ import annotations

from typing import Any

from .adapter import PlanAgentV2Decision
from runtime.gateway import OclawGatewayResult


def legacy_gateway_result_keys() -> set[str]:
    return set(OclawGatewayResult.__dataclass_fields__.keys())


def build_shadow_gateway_result(
    *,
    decision: PlanAgentV2Decision,
    run_id: str,
    trace_id: str,
    elapsed_ms: int,
    requested_specialist: str,
) -> dict[str, Any]:
    return {
        "run_id": str(run_id),
        "reply_text": str(decision.reply_text or ""),
        "trace_id": str(trace_id),
        "elapsed_ms": int(elapsed_ms),
        "mode": "sync_direct",
        "task_id": None,
        "selected_specialist": str((decision.plan_state or {}).get("owner_specialist") or requested_specialist or "generalist"),
        "interaction_mode": "expert",
        "dispatch_reason": f"plan_agent_v2:{decision.action}",
        "manager_selected_specialist": str((decision.plan_state or {}).get("owner_specialist") or requested_specialist or "generalist"),
        "requested_specialist": str(requested_specialist or "generalist"),
        "dynamic_agent_used": False,
        "dynamic_agent_name": "",
        "relay_pointer_count": 0,
        "relay_envelope_present": False,
        "relay_envelope_pointer_count": 0,
        "relay_ttl_turn_count": 0,
        "relay_ttl_session_count": 0,
        "relay_ttl_keep_count": 0,
    }


__all__ = ["build_shadow_gateway_result", "legacy_gateway_result_keys"]

