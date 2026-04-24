from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _normalize_optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    s = value.strip()
    return s or None


@dataclass(frozen=True)
class RestartDeliveryContext:
    channel: str | None = None
    to: str | None = None
    account_id: str | None = None


def _parse_restart_delivery_context(params: Any) -> tuple[RestartDeliveryContext | None, str | None]:
    raw = params.get("deliveryContext") if isinstance(params, dict) else None
    if not isinstance(raw, dict):
        return (None, None)
    channel = _normalize_optional_string(raw.get("channel"))
    to = _normalize_optional_string(raw.get("to"))
    account_id = _normalize_optional_string(raw.get("accountId"))
    ctx = RestartDeliveryContext(channel=channel, to=to, account_id=account_id)
    normalized_ctx = ctx if (channel or to or account_id) else None
    thread_id_raw = raw.get("threadId")
    if isinstance(thread_id_raw, (int, float)) and thread_id_raw == thread_id_raw:
        thread_id = str(int(thread_id_raw))
    else:
        thread_id = _normalize_optional_string(thread_id_raw)
    return (normalized_ctx, thread_id)


def parse_restart_request_params(params: Any) -> dict[str, Any]:
    session_key = _normalize_optional_string(params.get("sessionKey") if isinstance(params, dict) else None)
    delivery_context, thread_id = _parse_restart_delivery_context(params)
    note = _normalize_optional_string(params.get("note") if isinstance(params, dict) else None)
    restart_delay_raw = params.get("restartDelayMs") if isinstance(params, dict) else None
    restart_delay_ms = None
    if isinstance(restart_delay_raw, (int, float)) and restart_delay_raw == restart_delay_raw:
        restart_delay_ms = max(0, int(restart_delay_raw))
    return {
        "sessionKey": session_key,
        "deliveryContext": delivery_context.__dict__ if delivery_context else None,
        "threadId": thread_id,
        "note": note,
        "restartDelayMs": restart_delay_ms,
    }

