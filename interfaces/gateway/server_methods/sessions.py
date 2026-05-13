from __future__ import annotations

from typing import Any

from runtime.agents.agent_scope import resolve_default_agent_id

from .shared_types import GatewayRequestHandlers
from .telegram_send_normalize import normalize_transport_target_for_channel
from .validation import error_shape


def _ok(respond, payload: dict[str, Any] | None = None) -> None:
    if callable(respond):
        respond(True, payload or {"ok": True}, None, None)


def _bad(respond, message: str) -> None:
    if callable(respond):
        respond(False, None, error_shape("INVALID_REQUEST", message), None)


def _normalize_session_key(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _extract_session_key(params: Any) -> str | None:
    if not isinstance(params, dict):
        return None
    return _normalize_session_key(params.get("sessionKey")) or _normalize_session_key(params.get("key"))


def _require_session_key(params: Any, respond) -> str | None:
    if not isinstance(params, dict):
        _bad(respond, "params must be object")
        return None
    key = _extract_session_key(params)
    if not key:
        _bad(respond, "sessionKey (or key) is required")
        return None
    return key


def _context_subscribers(context: Any, name: str) -> set[str]:
    if not isinstance(context, dict):
        return set()
    value = context.get(name)
    if isinstance(value, set):
        return value
    created: set[str] = set()
    context[name] = created
    return created


def _sessions_list_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    context = opts.get("context")
    sessions = []
    if isinstance(context, dict):
        list_fn = context.get("list_sessions")
        if callable(list_fn):
            try:
                rows = list_fn()
                if isinstance(rows, list):
                    sessions = [x for x in rows if isinstance(x, dict)]
            except Exception:
                sessions = []
    _ok(respond, {"sessions": sessions, "total": len(sessions)})


def _sessions_subscribe_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    client = opts.get("client") or {}
    context = opts.get("context")
    conn_id = client.get("conn_id") if isinstance(client, dict) else None
    if isinstance(conn_id, str) and conn_id.strip():
        _context_subscribers(context, "session_event_subscribers").add(conn_id.strip())
    _ok(respond, {"subscribed": True, "connId": conn_id})


def _sessions_unsubscribe_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    client = opts.get("client") or {}
    context = opts.get("context")
    conn_id = client.get("conn_id") if isinstance(client, dict) else None
    if isinstance(conn_id, str) and conn_id.strip():
        _context_subscribers(context, "session_event_subscribers").discard(conn_id.strip())
    _ok(respond, {"subscribed": False, "connId": conn_id})


def _sessions_messages_subscribe_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    context = opts.get("context")
    client = opts.get("client") or {}
    key = _require_session_key(params, respond)
    if not key:
        return
    conn_id = client.get("conn_id") if isinstance(client, dict) else None
    if isinstance(conn_id, str) and conn_id.strip() and isinstance(context, dict):
        message_subscribers = context.get("session_message_subscribers")
        if not isinstance(message_subscribers, dict):
            message_subscribers = {}
            context["session_message_subscribers"] = message_subscribers
        bucket = message_subscribers.get(key)
        if not isinstance(bucket, set):
            bucket = set()
            message_subscribers[key] = bucket
        bucket.add(conn_id.strip())
    _ok(respond, {"sessionKey": key, "messagesSubscribed": True, "connId": conn_id})


def _sessions_messages_unsubscribe_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    context = opts.get("context")
    client = opts.get("client") or {}
    key = _require_session_key(params, respond)
    if not key:
        return
    conn_id = client.get("conn_id") if isinstance(client, dict) else None
    if isinstance(conn_id, str) and conn_id.strip() and isinstance(context, dict):
        message_subscribers = context.get("session_message_subscribers")
        if isinstance(message_subscribers, dict):
            bucket = message_subscribers.get(key)
            if isinstance(bucket, set):
                bucket.discard(conn_id.strip())
    _ok(respond, {"sessionKey": key, "messagesSubscribed": False, "connId": conn_id})


def _sessions_preview_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    _ok(respond, {"preview": []})


def _sessions_resolve_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    key = _require_session_key(params, respond)
    if not key:
        return
    _ok(respond, {"sessionKey": key, "resolved": True})


def _sessions_compaction_list_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    _ok(respond, {"checkpoints": []})


def _sessions_compaction_get_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    _ok(respond, {"checkpoint": None})


def _sessions_create_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    context = opts.get("context")
    key = _extract_session_key(params) or "main"
    agent_id = ""
    if isinstance(params, dict):
        agent_id = str(params.get("agentId") or "").strip()
        cfg = params.get("config") if isinstance(params.get("config"), dict) else {}
        if not agent_id and isinstance(cfg, dict) and cfg:
            agent_id = resolve_default_agent_id(cfg)
    if agent_id and ":" not in key:
        key = f"{agent_id}:{key}"
    session = {"sessionKey": key}
    if isinstance(context, dict):
        create_fn = context.get("create_session")
        if callable(create_fn):
            try:
                created = create_fn(key, params if isinstance(params, dict) else {})
                if isinstance(created, dict):
                    session = created
                    key = _normalize_session_key(created.get("sessionKey")) or key
            except Exception:
                pass
    _ok(respond, {"sessionKey": key, "created": True, "session": session})


def _sessions_compaction_branch_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    _ok(respond, {"branched": True})


def _sessions_compaction_restore_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    _ok(respond, {"restored": True})


def _sessions_send_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    context = opts.get("context")
    key = _require_session_key(params, respond)
    if not key:
        return
    message = params.get("message") if isinstance(params, dict) else None
    if not isinstance(message, str) or not message.strip():
        _bad(respond, "message is required")
        return
    payload: dict[str, Any] = {"sent": True, "sessionKey": key, "message": message.strip()}
    if isinstance(params, dict):
        channel = params.get("channel")
        to = params.get("to")
        if isinstance(channel, str) and channel.strip().lower() == "telegram" and isinstance(to, str) and to.strip():
            normalized_to, extra = normalize_transport_target_for_channel(
                channel="telegram",
                to=to.strip(),
                params=params,
            )
            payload.update({"channel": "telegram", "to": normalized_to, **extra})
    if isinstance(context, dict):
        send_fn = context.get("enqueue_session_send")
        if callable(send_fn):
            try:
                out = send_fn(key, message.strip(), dict(params or {}))
                if isinstance(out, dict):
                    payload.update(out)
            except Exception as exc:
                _bad(respond, f"sessions.send failed: {exc}")
                return
    _ok(respond, payload)


def _sessions_steer_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    _ok(respond, {"steered": True})


def _sessions_abort_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    key = _require_session_key(params, respond)
    if not key:
        return
    _ok(respond, {"aborted": True, "sessionKey": key})


def _sessions_patch_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    key = _require_session_key(params, respond)
    if not key:
        return
    _ok(respond, {"patched": True, "sessionKey": key})


def _sessions_reset_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    key = _require_session_key(params, respond)
    if not key:
        return
    _ok(respond, {"reset": True, "sessionKey": key})


def _sessions_delete_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    key = _require_session_key(params, respond)
    if not key:
        return
    _ok(respond, {"deleted": True, "sessionKey": key})


def _sessions_get_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    context = opts.get("context")
    key = _require_session_key(params, respond)
    if not key:
        return
    session: dict[str, Any] = {}
    if isinstance(context, dict):
        get_fn = context.get("get_session")
        if callable(get_fn):
            try:
                loaded = get_fn(key)
                if isinstance(loaded, dict):
                    session = loaded
            except Exception:
                session = {}
    _ok(respond, {"sessionKey": key, "session": session})


def _sessions_compact_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    _ok(respond, {"compacted": True})


sessions_handlers: GatewayRequestHandlers = {
    "sessions.list": _sessions_list_handler,
    "sessions.subscribe": _sessions_subscribe_handler,
    "sessions.unsubscribe": _sessions_unsubscribe_handler,
    "sessions.messages.subscribe": _sessions_messages_subscribe_handler,
    "sessions.messages.unsubscribe": _sessions_messages_unsubscribe_handler,
    "sessions.preview": _sessions_preview_handler,
    "sessions.resolve": _sessions_resolve_handler,
    "sessions.compaction.list": _sessions_compaction_list_handler,
    "sessions.compaction.get": _sessions_compaction_get_handler,
    "sessions.create": _sessions_create_handler,
    "sessions.compaction.branch": _sessions_compaction_branch_handler,
    "sessions.compaction.restore": _sessions_compaction_restore_handler,
    "sessions.send": _sessions_send_handler,
    "sessions.steer": _sessions_steer_handler,
    "sessions.abort": _sessions_abort_handler,
    "sessions.patch": _sessions_patch_handler,
    "sessions.reset": _sessions_reset_handler,
    "sessions.delete": _sessions_delete_handler,
    "sessions.get": _sessions_get_handler,
    "sessions.compact": _sessions_compact_handler,
}
