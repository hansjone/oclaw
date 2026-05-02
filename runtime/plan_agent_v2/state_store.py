from __future__ import annotations

import json
import time
from typing import Any

from .models import PLAN_MODE_NORMAL, PlanAgentStateV2


def _state_key(session_id: str) -> str:
    return f"AIA_PLAN_AGENT_V2_STATE:{str(session_id or '').strip()}"


class PlanAgentStateStoreV2:
    def __init__(self, store: Any):
        self._store = store

    def load(self, *, session_id: str) -> PlanAgentStateV2:
        sid = str(session_id or "").strip()
        if not sid:
            return PlanAgentStateV2()
        raw = str(self._store.get_setting(_state_key(sid)) or "").strip()
        if not raw:
            return PlanAgentStateV2()
        try:
            obj = json.loads(raw)
        except Exception:
            return PlanAgentStateV2()
        return PlanAgentStateV2.from_dict(obj if isinstance(obj, dict) else None)

    def save(self, *, session_id: str, state: PlanAgentStateV2) -> PlanAgentStateV2:
        sid = str(session_id or "").strip()
        if not sid:
            return state
        now_ms = int(time.time() * 1000)
        next_state = PlanAgentStateV2(
            mode=state.mode,
            owner_specialist=state.owner_specialist,
            plan_id=state.plan_id,
            plan_path=state.plan_path,
            plan_content=state.plan_content,
            plan_confirmed=bool(state.plan_confirmed),
            entered_at_ms=int(state.entered_at_ms or 0),
            updated_at_ms=now_ms,
            last_user_text_norm=str(state.last_user_text_norm or "").strip().lower(),
            plan_loop_count=int(state.plan_loop_count or 0),
        )
        self._store.set_setting(_state_key(sid), json.dumps(next_state.to_dict(), ensure_ascii=False))
        return next_state

    def reset(self, *, session_id: str) -> PlanAgentStateV2:
        sid = str(session_id or "").strip()
        if not sid:
            return PlanAgentStateV2()
        self._store.delete_setting(_state_key(sid))
        return PlanAgentStateV2(mode=PLAN_MODE_NORMAL)


__all__ = ["PlanAgentStateStoreV2"]

