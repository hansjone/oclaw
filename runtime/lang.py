from __future__ import annotations

from typing import Any


def resolve_runtime_lang(*, store: Any | None = None, hint: str | None = None) -> str:
    """Resolve zh/en for agent runtime (WS, worker, HTTP share this helper)."""
    raw = str(hint or "").strip().lower()
    if raw in ("zh", "en"):
        return raw
    if store is not None:
        try:
            v = str(store.get_setting("ui_lang") or "zh").strip().lower()
        except Exception:
            v = "zh"
        if v in ("zh", "en"):
            return v
    return "zh"


__all__ = ["resolve_runtime_lang"]
