from __future__ import annotations

from typing import Any


async def close_ws(conn: Any, code: int = 1000, reason: str = "done") -> None:
    try:
        await conn.ws.close(code=code, reason=reason)
    except Exception:
        pass


async def run_connection_loop(conn: Any) -> None:
    if hasattr(conn, "validate_origin") and not conn.validate_origin():
        await close_ws(conn, 1008, "origin not allowed")
        return
    await conn.ws.accept()
    await conn.send_event("connect.challenge", {"nonce": conn.connect_nonce, "ts": conn._now_ms()})
    while True:
        frame = await conn._recv_frame(preauth=not conn.connected)
        if frame is None:
            return
        if frame.get("type") != "req":
            await conn.send_res(
                str(frame.get("id") or "invalid"),
                ok=False,
                error=conn._error_shape("INVALID_REQUEST", "expected req frame"),
            )
            if not conn.connected:
                await close_ws(conn, 1008, "invalid handshake")
                return
            continue
        req_id = str(frame.get("id") or "invalid")
        method = str(frame.get("method") or "")
        params = frame.get("params")
        if not conn.connected:
            await conn._handle_connect(req_id, method, params)
            if conn.handshake_failed:
                await close_ws(conn, 1008, "invalid handshake")
                return
            continue
        await conn._dispatch_connected(req_id, method, params)


__all__ = ["run_connection_loop", "close_ws"]

