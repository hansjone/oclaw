from __future__ import annotations

from pathlib import Path

import pytest

from oclaw.openclaw_runtime.agent_core_run import AgentCoreRunInput, run_agent_core
from oclaw.openclaw_runtime.types import StandardMessage
from oclaw.platform.llm.chat_models import StaticTextChatModel
from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.tools.base import ToolRegistry


def _msg(session_id: str, *, metadata: dict | None = None) -> StandardMessage:
    return StandardMessage(
        session_id=session_id,
        tenant_id="t1",
        user_id="u1",
        role="member",
        channel="admin_chat",
        text="hello",
        attachments=[],
        metadata=metadata if isinstance(metadata, dict) else {"tenant_id": "t1", "user_id": "u1"},
    )


def test_agent_core_run_started_trace_payload_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = SqliteStore(str(tmp_path / "trace.sqlite"))
    sess = store.create_session("t")
    events: list[dict] = []
    real_add = store.add_trace_event

    def _wrap(**kwargs: object) -> None:
        events.append(dict(kwargs))
        return real_add(**kwargs)

    monkeypatch.setattr(store, "add_trace_event", _wrap)

    trace_id = "trace-abc"
    run_agent_core(
        store=store,
        data=AgentCoreRunInput(
            msg=_msg(sess.id),
            lang="zh",
            system_prompt="sys",
            model=StaticTextChatModel("done"),
            tools=ToolRegistry([]),
            trace_id=trace_id,
            parent_span_id=None,
            max_attempts=1,
            openclaw_task_id="task-99",
            openclaw_worker_id="worker-zz",
        ),
    )

    started = [e for e in events if e.get("event_type") == "run_started"]
    assert started, events
    pl = started[0].get("payload") or {}
    assert pl.get("pipeline") == "openclaw_agent_core"
    assert pl.get("oc_stage") == "run_start"
    assert pl.get("trace_id") == trace_id
    assert pl.get("lang") == "zh"
    assert "run_id" in pl
    assert pl.get("openclaw_task_id") == "task-99"
    assert pl.get("openclaw_worker_id") == "worker-zz"
    assert pl.get("relay_envelope_present") is False
    assert pl.get("relay_envelope_pointer_count") == 0

    att = [e for e in events if e.get("event_type") == "attempt_started"]
    assert att
    apl = att[0].get("payload") or {}
    assert apl.get("oc_stage") == "attempt"
    assert apl.get("attempt_no") == 1


def test_agent_core_trace_includes_relay_envelope_stats(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = SqliteStore(str(tmp_path / "trace2.sqlite"))
    sess = store.create_session("t")
    events: list[dict] = []
    real_add = store.add_trace_event

    def _wrap(**kwargs: object) -> None:
        events.append(dict(kwargs))
        return real_add(**kwargs)

    monkeypatch.setattr(store, "add_trace_event", _wrap)
    run_agent_core(
        store=store,
        data=AgentCoreRunInput(
            msg=_msg(
                sess.id,
                metadata={
                    "tenant_id": "t1",
                    "user_id": "u1",
                    "relay_share_envelope": {
                        "schema_version": "v1",
                        "attachments": {"pointers": [{"pointer_uri": "relay://attachments/scope_1/abcdef123456"}]},
                    },
                },
            ),
            lang="zh",
            system_prompt="sys",
            model=StaticTextChatModel("done"),
            tools=ToolRegistry([]),
            trace_id="trace-relay",
            parent_span_id=None,
            max_attempts=1,
        ),
    )
    started = [e for e in events if e.get("event_type") == "run_started"]
    assert started
    sp = started[0].get("payload") or {}
    assert sp.get("relay_envelope_present") is True
    assert sp.get("relay_envelope_pointer_count") == 1
    att = [e for e in events if e.get("event_type") == "attempt_started"]
    assert att
    ap = att[0].get("payload") or {}
    assert ap.get("relay_envelope_present") is True
    assert ap.get("relay_envelope_pointer_count") == 1
