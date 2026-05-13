from __future__ import annotations

import asyncio
import json
from typing import Any

from starlette.websockets import WebSocketDisconnect

from interfaces.ws.common import WS_REQUIRE_AUTH


async def recv_frame(
    *,
    conn: Any,
    preauth: bool,
    handshake_timeout_ms: int,
    validate_or_errors: Any,
    format_validation_errors: Any,
    error_shape: Any,
) -> dict[str, Any] | None:
    try:
        if preauth:
            raw = await asyncio.wait_for(conn.ws.receive_text(), timeout=handshake_timeout_ms / 1000.0)
        else:
            raw = await conn.ws.receive_text()
    except asyncio.TimeoutError:
        conn.handshake_failed = True
        return None
    except WebSocketDisconnect:
        return None
    try:
        frame = json.loads(raw)
    except Exception:
        await conn.send_res("invalid", ok=False, error=error_shape("INVALID_REQUEST", "invalid json"))
        if preauth:
            conn.handshake_failed = True
        return {}
    frame_errs = validate_or_errors(conn.schemas.frame, frame)
    if frame_errs:
        fid = str(frame.get("id") or "invalid") if isinstance(frame, dict) else "invalid"
        await conn.send_res(
            fid,
            ok=False,
            error=error_shape("INVALID_REQUEST", f"invalid frame: {format_validation_errors(frame_errs)}"),
        )
        if preauth:
            conn.handshake_failed = True
        return {}
    return frame if isinstance(frame, dict) else {}


async def handle_connect(
    *,
    conn: Any,
    req_id: str,
    method: str,
    params: Any,
    protocol_version: int,
    validate_or_errors: Any,
    format_validation_errors: Any,
    error_shape: Any,
) -> None:
    if method != "connect":
        await conn.send_res(req_id, ok=False, error=error_shape("INVALID_REQUEST", "first request must be connect"))
        conn.handshake_failed = True
        return
    p_errs = validate_or_errors(conn.schemas.connect_params, params)
    if p_errs:
        await conn.send_res(
            req_id,
            ok=False,
            error=error_shape("INVALID_REQUEST", f"invalid connect params: {format_validation_errors(p_errs)}"),
        )
        conn.handshake_failed = True
        return
    p = dict(params or {})
    device = p.get("device") if isinstance(p.get("device"), dict) else None
    if device is not None:
        nonce = str(device.get("nonce") or "").strip()
        if not nonce or nonce != conn.connect_nonce:
            await conn.send_res(
                req_id,
                ok=False,
                error=error_shape("INVALID_REQUEST", "device nonce mismatch", details={"code": "DEVICE_NONCE_MISMATCH"}),
            )
            conn.handshake_failed = True
            return
    min_protocol = int(p.get("minProtocol") or 0)
    max_protocol = int(p.get("maxProtocol") or 0)
    if max_protocol < protocol_version or min_protocol > protocol_version:
        await conn.send_res(
            req_id,
            ok=False,
            error=error_shape("INVALID_REQUEST", "protocol mismatch", details={"expectedProtocol": protocol_version}),
        )
        conn.handshake_failed = True
        return
    conn.connected = True
    conn.client_meta = dict(params or {})
    try:
        c = (conn.client_meta or {}).get("client") if isinstance((conn.client_meta or {}).get("client"), dict) else {}
        mode = str(c.get("mode") or "").strip().lower()
        cid = str(c.get("id") or "").strip().lower()
        conn._is_webchat_client = mode == "webchat" or cid in ("webchat-ui", "webchat", "control-ui-webchat")
    except Exception:
        conn._is_webchat_client = False
    conn.role = str((params or {}).get("role") or "operator")
    conn.scopes = list((params or {}).get("scopes") or [])
    conn.auth_ctx = conn.resolve_ws_auth(params)
    auth = p.get("auth") if isinstance(p.get("auth"), dict) else {}
    auth_provided = bool(
        str(auth.get("token") or "").strip()
        or str(auth.get("password") or "").strip()
        or str(auth.get("bootstrapToken") or "").strip()
        or str(auth.get("deviceToken") or "").strip()
    )
    if not conn.auth_ctx and (WS_REQUIRE_AUTH or auth_provided):
        await conn.send_res(
            req_id,
            ok=False,
            error=error_shape("UNAUTHORIZED", "unauthorized", details={"code": "AUTH_UNAUTHORIZED"}),
        )
        conn.handshake_failed = True
        if hasattr(conn, "mark_handshake"):
            conn.mark_handshake(ok=False)
        return
    if conn.auth_ctx:
        conn.role = str(conn.auth_ctx.get("role") or "member")
        conn.scopes = [f"user:{str(conn.auth_ctx.get('user_id') or '')}"]
    hello = conn.build_hello_ok(params)
    hello_errs = validate_or_errors(conn.schemas.hello_ok, hello)
    if hello_errs:
        await conn.send_res(
            req_id,
            ok=False,
            error=error_shape("UNAVAILABLE", f"server hello-ok schema mismatch: {format_validation_errors(hello_errs)}"),
        )
        conn.handshake_failed = True
        return
    await conn.send_res(req_id, ok=True, payload=hello)
    if hasattr(conn, "mark_handshake"):
        conn.mark_handshake(ok=True)
    if hasattr(conn, "replay_events_since"):
        try:
            last_seq = int(p.get("lastSeq") or 0)
        except Exception:
            last_seq = 0
        await conn.replay_events_since(last_seq)


__all__ = ["recv_frame", "handle_connect"]

