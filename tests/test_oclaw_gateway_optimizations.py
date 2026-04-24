from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any


def test_wait_for_agent_job_is_non_blocking_pending(monkeypatch) -> None:
    from oclaw.interfaces.ws import server_methods_bridge as bridge

    class DummyLock:
        def __enter__(self) -> None:
            return None

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    class DummyStore:
        def oclaw_run_get(self, run_id: str) -> None:
            return None

        def get_messages(self, session_id: str, limit: int) -> list[Any]:
            return []

        def list_sessions(self, limit: int, offset: int) -> list[Any]:
            return []

        def get_session(self, session_id: str) -> None:
            return None

    monkeypatch.setattr(bridge, "SqliteStore", lambda _p: DummyStore())
    monkeypatch.setattr(bridge, "db_path", lambda: "dummy.sqlite")

    ctx = bridge.build_gateway_context(
        conn_id="c1",
        subscribed_sessions_changed=False,
        subscribed_message_keys=set(),
        abort_lock=DummyLock(),
        active_run_session={},
        aborted_run_ids=set(),
        run_agent_turn=lambda *a, **k: None,
        normalize_ws_attachments=lambda _a: [],
        validate_relay_share_envelope=lambda _e: (True, "", {}),
        now_ms=lambda: 0,
    )

    out = ctx["wait_for_agent_job"]("rid-1", {})
    assert out["status"] == "pending"
    assert out["runId"] == "rid-1"
    assert out["pollAfterMs"] == 250


def test_turn_runner_emits_delta_only(monkeypatch) -> None:
    from oclaw.interfaces.ws import turn_runner

    @dataclass
    class DummyResult:
        run_id: str = "run-1"
        reply_text: str = ""
        elapsed_ms: int = 10

    class DummyGateway:
        def handle_turn(self, **kwargs: Any) -> DummyResult:
            kwargs["on_token"]("A")
            kwargs["on_token"]("B")
            return DummyResult()

    class DummyStore:
        def get_messages(self, session_id: str, limit: int) -> list[Any]:
            return []

    class DummyLock:
        def __enter__(self) -> None:
            return None

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    class DummyConn:
        def __init__(self) -> None:
            self.auth_ctx = {"tenant_id": "t", "user_id": "u", "username": "n"}
            self._abort_lock = DummyLock()
            self._active_run_session: dict[str, str] = {}
            self._aborted_run_ids: set[str] = set()
            self._is_webchat_client = False
            self._subscribed_sessions_changed = False
            self.chat_calls: list[dict[str, Any]] = []

        async def emit_agent_event(self, **kwargs: Any) -> None:
            return None

        async def emit_chat_event(self, **kwargs: Any) -> None:
            self.chat_calls.append(dict(kwargs))

        async def send_event(self, event: str, payload: Any) -> None:
            return None

        async def send_res(self, *args: Any, **kwargs: Any) -> None:
            return None

    monkeypatch.setattr(turn_runner, "SqliteStore", lambda _p: DummyStore())
    monkeypatch.setattr(turn_runner, "db_path", lambda: "dummy.sqlite")
    monkeypatch.setattr(turn_runner, "OclawGateway", lambda store: DummyGateway())
    monkeypatch.setattr(turn_runner, "build_gateway_executor", lambda *a, **k: object())

    conn = DummyConn()

    asyncio.run(
        turn_runner.run_agent_turn_via_bridge(
            conn=conn,
            req_id="req-1",
            p={"message": "hello"},
            session_id="s1",
            send_response=False,
            normalize_ws_attachments=lambda _a: [],
            validate_relay_share_envelope=lambda _e: (True, "", {}),
            now_ms=lambda: 1,
            error_shape=lambda c, m: {"code": c, "message": m},
        )
    )

    delta_calls = [c for c in conn.chat_calls if c.get("state") == "delta"]
    assert [c.get("delta") for c in delta_calls] == ["A", "B"]
    assert all("message" not in c for c in delta_calls)

