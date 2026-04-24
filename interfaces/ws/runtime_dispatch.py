from __future__ import annotations

from typing import Any


async def dispatch_connected(conn: Any, req_id: str, method: str, params: Any) -> None:
    if await conn._dispatch_via_server_methods(req_id=req_id, method=method, params=params):
        return
    await conn.send_res(req_id, ok=False, error=conn._error_shape("INVALID_REQUEST", f"unknown method: {method}"))


__all__ = ["dispatch_connected"]

