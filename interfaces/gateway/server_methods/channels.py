from __future__ import annotations

from typing import Any

from .shared_types import GatewayRequestHandlers
from .validation import error_shape


def _validate_channels_status_params(params: Any) -> bool:
    if not isinstance(params, dict):
        return False
    if "probe" in params and params["probe"] is not None and not isinstance(params["probe"], bool):
        return False
    if "timeoutMs" in params and params["timeoutMs"] is not None and not isinstance(params["timeoutMs"], int):
        return False
    return True


def _validate_channels_start_params(params: Any) -> bool:
    return isinstance(params, dict) and isinstance(params.get("channel"), str)


def _validate_channels_logout_params(params: Any) -> bool:
    return isinstance(params, dict) and isinstance(params.get("channel"), str)


def _channels_status_handler(opts: dict[str, Any]) -> Any:
    respond = opts.get("respond")
    params = opts.get("params")
    context = opts.get("context") or {}
    if not callable(respond):
        return None
    if not _validate_channels_status_params(params):
        respond(False, None, error_shape("INVALID_REQUEST", "invalid channels.status params"), None)
        return None
    runtime = context.get("get_runtime_snapshot")() if callable(context.get("get_runtime_snapshot")) else {}
    if not isinstance(runtime, dict):
        runtime = {}
    if "image_generation_providers" not in runtime:
        providers = context.get("image_generation_providers")
        if isinstance(providers, list):
            runtime = {
                **runtime,
                "image_generation_providers": [p for p in providers if isinstance(p, dict)],
            }
    payload = {
        "ts": 0,
        "channels": {},
        "channelAccounts": {},
        "runtime": runtime,
    }
    respond(True, payload, None, None)
    return None


def _channels_start_handler(opts: dict[str, Any]) -> Any:
    respond = opts.get("respond")
    params = opts.get("params") or {}
    context = opts.get("context") or {}
    if not callable(respond):
        return None
    if not _validate_channels_start_params(params):
        respond(False, None, error_shape("INVALID_REQUEST", "invalid channels.start params"), None)
        return None
    channel = str(params.get("channel") or "").strip()
    account_id = str(params.get("accountId") or "").strip() or "default"
    try:
        start = context.get("start_channel")
        if callable(start):
            start(channel, account_id)
        respond(True, {"channel": channel, "accountId": account_id, "started": True}, None, None)
    except Exception as exc:
        respond(False, None, error_shape("UNAVAILABLE", str(exc)), None)
    return None


def _channels_logout_handler(opts: dict[str, Any]) -> Any:
    respond = opts.get("respond")
    params = opts.get("params") or {}
    context = opts.get("context") or {}
    if not callable(respond):
        return None
    if not _validate_channels_logout_params(params):
        respond(False, None, error_shape("INVALID_REQUEST", "invalid channels.logout params"), None)
        return None
    channel = str(params.get("channel") or "").strip()
    account_id = str(params.get("accountId") or "").strip() or "default"
    try:
        stop = context.get("stop_channel")
        if callable(stop):
            stop(channel, account_id)
        mark = context.get("mark_channel_logged_out")
        if callable(mark):
            mark(channel, True, account_id)
        respond(True, {"channel": channel, "accountId": account_id, "cleared": True}, None, None)
    except Exception as exc:
        respond(False, None, error_shape("UNAVAILABLE", str(exc)), None)
    return None


channels_handlers: GatewayRequestHandlers = {
    "channels.status": _channels_status_handler,
    "channels.start": _channels_start_handler,
    "channels.logout": _channels_logout_handler,
}

