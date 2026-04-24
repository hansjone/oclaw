from __future__ import annotations

from typing import Any


def as_record(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def normalize_trimmed_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None

