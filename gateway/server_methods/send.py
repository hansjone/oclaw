from __future__ import annotations

import asyncio
from typing import Any

from .shared_types import GatewayRequestHandlers
from .telegram_send_normalize import normalize_transport_target_for_channel
from .validation import error_shape


def _bad(respond, message: str) -> None:
    if callable(respond):
        respond(False, None, error_shape("INVALID_REQUEST", message), None)


def _unavailable(respond, message: str, *, meta: dict[str, Any] | None = None) -> None:
    if callable(respond):
        respond(False, None, error_shape("UNAVAILABLE", message), meta or None)


def _ok(respond, payload: dict[str, Any] | None = None, *, meta: dict[str, Any] | None = None) -> None:
    if callable(respond):
        respond(True, payload or {"ok": True}, None, meta or None)


def _normalize_optional_str(value: Any) -> str | None:
    if isinstance(value, str):
        v = value.strip()
        return v or None
    return None


def _normalize_channel(value: Any) -> str | None:
    ch = _normalize_optional_str(value)
    if not ch:
        return None
    lower = ch.lower()
    # TS rejects webchat as internal-only for these endpoints.
    if lower == "webchat":
        return None
    return lower


def _dedupe_get(context: Any, key: str) -> dict[str, Any] | None:
    if not isinstance(context, dict):
        return None
    dedupe = context.get("dedupe")
    if isinstance(dedupe, dict):
        cached = dedupe.get(key)
        return cached if isinstance(cached, dict) else None
    return None


def _dedupe_set_success(context: Any, key: str, payload: Any) -> None:
    if not isinstance(context, dict):
        return
    dedupe = context.get("dedupe")
    if isinstance(dedupe, dict):
        dedupe[key] = {"ok": True, "payload": payload, "error": None}


def _dedupe_set_failure(context: Any, key: str, error: Any) -> None:
    if not isinstance(context, dict):
        return
    dedupe = context.get("dedupe")
    if isinstance(dedupe, dict):
        dedupe[key] = {"ok": False, "payload": None, "error": error}


def _run_maybe_await(value: Any) -> Any:
    """Run coroutine results in a sync handler.

    Gateway handlers in this repo are synchronous today, but some context hooks
    may be authored as async. We support both by executing coroutine results
    when no event loop is running; otherwise we raise to avoid deadlocks.
    """
    if asyncio.iscoroutine(value):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None and loop.is_running():
            raise RuntimeError("async hook used from sync handler while event loop is running")
        return asyncio.run(value)
    return value


def _message_action_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    context = opts.get("context")
    client = opts.get("client")

    if not isinstance(params, dict):
        _bad(respond, "invalid message.action params")
        return

    idem = _normalize_optional_str(params.get("idempotencyKey"))
    if not idem:
        _bad(respond, "invalid message.action params: idempotencyKey required")
        return

    dedupe_key = f"message.action:{idem}"
    cached = _dedupe_get(context, dedupe_key)
    if cached:
        if callable(respond):
            respond(bool(cached.get("ok")), cached.get("payload"), cached.get("error"), {"cached": True})
        return

    channel = _normalize_channel(params.get("channel"))
    if not channel:
        _bad(
            respond,
            "unsupported channel: webchat (internal-only). Use `chat.send` for WebChat UI messages or choose a deliverable channel.",
        )
        return

    action = _normalize_optional_str(params.get("action"))
    if not action:
        _bad(respond, "invalid message.action params: action required")
        return

    action_params = params.get("params")
    if not isinstance(action_params, dict):
        _bad(respond, "invalid message.action params: params must be object")
        return

    # Authorization: we only trust `senderIsOwner` if the caller is already admin-scoped.
    sender_is_owner_wire = params.get("senderIsOwner") is True
    caller_scopes = []
    if isinstance(client, dict):
        connect = client.get("connect")
        if isinstance(connect, dict) and isinstance(connect.get("scopes"), list):
            caller_scopes = [x for x in connect.get("scopes") if isinstance(x, str)]
    caller_is_full_operator = "operator.admin" in caller_scopes
    sender_is_owner = bool(caller_is_full_operator and sender_is_owner_wire)

    dispatch = context.get("dispatch_message_action") if isinstance(context, dict) else None
    if not callable(dispatch):
        payload = {"channel": channel, "action": action, "handled": False}
        _dedupe_set_success(context, dedupe_key, payload)
        _ok(respond, payload, meta={"channel": channel})
        return

    try:
        handled = _run_maybe_await(
            dispatch(
            {
                "channel": channel,
                "action": action,
                "params": action_params,
                "senderIsOwner": sender_is_owner,
                "raw": params,
            }
            )
        )
        payload = handled if isinstance(handled, dict) else {"handled": bool(handled)}
        _dedupe_set_success(context, dedupe_key, payload)
        _ok(respond, payload, meta={"channel": channel})
    except Exception as exc:
        err = error_shape("UNAVAILABLE", str(exc))
        _dedupe_set_failure(context, dedupe_key, err)
        _unavailable(respond, str(exc), meta={"channel": channel})


