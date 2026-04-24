from __future__ import annotations

from fastapi import WebSocket

from .runtime import ws_gateway_loop as _runtime_ws_gateway_loop


async def ws_gateway_loop(ws: WebSocket) -> None:
    """WS gateway entrypoint under oclaw interfaces."""
    await _runtime_ws_gateway_loop(ws)


__all__ = ["ws_gateway_loop"]

