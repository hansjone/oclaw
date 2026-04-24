from __future__ import annotations

import time
from typing import Any

from .shared_types import GatewayRequestHandlers
from .validation import error_shape

MODEL_AUTH_STATUS_NEVER_LOADED = 0
CACHE_TTL_MS = 60_000
_cached: dict[str, Any] | None = None


def invalidate_model_auth_status_cache() -> None:
    global _cached
    _cached = None


def _now_ms() -> int:
    return int(time.time() * 1000)


def _ok(respond, payload: Any, meta: dict[str, Any] | None = None) -> None:
    if callable(respond):
        respond(True, payload, None, meta or None)


def _unavailable(respond, message: str) -> None:
    if callable(respond):
        respond(False, None, error_shape("UNAVAILABLE", message), None)


def _normalize_profile_type(v: Any) -> str:
    if isinstance(v, str) and v in {"oauth", "token", "api_key"}:
        return v
    return "api_key"


def _build_expiry(remaining_ms: Any, expires_at: Any) -> dict[str, Any] | None:
    if not isinstance(expires_at, (int, float)) or not isinstance(remaining_ms, (int, float)):
        return None
    rm = int(remaining_ms)
    if rm >= 86_400_000:
        label = f"{rm // 86_400_000}d"
    elif rm >= 3_600_000:
        label = f"{rm // 3_600_000}h"
    else:
        label = f"{max(0, rm // 60_000)}m"
    return {"at": int(expires_at), "remainingMs": rm, "label": label}


def _map_provider(item: dict[str, Any]) -> dict[str, Any]:
    provider = str(item.get("provider") or "")
    profiles_raw = item.get("profiles")
    profiles: list[dict[str, Any]] = []
    if isinstance(profiles_raw, list):
        for p in profiles_raw:
            if not isinstance(p, dict):
                continue
            expiry = _build_expiry(p.get("remainingMs"), p.get("expiresAt"))
            prof = {
                "profileId": str(p.get("profileId") or ""),
                "type": _normalize_profile_type(p.get("type")),
                "status": str(p.get("status") or "missing"),
            }
            if expiry is not None:
                prof["expiry"] = expiry
            profiles.append(prof)

    expiry = _build_expiry(item.get("remainingMs"), item.get("expiresAt"))
    out = {
        "provider": provider,
        "displayName": str(item.get("displayName") or provider),
        "status": str(item.get("status") or "missing"),
        "profiles": profiles,
    }
    if expiry is not None:
        out["expiry"] = expiry
    usage = item.get("usage")
    if isinstance(usage, dict):
        windows = usage.get("windows")
        plan = usage.get("plan")
        out["usage"] = {
            "windows": windows if isinstance(windows, list) else [],
            "plan": str(plan) if isinstance(plan, str) else None,
        }
    return out


def _models_auth_status_handler(opts: dict[str, Any]) -> None:
    global _cached
    params = opts.get("params")
    respond = opts.get("respond")
    context = opts.get("context")
    if params is not None and not isinstance(params, dict):
        _unavailable(respond, "invalid models.authStatus params")
        return

    now = _now_ms()
    bypass_cache = bool((params or {}).get("refresh")) if isinstance(params, dict) else False
    if not bypass_cache and _cached is not None:
        cached_ts = int(_cached.get("ts") or 0)
        if now - cached_ts < CACHE_TTL_MS:
            _ok(respond, _cached["result"], {"cached": True})
            return

    load_auth = context.get("load_models_auth_status") if isinstance(context, dict) else None
    try:
        providers: list[dict[str, Any]] = []
        if callable(load_auth):
            raw = load_auth()
            if isinstance(raw, dict):
                providers_raw = raw.get("providers")
                if isinstance(providers_raw, list):
                    providers = [_map_provider(x) for x in providers_raw if isinstance(x, dict)]
            elif isinstance(raw, list):
                providers = [_map_provider(x) for x in raw if isinstance(x, dict)]
        result = {"ts": now, "providers": providers}
        _cached = {"ts": now, "result": result}
        _ok(respond, result)
    except Exception as exc:
        _unavailable(respond, str(exc))


models_auth_status_handlers: GatewayRequestHandlers = {
    "models.authStatus": _models_auth_status_handler,
}

