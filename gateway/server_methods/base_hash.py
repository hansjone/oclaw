from __future__ import annotations

from typing import Any


def resolve_base_hash_param(params: Any) -> str | None:
    raw = None
    if isinstance(params, dict):
        raw = params.get("baseHash")
    if not isinstance(raw, str):
        return None
    trimmed = raw.strip()
    return trimmed or None

