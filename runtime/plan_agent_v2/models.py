from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


PLAN_MODE_NORMAL = "normal"
PLAN_MODE_PLAN = "plan"
_VALID_MODES = {PLAN_MODE_NORMAL, PLAN_MODE_PLAN}


@dataclass(frozen=True)
class PlanAgentStateV2:
    mode: str = PLAN_MODE_NORMAL
    owner_specialist: str = "generalist"
    plan_id: str = ""
    plan_path: str = ""
    plan_content: str = ""
    plan_confirmed: bool = False
    entered_at_ms: int = 0
    updated_at_ms: int = 0
    last_user_text_norm: str = ""
    plan_loop_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(raw: dict[str, Any] | None) -> "PlanAgentStateV2":
        obj = raw if isinstance(raw, dict) else {}
        mode = str(obj.get("mode") or PLAN_MODE_NORMAL).strip().lower()
        if mode not in _VALID_MODES:
            mode = PLAN_MODE_NORMAL
        return PlanAgentStateV2(
            mode=mode,
            owner_specialist=str(obj.get("owner_specialist") or "generalist").strip().lower() or "generalist",
            plan_id=str(obj.get("plan_id") or "").strip(),
            plan_path=str(obj.get("plan_path") or "").strip(),
            plan_content=str(obj.get("plan_content") or ""),
            plan_confirmed=bool(obj.get("plan_confirmed")),
            entered_at_ms=int(obj.get("entered_at_ms") or 0),
            updated_at_ms=int(obj.get("updated_at_ms") or 0),
            last_user_text_norm=str(obj.get("last_user_text_norm") or "").strip().lower(),
            plan_loop_count=int(obj.get("plan_loop_count") or 0),
        )


__all__ = ["PLAN_MODE_NORMAL", "PLAN_MODE_PLAN", "PlanAgentStateV2"]

