from __future__ import annotations

from pathlib import Path

from oclaw.runtime.agent_core_run import AgentCoreRunInput, run_agent_core
from oclaw.runtime.gateway import OclawGateway
from oclaw.runtime.types import StandardMessage
from oclaw.platform.llm.chat_models import LLMResponse, StaticTextChatModel
from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.runtime.tools.base import ToolRegistry


class _FailOnceModel:
    def __init__(self) -> None:
        self._n = 0

    def chat(self, messages, tools, *, on_token=None):
        self._n += 1
        if self._n == 1:
            raise RuntimeError("temporary_model_error")
        if on_token:
            on_token("ok")
        return LLMResponse(content="ok", tool_calls=[])


def _msg(session_id: str) -> StandardMessage:
    return StandardMessage(
        session_id=session_id,
        tenant_id="t1",
        user_id="u1",
        role="member",
        channel="admin_chat",
        text="hello",
        attachments=[],
        metadata={"tenant_id": "t1", "user_id": "u1"},
    )


def test_agent_core_run_retries_then_succeeds(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "a.sqlite"))
    sess = store.create_session("t")
    model = _FailOnceModel()
    out = run_agent_core(
        store=store,
        data=AgentCoreRunInput(
            msg=_msg(sess.id),
            lang="zh",
            system_prompt="sys",
            model=model,
            tools=ToolRegistry([]),
            trace_id=None,
            parent_span_id=None,
            max_attempts=2,
        ),
    )
    assert out.run_state.status == "success"
    assert len(out.run_state.attempts) == 2
    assert out.run_state.attempts[0].status == "retry"
    assert out.run_state.attempts[1].status == "success"

    rows = store.oclaw_attempt_list(run_id=out.run_state.run_id)
    assert len(rows) == 2


class _AlwaysFailModel:
    def chat(self, messages, tools, *, on_token=None):
        raise RuntimeError("bad_request_invalid_input")


class _AuthFailModel:
    def chat(self, messages, tools, *, on_token=None):
        raise RuntimeError("401 unauthorized invalid api key")


class _RelayEnvelopeFailModel:
    def chat(self, messages, tools, *, on_token=None):
        raise RuntimeError("relay_envelope_invalid")


def test_agent_core_non_retryable_stops_early(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "d.sqlite"))
    sess = store.create_session("t")
    out = run_agent_core(
        store=store,
        data=AgentCoreRunInput(
            msg=_msg(sess.id),
            lang="zh",
            system_prompt="sys",
            model=_AlwaysFailModel(),
            tools=ToolRegistry([]),
            trace_id=None,
            parent_span_id=None,
            max_attempts=3,
        ),
    )
    assert out.run_state.status == "failed"
    assert out.run_state.stop_reason == "non_retryable_error"
    assert len(out.run_state.attempts) == 1
    assert out.run_state.attempts[0].status == "failed"


def test_agent_core_auth_error_not_retryable(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "e.sqlite"))
    sess = store.create_session("t")
    out = run_agent_core(
        store=store,
        data=AgentCoreRunInput(
            msg=_msg(sess.id),
            lang="zh",
            system_prompt="sys",
            model=_AuthFailModel(),
            tools=ToolRegistry([]),
            trace_id=None,
            parent_span_id=None,
            max_attempts=3,
        ),
    )
    assert out.run_state.status == "failed"
    assert out.run_state.last_error_code == "auth_invalid_credentials"
    assert len(out.run_state.attempts) == 1
    assert out.run_state.attempts[0].error_code == "auth_invalid_credentials"


def test_agent_core_relay_envelope_error_not_retryable(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "f.sqlite"))
    sess = store.create_session("t")
    out = run_agent_core(
        store=store,
        data=AgentCoreRunInput(
            msg=_msg(sess.id),
            lang="zh",
            system_prompt="sys",
            model=_RelayEnvelopeFailModel(),
            tools=ToolRegistry([]),
            trace_id=None,
            parent_span_id=None,
            max_attempts=3,
        ),
    )
    assert out.run_state.status == "failed"
    assert out.run_state.last_error_code == "relay_envelope_invalid"
    assert len(out.run_state.attempts) == 1
    assert out.run_state.attempts[0].error_code == "relay_envelope_invalid"


def test_gateway_fail_closed_when_executor_missing_model_tools(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "b.sqlite"))
    sess = store.create_session("t")
    gw = OclawGateway(store=store)

    class _BadExecutor:
        pass

    res = gw.handle_turn(msg=_msg(sess.id), lang="zh", executor=_BadExecutor())
    assert "缺少 model/tools" in res.reply_text


def test_agent_core_single_attempt_success(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "c.sqlite"))
    sess = store.create_session("t")
    out = run_agent_core(
        store=store,
        data=AgentCoreRunInput(
            msg=_msg(sess.id),
            lang="zh",
            system_prompt="sys",
            model=StaticTextChatModel("done"),
            tools=ToolRegistry([]),
            trace_id=None,
            parent_span_id=None,
            max_attempts=2,
        ),
    )
    assert out.run_state.status == "success"
    assert out.outcome.final_text == "done"

