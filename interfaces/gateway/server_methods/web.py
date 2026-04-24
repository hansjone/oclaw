from __future__ import annotations

from typing import Any

from .shared_types import GatewayRequestHandlers
from .validation import error_shape


def _ok(respond, payload: Any) -> None:
    if callable(respond):
        respond(True, payload, None, None)


def _bad(respond, message: str) -> None:
    if callable(respond):
        respond(False, None, error_shape("INVALID_REQUEST", message), None)


def _unavailable(respond, message: str) -> None:
    if callable(respond):
        respond(False, None, error_shape("UNAVAILABLE", message), None)


def _norm_str(v: Any) -> str | None:
    if isinstance(v, str):
        s = v.strip()
        return s or None
    return None


def _resolve_provider(context: Any) -> dict[str, Any] | None:
    hook = context.get("resolve_web_login_provider") if isinstance(context, dict) else None
    if callable(hook):
        out = hook()
        if isinstance(out, dict):
            return out
    return None


def _web_login_start_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params")
    respond = opts.get("respond")
    context = opts.get("context")
    if params is not None and not isinstance(params, dict):
        _bad(respond, "invalid web.login.start params")
        return
    p = dict(params or {})
    provider = _resolve_provider(context)
    if not provider:
        _bad(respond, "web login provider is not available")
        return
    start_fn = provider.get("loginWithQrStart")
    if not callable(start_fn):
        _bad(respond, f"web login is not supported by provider {provider.get('id')}")
        return
    account_id = _norm_str(p.get("accountId"))
    try:
        stop_channel = context.get("stopChannel") if isinstance(context, dict) else None
        if callable(stop_channel):
            stop_channel(provider.get("id"), account_id)
        result = start_fn(
            {
                "force": bool(p.get("force")),
                "timeoutMs": p.get("timeoutMs") if isinstance(p.get("timeoutMs"), (int, float)) else None,
                "verbose": bool(p.get("verbose")),
                "accountId": account_id,
            }
        )
        if not isinstance(result, dict):
            result = {}
        connected = bool(result.get("connected"))
        if connected:
            start_channel = context.get("startChannel") if isinstance(context, dict) else None
            if callable(start_channel):
                start_channel(provider.get("id"), account_id)
        _ok(respond, result)
    except Exception as exc:
        _unavailable(respond, str(exc))


def _web_login_wait_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params")
    respond = opts.get("respond")
    context = opts.get("context")
    if params is not None and not isinstance(params, dict):
        _bad(respond, "invalid web.login.wait params")
        return
    p = dict(params or {})
    provider = _resolve_provider(context)
    if not provider:
        _bad(respond, "web login provider is not available")
        return
    wait_fn = provider.get("loginWithQrWait")
    if not callable(wait_fn):
        _bad(respond, f"web login is not supported by provider {provider.get('id')}")
        return
    account_id = _norm_str(p.get("accountId"))
    try:
        result = wait_fn(
            {
                "timeoutMs": p.get("timeoutMs") if isinstance(p.get("timeoutMs"), (int, float)) else None,
                "accountId": account_id,
            }
        )
        if not isinstance(result, dict):
            result = {}
        if bool(result.get("connected")):
            start_channel = context.get("startChannel") if isinstance(context, dict) else None
            if callable(start_channel):
                start_channel(provider.get("id"), account_id)
        _ok(respond, result)
    except Exception as exc:
        _unavailable(respond, str(exc))


web_handlers: GatewayRequestHandlers = {
    "web.login.start": _web_login_start_handler,
    "web.login.wait": _web_login_wait_handler,
}

