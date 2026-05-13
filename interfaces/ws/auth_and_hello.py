from __future__ import annotations

import hashlib
import os
from typing import Any

from svc.config.paths import db_path
from svc.persistence.sqlite_store import SqliteStore


def build_hello_ok_payload(
    *,
    conn_id: str,
    started_at_ms: int,
    role: str,
    scopes: list[str],
    protocol_version: int,
    methods: list[str],
    max_payload_bytes: int,
    max_buffered_bytes: int,
    tick_interval_ms: int,
    now_ms: int,
) -> dict[str, Any]:
    return {
        "type": "hello-ok",
        "protocol": int(protocol_version),
        "server": {"version": str(os.getenv("OCLAW_VERSION") or "0.1"), "connId": str(conn_id)},
        "features": {
            "methods": list(methods),
            "events": ["connect.challenge", "chat", "session.message", "session.tool", "sessions.changed", "agent.event", "tick", "shutdown"],
        },
        "snapshot": {
            "presence": [],
            "health": {},
            "stateVersion": {"presence": 0, "health": 0},
            "uptimeMs": max(0, int(now_ms) - int(started_at_ms or now_ms)),
        },
        "policy": {"maxPayload": int(max_payload_bytes), "maxBufferedBytes": int(max_buffered_bytes), "tickIntervalMs": int(tick_interval_ms)},
        "auth": {"role": str(role or "operator"), "scopes": list(scopes or [])},
    }


def resolve_ws_auth(connect_params: dict[str, Any] | None) -> dict[str, Any]:
    p = connect_params if isinstance(connect_params, dict) else {}
    auth = p.get("auth") if isinstance(p.get("auth"), dict) else {}
    token = str(auth.get("token") or "").strip()
    device_token = str(auth.get("deviceToken") or "").strip()
    bootstrap_token = str(auth.get("bootstrapToken") or "").strip()
    if not token and (device_token or bootstrap_token):
        token = device_token or bootstrap_token
    if not token:
        return {}
    store = SqliteStore(db_path())
    token_hash = hashlib.sha256(token.encode("utf-8", errors="ignore")).hexdigest()
    session = store.get_auth_session(session_token_hash=token_hash)
    if not session or session.get("revoked_at"):
        return {}
    user = store.get_user_by_id(tenant_id=str(session.get("tenant_id") or ""), user_id=str(session.get("user_id") or ""))
    if not user or not bool(user.get("is_active")):
        return {}
    return {
        "tenant_id": str(user.get("tenant_id") or ""),
        "user_id": str(user.get("id") or ""),
        "username": str(user.get("username") or ""),
        "role": str(user.get("role") or "member"),
    }


__all__ = ["build_hello_ok_payload", "resolve_ws_auth"]

