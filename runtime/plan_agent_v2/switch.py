from __future__ import annotations

import os
from typing import Any


def _is_truthy(raw: str | None) -> bool:
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on"}


def v2_feature_enabled(*, store: Any | None = None) -> bool:
    # Default off for shadow path safety.
    raw = ""
    try:
        if store is not None:
            raw = str(store.get_setting("AIA_EXPERT_PLAN_AGENT_V2_ENABLED") or "").strip()
    except Exception:
        raw = ""
    if not raw:
        raw = str(os.getenv("AIA_EXPERT_PLAN_AGENT_V2_ENABLED") or "").strip()
    if not raw:
        return False
    return _is_truthy(raw)


def should_route_to_v2(*, store: Any | None, interaction_mode: str, force_flag: bool = False) -> bool:
    if str(interaction_mode or "").strip().lower() != "expert":
        return False
    if force_flag:
        return True
    return v2_feature_enabled(store=store)


__all__ = ["should_route_to_v2", "v2_feature_enabled"]

