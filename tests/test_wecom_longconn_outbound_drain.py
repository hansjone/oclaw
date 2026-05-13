from __future__ import annotations

import json
import queue
import sys
from types import SimpleNamespace
from typing import Any

import pytest


def test_wecom_longconn_drains_outbound_on_idle_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    # Import module under test.
    import interfaces.channels.wecom.longconn_runner as m

    # Build a fake websocket that raises timeout once, then exits by raising KeyboardInterrupt.
    class _TimeoutOnceWs:
        def __init__(self) -> None:
            self.sent: list[str] = []
            self._recv_calls = 0

        def settimeout(self, _t: float) -> None:
            return None

        def recv(self) -> str:
            self._recv_calls += 1
            if self._recv_calls == 1:
                # Mimic websocket-client exception type used in module.
                raise WebSocketTimeoutException()
            raise KeyboardInterrupt()

        def send(self, data: str) -> None:
            self.sent.append(data)

        def ping(self) -> None:
            return None

        def close(self) -> None:
            return None

    ws = _TimeoutOnceWs()

    class WebSocketTimeoutException(Exception):
        pass

    fake_ws_mod = SimpleNamespace(
        WebSocketTimeoutException=WebSocketTimeoutException,
        create_connection=lambda *_a, **_k: ws,
    )
    monkeypatch.setitem(sys.modules, "websocket", fake_ws_mod)

    # Patch WeComClient to avoid real credentials.
    class _Sender:
        def __init__(self) -> None:
            self.store = SimpleNamespace(
                get_setting=lambda _k: "",
                set_setting=lambda _k, _v: None,
            )

        def get_bot_credentials(self) -> tuple[str, str]:
            return ("bot", "secret")

    sender = _Sender()

    # Patch worker threads/queues by replacing queue.Queue with one we can prefill for outbound only.
    # We do this by monkeypatching the queue constructor used in _run_ws_forever.
    real_queue = queue.Queue
    ctor_count = {"n": 0}

    def _queue_ctor(*args: Any, **kwargs: Any) -> Any:
        ctor_count["n"] += 1
        q = real_queue(*args, **kwargs)
        # Second queue constructed is outbound_q in _run_ws_forever.
        if ctor_count["n"] == 2:
            q.put({"callback_req_id": "r1", "response_url": "", "text": "hello", "raw_rep": {}})
        return q

    monkeypatch.setattr(m.queue, "Queue", _queue_ctor)

    # Run; it should exit cleanly via KeyboardInterrupt from fake ws.recv.
    assert m._run_ws_forever(sender=sender, deliver_outbound=True, use_response_url=False) == 0  # type: ignore[arg-type]

    # Assert that a send happened with expected cmd.
    assert ws.sent, "expected outbound to be sent during idle timeout drain"
    obj = json.loads(ws.sent[-1])
    assert obj.get("cmd") == "aibot_respond_msg"
    assert (obj.get("body") or {}).get("markdown", {}).get("content") == "hello"

