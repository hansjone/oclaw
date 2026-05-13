from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any

from runtime.gateway import OclawGatewayResult
from runtime.plan_agent_v2 import (
    build_shadow_gateway_result,
    evaluate_gateway_expert_turn_shadow,
)
from runtime.types import StandardMessage


@dataclass(frozen=True)
class GatewayCutoverDraftOutput:
    handled: bool
    result: OclawGatewayResult | None
    system_prompt_override: str = ""
    decision_action: str = ""


def maybe_handle_expert_turn_v2_draft(
    *,
    store: Any,
    msg: StandardMessage,
    lang: str,
    interaction_mode: str,
    requested_specialist: str,
    base_system_prompt: str,
    force_flag: bool = False,
) -> GatewayCutoverDraftOutput:
    """Draft-only helper for future gateway cutover.

    Important:
    - This module is intentionally NOT wired into `runtime/gateway.py`.
    - It documents and validates the minimal cutover behavior in isolation.
    """
    t0 = time.perf_counter()
    trace_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())

    shadow = evaluate_gateway_expert_turn_shadow(
        store=store,
        msg=msg,
        lang=lang,
        interaction_mode=interaction_mode,
        requested_specialist=requested_specialist,
        base_system_prompt=base_system_prompt,
        force_flag=force_flag,
        trace_id=trace_id,
        parent_span_id=None,
    )
    if not shadow.used_v2 or shadow.decision is None:
        return GatewayCutoverDraftOutput(handled=False, result=None)

    action = str(shadow.decision.action or "")
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    if action in {"enter_plan", "stay_plan"}:
        row = build_shadow_gateway_result(
            decision=shadow.decision,
            run_id=run_id,
            trace_id=trace_id,
            elapsed_ms=elapsed_ms,
            requested_specialist=requested_specialist,
        )
        result = OclawGatewayResult(**row)
        return GatewayCutoverDraftOutput(
            handled=True,
            result=result,
            decision_action=action,
            system_prompt_override="",
        )

    # run_agent: draft suggests continuing legacy execution with injected prompt.
    return GatewayCutoverDraftOutput(
        handled=False,
        result=None,
        decision_action=action,
        system_prompt_override=str(shadow.decision.system_prompt_override or ""),
    )


__all__ = ["GatewayCutoverDraftOutput", "maybe_handle_expert_turn_v2_draft"]

