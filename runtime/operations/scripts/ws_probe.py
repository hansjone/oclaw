from __future__ import annotations

import asyncio
import json
import time
import uuid

import websockets


async def main() -> None:
    ws_url = "ws://127.0.0.1:8790/ws"
    t0 = time.time()
    async with websockets.connect(ws_url, open_timeout=5) as ws:
        challenge = json.loads(await ws.recv())
        print("challenge", challenge.get("event"), challenge.get("payload", {}).get("nonce"))
        nonce = challenge.get("payload", {}).get("nonce", "")

        req_id = uuid.uuid4().hex
        await ws.send(
            json.dumps(
                {
                    "type": "req",
                    "id": req_id,
                    "method": "connect",
                    "params": {
                        "minProtocol": 3,
                        "maxProtocol": 3,
                        "client": {"id": "probe", "mode": "cli", "version": "0.0.0", "platform": "cli"},
                        "device": {
                            "id": uuid.uuid4().hex,
                            "publicKey": "dummy",
                            "signature": "dummy",
                            "signedAt": int(time.time() * 1000),
                            "nonce": nonce,
                        },
                    },
                }
            )
        )
        hello = json.loads(await ws.recv())
        print("hello", hello)

        session_key = uuid.uuid4().hex
        req_id2 = uuid.uuid4().hex
        await ws.send(
            json.dumps(
                {
                    "type": "req",
                    "id": req_id2,
                    "method": "chat.send",
                    "params": {
                        "sessionKey": session_key,
                        "idempotencyKey": uuid.uuid4().hex,
                        "message": "hi streaming test",
                    },
                }
            )
        )

        got_delta = False
        first_delta_at: float | None = None
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("type") == "res" and msg.get("id") == req_id2:
                print("chat.send res", msg)
                continue
            if msg.get("type") == "event" and msg.get("event") == "chat":
                st = (msg.get("payload") or {}).get("state")
                if st == "delta":
                    if not got_delta:
                        got_delta = True
                        first_delta_at = time.time() - t0
                if st in ("final", "error"):
                    pl = msg.get("payload") or {}
                    print(
                        "final_state",
                        st,
                        "got_delta",
                        got_delta,
                        "first_delta_at",
                        first_delta_at,
                        "reply_preview",
                        str(pl.get("reply") or "")[:120],
                    )
                    break


if __name__ == "__main__":
    asyncio.run(main())

