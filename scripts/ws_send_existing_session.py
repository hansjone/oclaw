from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any

import websockets


SESSION_ID = "c257a9cc64404152ac2f2b2c0e58b9d8"


async def _recv_json(ws: websockets.ClientConnection) -> dict[str, Any]:
    raw = await ws.recv()
    if not isinstance(raw, str):
        raw = raw.decode("utf-8", errors="replace")
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        return {}
    return obj


async def _recv_res(ws: websockets.ClientConnection, req_id: str, timeout_s: float = 20.0) -> dict[str, Any]:
    end = time.time() + timeout_s
    while time.time() < end:
        f = await _recv_json(ws)
        if f.get("type") == "res" and str(f.get("id") or "") == req_id:
            return f
    raise TimeoutError(req_id)


async def main() -> None:
    run_id = f"manual_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
    async with websockets.connect("ws://127.0.0.1:8787/ws", max_size=26_214_400) as ws:
        await _recv_json(ws)  # connect.challenge
        await ws.send(
            json.dumps(
                {
                    "type": "req",
                    "id": "c1",
                    "method": "connect",
                    "params": {
                        "minProtocol": 3,
                        "maxProtocol": 3,
                        "client": {
                            "id": "ws-manual",
                            "version": "0",
                            "platform": "win32",
                            "mode": "webchat",
                            "instanceId": uuid.uuid4().hex[:8],
                        },
                        "role": "operator",
                        "scopes": [],
                    },
                },
                ensure_ascii=False,
            )
        )
        await _recv_res(ws, "c1")

        await ws.send(
            json.dumps(
                {
                    "type": "req",
                    "id": "a1",
                    "method": "agent",
                    "params": {
                        "message": "现在几点了，1句回答。",
                        "sessionId": SESSION_ID,
                        "sessionKey": SESSION_ID,
                        "idempotencyKey": run_id,
                        "interaction_mode": "comprehensive",
                        "specialist": "generalist",
                    },
                },
                ensure_ascii=False,
            )
        )
        print(await _recv_res(ws, "a1"))
    print("run_id=", run_id)
    print("session_id=", SESSION_ID)


if __name__ == "__main__":
    asyncio.run(main())