def _send_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    context = opts.get("context")

    if not isinstance(params, dict):
        _bad(respond, "invalid send params")
        return

    idem = _normalize_optional_str(params.get("idempotencyKey"))
    if not idem:
        _bad(respond, "invalid send params: idempotencyKey required")
        return

    dedupe_key = f"send:{idem}"
    cached = _dedupe_get(context, dedupe_key)
    if cached:
        if callable(respond):
            respond(bool(cached.get("ok")), cached.get("payload"), cached.get("error"), {"cached": True})
        return

    to = _normalize_optional_str(params.get("to")) or ""
    if not to:
        _bad(respond, "invalid send params: to required")
        return

    message = _normalize_optional_str(params.get("message")) or ""
    media_url = _normalize_optional_str(params.get("mediaUrl"))
    media_urls_raw = params.get("mediaUrls")
    media_urls: list[str] = []
    if isinstance(media_urls_raw, list):
        for entry in media_urls_raw:
            v = _normalize_optional_str(entry)
            if v:
                media_urls.append(v)

    if not message and not media_url and not media_urls:
        _bad(respond, "invalid send params: text or media is required")
        return

    channel = _normalize_channel(params.get("channel")) or "auto"
    if channel == "auto":
        # If caller doesn't specify a channel, allow context to choose a default deliverable channel.
        choose = context.get("resolve_default_channel") if isinstance(context, dict) else None
        if callable(choose):
            try:
                chosen = choose()
                channel = _normalize_channel(chosen) or "auto"
            except Exception:
                channel = "auto"
        if channel == "auto":
            channel = "unknown"

    to, channel_extra = normalize_transport_target_for_channel(channel=channel, to=to, params=params)

    deliver = context.get("deliver_outbound") if isinstance(context, dict) else None
    if not callable(deliver):
        payload = {
            "runId": idem,
            "channel": channel,
            "to": to,
            "messageId": f"msg_{idem}",
            **channel_extra,
        }
        _dedupe_set_success(context, dedupe_key, payload)
        _ok(respond, payload, meta={"channel": channel})
        return

    try:
        result = _run_maybe_await(
            deliver(
            {
                "runId": idem,
                "channel": channel,
                "to": to,
                "message": message or None,
                "mediaUrl": media_url,
                "mediaUrls": media_urls,
                **channel_extra,
                "raw": params,
            }
            )
        )
        payload = result if isinstance(result, dict) else {"ok": True}
        if "runId" not in payload:
            payload["runId"] = idem
        if "channel" not in payload:
            payload["channel"] = channel
        _dedupe_set_success(context, dedupe_key, payload)
        _ok(respond, payload, meta={"channel": channel})
    except Exception as exc:
        err = error_shape("UNAVAILABLE", str(exc))
        _dedupe_set_failure(context, dedupe_key, err)
        _unavailable(respond, str(exc), meta={"channel": channel})


send_handlers: GatewayRequestHandlers = {
    "message.action": _message_action_handler,
    "send": _send_handler,
}

