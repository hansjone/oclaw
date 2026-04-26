from __future__ import annotations

import json
from typing import Any

from starlette.websockets import WebSocketState


def _ws_is_disconnected(conn: Any) -> bool:
    ws = getattr(conn, "ws", None)
    if ws is None:
        return True
    state = getattr(ws, "application_state", None)
    if state == WebSocketState.DISCONNECTED:
        return True
    state = getattr(ws, "client_state", None)
    if state == WebSocketState.DISCONNECTED:
        return True
    return False


async def _safe_send_text(conn: Any, text: str) -> None:
    if _ws_is_disconnected(conn):
        return
    try:
        await conn.ws.send_text(text)
    except Exception as e:
        msg = str(e or "")
        if "Unexpected ASGI message 'websocket.send'" in msg or "response already completed" in msg:
            return
        raise


async def send_res(conn: Any, req_id: str, *, ok: bool, payload: Any | None = None, error: Any | None = None) -> None:
    frame: dict[str, Any] = {"type": "res", "id": str(req_id or "invalid"), "ok": bool(ok)}
    if payload is not None:
        frame["payload"] = payload
    if error is not None:
        frame["error"] = error
    await _safe_send_text(conn, json.dumps(frame, ensure_ascii=False))


async def send_event(conn: Any, event: str, payload: Any | None = None) -> None:
    if _ws_is_disconnected(conn):
        return
    conn.seq += 1
    frame: dict[str, Any] = {"type": "event", "event": str(event or "event"), "seq": int(conn.seq)}
    if payload is not None:
        frame["payload"] = payload
    await _safe_send_text(conn, json.dumps(frame, ensure_ascii=False))


async def emit_agent_event(conn: Any, *, run_id: str, stream: str, data: dict[str, Any], now_ms: int) -> None:
    payload = {"runId": str(run_id), "seq": int(conn.seq + 1), "stream": str(stream), "ts": int(now_ms), "data": dict(data or {})}
    await send_event(conn, "agent.event", payload)


async def emit_chat_event(
    conn: Any,
    *,
    run_id: str,
    state: str,
    delta: str = "",
    reply: str = "",
    error: str = "",
    message: dict[str, Any] | None = None,
    session_key: str | None = None,
    seq: int | None = None,
) -> None:
    payload: dict[str, Any] = {"runId": str(run_id), "state": str(state or "")}
    if session_key:
        payload["sessionKey"] = str(session_key)
    if seq is not None:
        payload["seq"] = int(seq)
    if delta:
        payload["message"] = {"role": "assistant", "content": [{"type": "text", "text": str(delta)}]}
    elif reply and message is None:
        payload["message"] = {"role": "assistant", "content": [{"type": "text", "text": str(reply)}]}
    if error:
        payload["errorMessage"] = str(error)
    if message is not None:
        payload["message"] = message
    await send_event(conn, "chat", payload)


__all__ = ["send_res", "send_event", "emit_agent_event", "emit_chat_event"]

