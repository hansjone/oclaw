from __future__ import annotations

import asyncio
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

import websockets


def _now_ms() -> int:
    return int(time.time() * 1000)


async def _recv_json(ws: websockets.ClientConnection) -> dict[str, Any]:
    raw = await ws.recv()
    if not isinstance(raw, str):
        raw = raw.decode("utf-8", errors="replace")
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise RuntimeError(f"unexpected frame: {type(obj).__name__}")
    return obj


async def _send_req(ws: websockets.ClientConnection, req_id: str, method: str, params: dict[str, Any]) -> None:
    await ws.send(json.dumps({"type": "req", "id": req_id, "method": method, "params": params}, ensure_ascii=False))


async def _recv_res(ws: websockets.ClientConnection, req_id: str, *, timeout_s: float = 30.0) -> dict[str, Any]:
    """Receive frames until we get the response for req_id (ignore events)."""
    deadline = time.time() + float(timeout_s)
    while True:
        if time.time() > deadline:
            raise TimeoutError(f"timeout waiting for res id={req_id}")
        frame = await _recv_json(ws)
        if frame.get("type") == "res" and str(frame.get("id") or "") == str(req_id):
            return frame
        # Ignore events (chat/agent/tick/etc) during sync requests.


async def main() -> None:
    ws_url = "ws://127.0.0.1:8787/ws"
    session_key = f"e2e:{uuid.uuid4().hex[:8]}"
    run_id = f"e2e_{_now_ms()}_{uuid.uuid4().hex[:8]}"

    async with websockets.connect(ws_url, max_size=26_214_400) as ws:
        # server sends connect.challenge first
        frame = await _recv_json(ws)
        if frame.get("type") != "event" or frame.get("event") != "connect.challenge":
            raise RuntimeError(f"expected connect.challenge, got: {frame}")

        # handshake
        await _send_req(
            ws,
            "c1",
            "connect",
            {
                "minProtocol": 3,
                "maxProtocol": 3,
                "client": {
                    "id": "ws-e2e-smoke",
                    "version": "0",
                    "platform": "win32",
                    "mode": "webchat",
                    "instanceId": uuid.uuid4().hex[:12],
                },
                "role": "operator",
                "scopes": [],
            },
        )
        res = await _recv_res(ws, "c1", timeout_s=15.0)
        if res.get("type") != "res" or res.get("id") != "c1" or not bool(res.get("ok")):
            raise RuntimeError(f"connect failed: {res}")

        # create session
        await _send_req(ws, "s1", "sessions.create", {"key": session_key})
        res = await _recv_res(ws, "s1", timeout_s=15.0)
        if res.get("type") != "res" or res.get("id") != "s1" or not bool(res.get("ok")):
            raise RuntimeError(f"sessions.create failed: {res}")

        # run agent in comprehensive mode (gateway will invoke manager internally)
        await _send_req(
            ws,
            "a1",
            "agent",
            {
                "message": "现在几点了？请用一句话回答。",
                "sessionId": session_key,
                "sessionKey": session_key,
                "idempotencyKey": run_id,
                "interaction_mode": "comprehensive",
                "specialist": "generalist",
            },
        )
        res = await _recv_res(ws, "a1", timeout_s=15.0)
        if res.get("type") != "res" or res.get("id") != "a1" or not bool(res.get("ok")):
            raise RuntimeError(f"agent enqueue failed: {res}")

        # poll completion
        final_status = "pending"
        for _ in range(60):
            await _send_req(ws, "w1", "agent.wait", {"runId": run_id})
            w = await _recv_res(ws, "w1", timeout_s=15.0)
            if w.get("type") != "res" or w.get("id") != "w1" or not bool(w.get("ok")):
                raise RuntimeError(f"agent.wait failed: {w}")
            payload = w.get("payload") if isinstance(w.get("payload"), dict) else {}
            status = str(payload.get("status") or "").strip().lower()
            final_status = status or final_status
            if status in {"ok", "error"}:
                break
            await asyncio.sleep(0.25)

        # fetch history
        await _send_req(ws, "h1", "chat.history", {"sessionKey": session_key, "limit": 20})
        h = await _recv_res(ws, "h1", timeout_s=15.0)
        msgs = []
        if isinstance(h.get("payload"), dict):
            msgs = list(h["payload"].get("messages") or [])
        last_assistant = ""
        for m in reversed(msgs):
            if isinstance(m, dict) and str(m.get("role") or "").lower() == "assistant":
                c = m.get("content")
                if isinstance(c, str):
                    last_assistant = c
                elif isinstance(c, list):
                    # Best-effort: join text blocks.
                    parts: list[str] = []
                    for it in c:
                        if isinstance(it, dict) and it.get("type") == "text":
                            parts.append(str(it.get("text") or ""))
                    last_assistant = "".join(parts)
                else:
                    last_assistant = str(c or "")
                break
        print(f"session_key={session_key}")
        print(f"run_id={run_id}")
        print(f"status={final_status}")
        print(f"assistant_reply={last_assistant!r}")

    # DB check: did we record manager_decision?
    db = Path(r"D:\project\chatgpt\oclaw\data\ai_ops.sqlite")
    con = sqlite3.connect(str(db))
    cur = con.cursor()
    try:
        count = int(cur.execute("select count(1) from trace_event where event_type='manager_decision'").fetchone()[0])
    except Exception:
        count = -1
    con.close()
    print(f"manager_decision_count={count}")


if __name__ == "__main__":
    asyncio.run(main())

