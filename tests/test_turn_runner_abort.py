"""WS turn abort must stop the agent and not emit a full final reply."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest


@dataclass
class DummyResult:
    run_id: str = "run-abort-1"
    reply_text: str = "FULL_REPLY_SHOULD_NOT_EMIT"
    elapsed_ms: int = 10
    turn_uuid: str = "tu-1"
    mode: str = "sync_direct"
    trace_id: str = ""


class DummyLock:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class DummyStore:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    def get_messages(self, session_id: str, limit: int = 200) -> list[Any]:
        return []

    def add_message(self, **kwargs: Any) -> None:
        self.messages.append(dict(kwargs))

    def oclaw_run_get(self, **kwargs: Any) -> None:
        return None

    def get_setting(self, key: str) -> str:
        return ""


class DummyConn:
    def __init__(self) -> None:
        self.auth_ctx = {"tenant_id": "t", "user_id": "u", "username": "n", "lang": "zh"}
        self._abort_lock = DummyLock()
        self._active_run_session: dict[str, str] = {}
        self._aborted_run_ids: set[str] = set()
        self._is_webchat_client = True
        self._subscribed_sessions_changed = False
        self.chat_calls: list[dict[str, Any]] = []
        self.events: list[tuple[str, Any]] = []

    async def emit_agent_event(self, **kwargs: Any) -> None:
        return None

    async def emit_chat_event(self, **kwargs: Any) -> None:
        self.chat_calls.append(dict(kwargs))

    async def send_event(self, event: str, payload: Any) -> None:
        self.events.append((str(event), payload))

    async def send_res(self, *args: Any, **kwargs: Any) -> None:
        return None


def _run_turn(monkeypatch: pytest.MonkeyPatch, *, gateway: Any, conn: DummyConn, run_id: str) -> DummyStore:
    from interfaces.ws import turn_runner

    store = DummyStore()
    monkeypatch.setattr(turn_runner, "SqliteStore", lambda _p: store)
    monkeypatch.setattr(turn_runner, "db_path", lambda: "dummy.sqlite")
    monkeypatch.setattr(turn_runner, "OclawGateway", lambda store: gateway)
    monkeypatch.setattr(turn_runner, "build_gateway_executor", lambda *a, **k: object())
    monkeypatch.setattr(turn_runner, "get_assistant_store", lambda: store)
    monkeypatch.setattr(turn_runner, "persist_assistant_text_if_turn_missing", lambda **k: False)

    asyncio.run(
        turn_runner.run_agent_turn_via_bridge(
            conn=conn,
            req_id="req-1",
            p={"message": "hello", "runId": run_id, "lang": "zh"},
            session_id="s1",
            send_response=False,
            normalize_ws_attachments=lambda _a: [],
            validate_relay_share_envelope=lambda _e: (True, "", {}),
            now_ms=lambda: 1,
            error_shape=lambda c, m: {"code": c, "message": m},
        )
    )
    return store


def test_abort_before_finish_emits_aborted_not_final(monkeypatch: pytest.MonkeyPatch) -> None:
    run_id = "run-abort-1"
    seen_should_stop: list[bool] = []

    class Gateway:
        def handle_turn(self, **kwargs: Any) -> DummyResult:
            assert callable(kwargs.get("should_stop"))
            seen_should_stop.append(bool(kwargs["should_stop"]()))
            return DummyResult(run_id=run_id, reply_text="FULL_REPLY_SHOULD_NOT_EMIT")

    conn = DummyConn()
    conn._aborted_run_ids.add(run_id)
    store = _run_turn(monkeypatch, gateway=Gateway(), conn=conn, run_id=run_id)

    states = [c.get("state") for c in conn.chat_calls]
    assert "aborted" in states
    assert "final" not in states
    assert seen_should_stop == [True]
    assert any("已中断" in str(m.get("content") or "") for m in store.messages)
    assert not any("FULL_REPLY" in str(m.get("content") or "") for m in store.messages)


def test_on_token_raises_when_aborted_mid_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    run_id = "run-abort-2"
    conn = DummyConn()

    class Gateway:
        def handle_turn(self, **kwargs: Any) -> DummyResult:
            on_token = kwargs["on_token"]
            on_token("partial")
            conn._aborted_run_ids.add(run_id)
            with pytest.raises(RuntimeError, match="interrupted"):
                on_token("more")
            raise RuntimeError("generation interrupted by user")

    store = _run_turn(monkeypatch, gateway=Gateway(), conn=conn, run_id=run_id)
    states = [c.get("state") for c in conn.chat_calls]
    assert "aborted" in states
    assert "final" not in states
    assert any("已中断" in str(m.get("content") or "") for m in store.messages)


def test_abort_chat_session_marks_active_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    from interfaces.ws import server_methods_bridge

    monkeypatch.setattr(server_methods_bridge, "get_assistant_store", lambda: DummyStore())
    lock = DummyLock()
    active: dict[str, str] = {"r1": "s1", "r2": "s2"}
    aborted: set[str] = set()

    ctx = server_methods_bridge.build_gateway_context(
        conn_id="c1",
        subscribed_sessions_changed=False,
        subscribed_message_keys=set(),
        abort_lock=lock,
        active_run_session=active,
        aborted_run_ids=aborted,
        run_agent_turn=lambda *a, **k: None,
        normalize_ws_attachments=lambda _a: [],
        validate_relay_share_envelope=lambda _e: (True, "", {}),
        now_ms=lambda: 1,
    )
    assert ctx["abort_chat_session"]("s1") is True
    assert "r1" in aborted
    assert "r2" not in aborted
    assert ctx["abort_chat_run"]("r2") is True
    assert "r2" in aborted
