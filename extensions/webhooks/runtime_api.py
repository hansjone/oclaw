from __future__ import annotations

from typing import Any


WEBHOOK_RATE_LIMIT_DEFAULTS: dict[str, int] = {
    "window_ms": 60_000,
    "max_requests": 120,
    "max_tracked_keys": 20_000,
}

WEBHOOK_IN_FLIGHT_DEFAULTS: dict[str, int] = {
    "max_in_flight_per_key": 8,
    "max_tracked_keys": 20_000,
}


def normalize_webhook_path(path: str) -> str:
    p = str(path or "").strip()
    if not p:
        raise ValueError("webhook path is required")
    if not p.startswith("/"):
        p = "/" + p
    while "//" in p:
        p = p.replace("//", "/")
    return p.rstrip("/") or "/"


def resolve_configured_secret_input_string(*, value: Any) -> str | None:
    # Python 重写版先支持直传字符串；ref 由上层配置系统扩展。
    if isinstance(value, str):
        s = value.strip()
        return s or None
    return None

