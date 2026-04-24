from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .shared_types import GatewayRequestHandlers
from .validation import error_shape


def _ok(respond, payload: Any) -> None:
    if callable(respond):
        respond(True, payload, None, None)


def _bad(respond, message: str) -> None:
    if callable(respond):
        respond(False, None, error_shape("INVALID_REQUEST", message), None)


def _normalize_optional_str(v: Any) -> str | None:
    if isinstance(v, str):
        s = v.strip()
        return s or None
    return None


def _read_string_value(v: Any) -> str | None:
    return _normalize_optional_str(v)


def _normalize_lowercase_string_or_empty(v: Any) -> str:
    return str(v or "").strip().lower()


@dataclass
class _PresenceUpdate:
    key: str
    next: dict[str, Any]
    changed_keys: list[str]


def _presence_store(context: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(context, dict):
        return {}
    store = context.get("_system_presence_store")
    if isinstance(store, dict):
        return store
    created: dict[str, dict[str, Any]] = {}
    context["_system_presence_store"] = created
    return created


def _list_system_presence(context: Any) -> list[dict[str, Any]]:
    hook = context.get("list_system_presence") if isinstance(context, dict) else None
    if callable(hook):
        out = hook()
        return out if isinstance(out, list) else []
    store = _presence_store(context)
    return [dict(v) for _, v in sorted(store.items(), key=lambda kv: kv[0])]


def _update_system_presence(context: Any, payload: dict[str, Any]) -> _PresenceUpdate:
    hook = context.get("update_system_presence") if isinstance(context, dict) else None
    if callable(hook):
        raw = hook(payload)
        if isinstance(raw, dict):
            key = str(raw.get("key") or payload.get("deviceId") or "unknown")
            nxt = raw.get("next")
            nxt = dict(nxt) if isinstance(nxt, dict) else dict(payload)
            changed = raw.get("changedKeys")
            changed = list(changed) if isinstance(changed, list) else []
            return _PresenceUpdate(key=key, next=nxt, changed_keys=[str(x) for x in changed if str(x)])

    store = _presence_store(context)
    key = str(payload.get("deviceId") or payload.get("instanceId") or payload.get("host") or "unknown").strip() or "unknown"
    prev = dict(store.get(key) or {})
    nxt = {**prev, **{k: v for k, v in payload.items() if v is not None}}
    changed = [k for k in nxt.keys() if prev.get(k) != nxt.get(k)]
    store[key] = dict(nxt)
    return _PresenceUpdate(key=key, next=nxt, changed_keys=changed)


def _resolve_main_session_key(context: Any) -> str:
    hook = context.get("resolve_main_session_key") if isinstance(context, dict) else None
    if callable(hook):
        try:
            v = hook()
            if isinstance(v, str) and v.strip():
                return v.strip()
        except Exception:
            pass
    return "main"


def _gateway_identity_get_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    context = opts.get("context")
    hook = context.get("load_or_create_device_identity") if isinstance(context, dict) else None
    if callable(hook):
        ident = hook()
        if isinstance(ident, dict):
            _ok(
                respond,
                {
                    "deviceId": str(ident.get("deviceId") or ""),
                    "publicKey": ident.get("publicKey"),
                },
            )
            return
    # Staging fallback: stable-but-non-cryptographic identity.
    _ok(respond, {"deviceId": "dev", "publicKey": "publicKey"})


def _last_heartbeat_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    context = opts.get("context")
    hook = context.get("get_last_heartbeat_event") if isinstance(context, dict) else None
    if callable(hook):
        try:
            _ok(respond, hook())
            return
        except Exception:
            pass
    _ok(respond, None)


def _set_heartbeats_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params") or {}
    context = opts.get("context")
    enabled = params.get("enabled") if isinstance(params, dict) else None
    if not isinstance(enabled, bool):
        _bad(respond, "invalid set-heartbeats params: enabled (boolean) required")
        return
    hook = context.get("set_heartbeats_enabled") if isinstance(context, dict) else None
    if callable(hook):
        try:
            hook(enabled)
        except Exception:
            pass
    _ok(respond, {"ok": True, "enabled": enabled})


def _system_presence_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    context = opts.get("context")
    _ok(respond, _list_system_presence(context))


def _system_event_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params") or {}
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid system-event params")
        return
    text = _normalize_optional_str(params.get("text")) or ""
    if not text:
        _bad(respond, "text required")
        return

    session_key = _resolve_main_session_key(context)
    presence_payload = {
        "text": text,
        "deviceId": _read_string_value(params.get("deviceId")),
        "instanceId": _read_string_value(params.get("instanceId")),
        "host": _read_string_value(params.get("host")),
        "ip": _read_string_value(params.get("ip")),
        "mode": _read_string_value(params.get("mode")),
        "version": _read_string_value(params.get("version")),
        "platform": _read_string_value(params.get("platform")),
        "deviceFamily": _read_string_value(params.get("deviceFamily")),
        "modelIdentifier": _read_string_value(params.get("modelIdentifier")),
        "reason": _read_string_value(params.get("reason")),
    }
    last_input_seconds = params.get("lastInputSeconds")
    if isinstance(last_input_seconds, (int, float)) and float(last_input_seconds) == float(last_input_seconds):
        presence_payload["lastInputSeconds"] = float(last_input_seconds)
    roles = params.get("roles")
    scopes = params.get("scopes")
    tags = params.get("tags")
    if isinstance(roles, list) and all(isinstance(x, str) for x in roles):
        presence_payload["roles"] = roles
    if isinstance(scopes, list) and all(isinstance(x, str) for x in scopes):
        presence_payload["scopes"] = scopes
    if isinstance(tags, list) and all(isinstance(x, str) for x in tags):
        presence_payload["tags"] = tags

    upd = _update_system_presence(context, presence_payload)

    enqueue = context.get("enqueue_system_event") if isinstance(context, dict) else None
    if not callable(enqueue):
        # no-op fallback
        enqueue = lambda *_args, **_kwargs: None  # noqa: E731

    is_node_presence_line = text.startswith("Node:")
    if is_node_presence_line:
        changed = set(upd.changed_keys)
        reason_value = upd.next.get("reason") or presence_payload.get("reason")
        normalized_reason = _normalize_lowercase_string_or_empty(reason_value)
        ignore_reason = normalized_reason.startswith("periodic") or normalized_reason == "heartbeat"
        host_changed = "host" in changed
        ip_changed = "ip" in changed
        version_changed = "version" in changed
        mode_changed = "mode" in changed
        reason_changed = ("reason" in changed) and (not ignore_reason)
        has_changes = host_changed or ip_changed or version_changed or mode_changed or reason_changed
        if has_changes:
            parts: list[str] = []
            if host_changed or ip_changed:
                host_label = _normalize_optional_str(upd.next.get("host")) or "Unknown"
                ip_label = _normalize_optional_str(upd.next.get("ip"))
                parts.append(f"Node: {host_label}{f' ({ip_label})' if ip_label else ''}")
            if version_changed:
                parts.append(f"app {_normalize_optional_str(upd.next.get('version')) or 'unknown'}")
            if mode_changed:
                parts.append(f"mode {_normalize_optional_str(upd.next.get('mode')) or 'unknown'}")
            if reason_changed:
                parts.append(f"reason {_normalize_optional_str(reason_value) or 'event'}")
            delta_text = " · ".join([p for p in parts if p])
            if delta_text:
                enqueue(delta_text, {"sessionKey": session_key, "contextKey": upd.key})
    else:
        enqueue(text, {"sessionKey": session_key})

    broadcast = context.get("broadcast_presence_snapshot") if isinstance(context, dict) else None
    if callable(broadcast):
        try:
            broadcast()
        except Exception:
            pass

    _ok(respond, {"ok": True})


system_handlers: GatewayRequestHandlers = {
    "gateway.identity.get": _gateway_identity_get_handler,
    "last-heartbeat": _last_heartbeat_handler,
    "set-heartbeats": _set_heartbeats_handler,
    "system-presence": _system_presence_handler,
    "system-event": _system_event_handler,
}

