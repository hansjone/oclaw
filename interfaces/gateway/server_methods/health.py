from __future__ import annotations

from typing import Any

from .shared_types import GatewayRequestHandlers
from .validation import error_shape

HEALTH_REFRESH_INTERVAL_MS = 5_000
ADMIN_SCOPE = "operator.admin"


def _health_handler(opts: dict[str, Any]) -> Any:
    respond = opts.get("respond")
    context = opts.get("context") or {}
    params = opts.get("params") or {}
    if not callable(respond):
        return None
    wants_probe = bool(params.get("probe") is True)
    get_health_cache = context.get("get_health_cache")
    refresh_health_snapshot = context.get("refresh_health_snapshot")
    now = __import__("time").time() * 1000
    cached = get_health_cache() if callable(get_health_cache) else None
    if (
        not wants_probe
        and isinstance(cached, dict)
        and isinstance(cached.get("ts"), (int, float))
        and now - float(cached["ts"]) < HEALTH_REFRESH_INTERVAL_MS
    ):
        respond(True, cached, None, {"cached": True})
        return None
    try:
        snap = refresh_health_snapshot({"probe": wants_probe}) if callable(refresh_health_snapshot) else {}
        respond(True, snap, None, None)
    except Exception as exc:
        respond(False, None, error_shape("UNAVAILABLE", str(exc)), None)
    return None


def _status_handler(opts: dict[str, Any]) -> Any:
    respond = opts.get("respond")
    client = opts.get("client") or {}
    if not callable(respond):
        return None
    scopes = []
    connect = client.get("connect")
    if isinstance(connect, dict) and isinstance(connect.get("scopes"), list):
        scopes = [str(x) for x in connect.get("scopes", [])]
    status = {
        "includeSensitive": ADMIN_SCOPE in scopes,
        "ok": True,
    }
    respond(True, status, None, None)
    return None


health_handlers: GatewayRequestHandlers = {
    "health": _health_handler,
    "status": _status_handler,
}

