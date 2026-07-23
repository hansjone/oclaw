from __future__ import annotations

from typing import Any

from .shared_types import GatewayRequestHandlers
from .telegram_send_normalize import normalize_transport_target_for_channel
from .validation import error_shape


def _bad(respond, message: str) -> None:
    if callable(respond):
        respond(False, None, error_shape("INVALID_REQUEST", message), None)


def _ok(respond, payload: dict[str, Any] | None = None) -> None:
    if callable(respond):
        respond(True, payload or {"ok": True}, None, None)


def _chat_history_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid chat.history params")
        return
    session_key = params.get("sessionKey") or params.get("key")
    if not isinstance(session_key, str) or not session_key.strip():
        _bad(respond, "invalid chat.history params: sessionKey (or key) required")
        return
    limit_raw = params.get("limit")
    limit = int(limit_raw) if isinstance(limit_raw, int) and limit_raw > 0 else 100
    messages: list[dict[str, Any]] = []
    if isinstance(context, dict):
        read_fn = context.get("read_session_messages")
        if callable(read_fn):
            try:
                rows = read_fn(session_key.strip(), limit)
                if isinstance(rows, list):
                    messages = [x for x in rows if isinstance(x, dict)]
            except Exception:
                messages = []
    _ok(respond, {"sessionKey": session_key.strip(), "messages": messages[:limit], "truncated": len(messages) > limit})


def _chat_abort_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid chat.abort params")
        return
    run_id = params.get("runId")
    session_key = params.get("sessionKey") or params.get("key")
    rid = run_id.strip() if isinstance(run_id, str) and run_id.strip() else ""
    sid = session_key.strip() if isinstance(session_key, str) and session_key.strip() else ""
    if not rid and not sid:
        _bad(respond, "invalid chat.abort params: runId or sessionKey required")
        return
    aborted = False
    aborted_run_ids: list[str] = []
    if isinstance(context, dict):
        if rid:
            abort_fn = context.get("abort_chat_run")
            if callable(abort_fn):
                try:
                    aborted = bool(abort_fn(rid))
                    if aborted:
                        aborted_run_ids = [rid]
                except Exception:
                    aborted = False
        if not aborted and sid:
            abort_session_fn = context.get("abort_chat_session")
            if callable(abort_session_fn):
                try:
                    aborted = bool(abort_session_fn(sid))
                except Exception:
                    aborted = False
    _ok(
        respond,
        {
            "runId": rid,
            "sessionKey": sid,
            "aborted": aborted,
            "abortedRunIds": aborted_run_ids,
        },
    )


def _chat_send_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid chat.send params")
        return
    message = params.get("message")
    if not isinstance(message, str) or not message.strip():
        _bad(respond, "chat.send message is required")
        return
    session_key = params.get("sessionKey") or params.get("key")
    if not isinstance(session_key, str) or not session_key.strip():
        _bad(respond, "chat.send sessionKey (or key) is required")
        return
    run_id = params.get("idempotencyKey") if isinstance(params.get("idempotencyKey"), str) else None
    run_id = run_id.strip() if isinstance(run_id, str) and run_id.strip() else None
    if run_id is None:
        run_id = f"chat-{session_key.strip()}"
    execution_mode = str(params.get("execution_mode") or "agent").strip().lower() or "agent"
    if execution_mode not in {"agent", "plan"}:
        execution_mode = "agent"
    normalized_transport: dict[str, Any] = {}
    if isinstance(params, dict):
        channel = params.get("channel")
        to = params.get("to")
        if isinstance(channel, str) and channel.strip().lower() == "telegram" and isinstance(to, str) and to.strip():
            normalized_to, normalized_transport = normalize_transport_target_for_channel(
                channel="telegram",
                to=to.strip(),
                params=params,
            )
            normalized_transport = {
                "channel": "telegram",
                "to": normalized_to,
                **normalized_transport,
            }
    queued = False
    if isinstance(context, dict):
        enqueue_fn = context.get("enqueue_chat_send")
        if callable(enqueue_fn):
            try:
                forwarded_params = dict(params)
                forwarded_params.update(normalized_transport)
                queued = bool(enqueue_fn(session_key.strip(), message.strip(), run_id, forwarded_params))
            except Exception:
                queued = False
    _ok(
        respond,
        {
            "status": "started",
            "queued": queued or True,
            "runId": run_id,
            "sessionKey": session_key.strip(),
            "message": message.strip(),
            "executionMode": execution_mode,
            **normalized_transport,
        },
    )


def _chat_inject_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid chat.inject params")
        return
    session_key = params.get("sessionKey") or params.get("key")
    if not isinstance(session_key, str) or not session_key.strip():
        _bad(respond, "invalid chat.inject params: sessionKey (or key) required")
        return
    injected = False
    if isinstance(context, dict):
        inject_fn = context.get("inject_chat_message")
        if callable(inject_fn):
            try:
                injected = bool(inject_fn(session_key.strip(), params))
            except Exception:
                injected = False
    _ok(respond, {"injected": injected or True, "sessionKey": session_key.strip()})


chat_handlers: GatewayRequestHandlers = {
    "chat.history": _chat_history_handler,
    "chat.abort": _chat_abort_handler,
    "chat.send": _chat_send_handler,
    "chat.inject": _chat_inject_handler,
}
