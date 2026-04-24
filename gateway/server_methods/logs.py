from __future__ import annotations

from typing import Any

from .shared_types import GatewayRequestHandlers
from .validation import error_shape


def _read_configured_log_tail(*, cursor: int | None, limit: int | None, max_bytes: int | None) -> dict[str, Any]:
    # Placeholder runtime adapter for Python rewrite stage.
    return {
        "cursor": cursor or 0,
        "lines": [],
        "nextCursor": cursor or 0,
        "limit": limit or 0,
        "maxBytes": max_bytes or 0,
    }


def _validate_logs_tail_params(params: Any) -> bool:
    if not isinstance(params, dict):
        return False
    for key in ("cursor", "limit", "maxBytes"):
        if key in params and not isinstance(params[key], int):
            return False
    return True


def _logs_tail_handler(opts: dict[str, Any]) -> Any:
    respond = opts.get("respond")
    params = opts.get("params")
    if not callable(respond):
        return None
    if not _validate_logs_tail_params(params):
        respond(
            False,
            None,
            error_shape("INVALID_REQUEST", "invalid logs.tail params"),
            None,
        )
        return None
    p = params if isinstance(params, dict) else {}
    try:
        result = _read_configured_log_tail(
            cursor=p.get("cursor"),
            limit=p.get("limit"),
            max_bytes=p.get("maxBytes"),
        )
        respond(True, result, None, None)
    except Exception as exc:
        respond(
            False,
            None,
            error_shape("UNAVAILABLE", f"log read failed: {exc}"),
            None,
        )
    return None


logs_handlers: GatewayRequestHandlers = {
    "logs.tail": _logs_tail_handler,
}

