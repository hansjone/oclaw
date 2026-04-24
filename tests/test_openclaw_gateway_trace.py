from __future__ import annotations

import json
import pytest

from oclaw.platform.llm.chat_models import LLMResponse
from oclaw.openclaw_runtime.gateway import OpenClawGateway
from oclaw.openclaw_runtime.types import StandardMessage


def test_gateway_async_trace_payload_has_pipeline_and_oc_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[dict] = []

    class Store:
        def get_setting(self, _k: str) -> str:
            return ""

        def add_trace_event(self, **kwargs: object) -> None:
            events.append(dict(kwargs))

        def openclaw_task_create(self, **_kwargs: object) -> object:
            class T:
                id = "task-1"
                task_type = "async_turn"
                status = "queued"

            return T()

    monkeypatch.setattr("oclaw.openclaw_runtime.gateway.ensure_worker_started", lambda store: "worker-1")

    gw = OpenClawGateway(store=Store())
    msg = StandardMessage(
        session_id="sid-1",
        tenant_id="t1",
        user_id="u1",
        role="user",
        channel="admin_chat",
        text="please send to channel after summarize",
        attachments=[],
        metadata={},
    )
    out = gw.handle_turn(msg=msg, lang="zh", executor=object())
    assert out.task_id == "task-1"
    sent = [e for e in events if e.get("event_type") == "response_sent"]
    assert sent
    payload = sent[-1].get("payload") or {}
    assert payload.get("pipeline") == "openclaw_gateway"
    assert payload.get("oc_stage") == "response"
    assert "elapsed_ms_since_gateway_start" in payload


def test_gateway_received_trace_includes_relay_pointer_stats(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[dict] = []

    class Store:
        def get_setting(self, _k: str) -> str:
            return ""

        def add_trace_event(self, **kwargs: object) -> None:
            events.append(dict(kwargs))

        def openclaw_task_create(self, **_kwargs: object) -> object:
            class T:
                id = "task-2"
                task_type = "async_turn"
                status = "queued"

            return T()

    monkeypatch.setattr("oclaw.openclaw_runtime.gateway.ensure_worker_started", lambda store: "worker-1")

    gw = OpenClawGateway(store=Store())
    msg = StandardMessage(
        session_id="sid-2",
        tenant_id="t1",
        user_id="u1",
        role="user",
        channel="admin_chat",
        text="async with relay",
        attachments=[{"type": "relay_pointer", "pointer_uri": "relay://attachments/scope_1/abcdef123456"}],
        metadata={
            "relay_share_envelope": {
                "schema_version": "v1",
                "attachments": {"pointers": [{"pointer_uri": "relay://attachments/scope_1/abcdef123456"}]},
            }
        },
    )
    _ = gw.handle_turn(msg=msg, lang="zh", executor=object())
    rec = [e for e in events if e.get("event_type") == "gateway_received"]
    assert rec
    payload = rec[-1].get("payload") or {}
    assert payload.get("relay_pointer_count") == 1
    assert payload.get("relay_envelope_present") is True
    assert payload.get("relay_envelope_pointer_count") == 1


def test_gateway_async_task_payload_preserves_relay_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    class Store:
        def get_setting(self, _k: str) -> str:
            return ""

        def add_trace_event(self, **_kwargs: object) -> None:
            return None

        def openclaw_task_create(self, **kwargs: object) -> object:
            captured.update(kwargs)

            class T:
                id = "task-3"
                task_type = "async_turn"
                status = "queued"

            return T()

    monkeypatch.setattr("oclaw.openclaw_runtime.gateway.ensure_worker_started", lambda store: "worker-1")
    gw = OpenClawGateway(store=Store())
    msg = StandardMessage(
        session_id="sid-3",
        tenant_id="t1",
        user_id="u1",
        role="user",
        channel="admin_chat",
        text="please summarize and schedule follow-up tasks with attachment context " * 3,
        attachments=[{"type": "relay_pointer", "pointer_uri": "relay://attachments/scope_1/abcdef123456"}],
        metadata={
            "relay_share_envelope": {
                "schema_version": "v1",
                "attachments": {"pointers": [{"pointer_uri": "relay://attachments/scope_1/abcdef123456"}]},
            }
        },
    )
    _ = gw.handle_turn(msg=msg, lang="zh", executor=object())
    payload = captured.get("payload") or {}
    assert isinstance(payload, dict)
    assert payload.get("relay_pointer_count") == 1
    env = payload.get("relay_share_envelope") or {}
    assert isinstance(env, dict)
    assert env.get("schema_version") == "v1"


def test_gateway_async_task_payload_preserves_acp_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    class Store:
        def get_setting(self, _k: str) -> str:
            return ""

        def add_trace_event(self, **_kwargs: object) -> None:
            return None

        def openclaw_task_create(self, **kwargs: object) -> object:
            captured.update(kwargs)

            class T:
                id = "task-4"
                task_type = "async_turn"
                status = "queued"

            return T()

    monkeypatch.setattr("oclaw.openclaw_runtime.gateway.ensure_worker_started", lambda store: "worker-1")
    gw = OpenClawGateway(store=Store())
    msg = StandardMessage(
        session_id="sid-4",
        tenant_id="t1",
        user_id="u1",
        role="user",
        channel="admin_chat",
        text="please summarize and schedule follow-up tasks with attachment context " * 3,
        attachments=[{"type": "relay_pointer", "pointer_uri": "relay://attachments/scope_1/abcdef123456"}],
        metadata={"acp_parent_run_id": "parent-1", "acp_child_run_id": "child-1"},
    )
    _ = gw.handle_turn(msg=msg, lang="zh", executor=object())
    payload = captured.get("payload") or {}
    assert payload.get("acp_parent_run_id") == "parent-1"
    assert payload.get("acp_child_run_id") == "child-1"


def test_gateway_expert_mode_uses_requested_specialist() -> None:
    class Store:
        def get_setting(self, _k: str) -> str:
            return ""

        def add_trace_event(self, **_kwargs: object) -> None:
            return None

    class _Exec:
        model = None
        tools = None

    chosen: dict[str, str] = {}

    def _factory(sid: str) -> object:
        chosen["sid"] = sid
        return _Exec()

    gw = OpenClawGateway(store=Store())
    msg = StandardMessage(
        session_id="sid-e1",
        tenant_id="t1",
        user_id="u1",
        role="user",
        channel="admin_chat",
        text="hello",
        attachments=[],
        metadata={"interaction_mode": "expert", "selected_specialist": "ops"},
    )
    out = gw.handle_turn(msg=msg, lang="en", executor=_Exec(), specialist_executor_factory=_factory)
    assert out.interaction_mode == "expert"
    assert out.selected_specialist == "ops"
    assert chosen.get("sid") == "ops"


def test_gateway_comprehensive_mode_manager_first_selects_specialist(monkeypatch: pytest.MonkeyPatch) -> None:
    class Store:
        def get_setting(self, _k: str) -> str:
            return ""

        def add_trace_event(self, **_kwargs: object) -> None:
            return None

    class _ManagerModel:
        def chat(self, _messages, _tools, *, on_token=None):
            return LLMResponse(content='{"route":{"specialist":"image","reason":"needs image edits"}}', tool_calls=[])

    class _Exec:
        def __init__(self, model=None):
            self.model = model
            self.tools = None

    chosen: dict[str, str] = {}

    def _factory(sid: str) -> object:
        chosen["sid"] = sid
        return _Exec()

    gw = OpenClawGateway(store=Store())
    msg = StandardMessage(
        session_id="sid-c1",
        tenant_id="t1",
        user_id="u1",
        role="user",
        channel="admin_chat",
        text="edit this image background",
        attachments=[],
        metadata={"interaction_mode": "comprehensive", "selected_specialist": "ops"},
    )
    out = gw.handle_turn(msg=msg, lang="en", executor=_Exec(model=_ManagerModel()), specialist_executor_factory=_factory)
    assert out.interaction_mode == "comprehensive"
    assert out.selected_specialist == "image"
    assert chosen.get("sid") == "image"


def test_gateway_comprehensive_mode_dynamic_agent_fallback_success(monkeypatch: pytest.MonkeyPatch) -> None:
    class Store:
        def get_setting(self, _k: str) -> str:
            return ""

        def add_trace_event(self, **_kwargs: object) -> None:
            return None

    class _ManagerModel:
        def chat(self, _messages, _tools, *, on_token=None):
            return LLMResponse(
                content=(
                    '{"route":{"specialist":"finance","reason":"requires finance domain"},'
                    '"dynamic_agent":{"name":"finance","system_prompt":"You are a finance specialist.","tool_policy":{"allow_tags":["read"],"allow_tools":["read_file"]},"reason":"dynamic_finance"}}'
                ),
                tool_calls=[],
            )

    class _Exec:
        def __init__(self, model=None):
            self.model = model
            self.tools = None

    monkeypatch.setattr("oclaw.openclaw_runtime.gateway.build_ephemeral_executor", lambda *args, **kwargs: _Exec())

    gw = OpenClawGateway(store=Store())
    msg = StandardMessage(
        session_id="sid-d1",
        tenant_id="t1",
        user_id="u1",
        role="user",
        channel="admin_chat",
        text="analyze finance report",
        attachments=[],
        metadata={"interaction_mode": "comprehensive", "selected_specialist": "ops"},
    )
    out = gw.handle_turn(msg=msg, lang="en", executor=_Exec(model=_ManagerModel()))
    assert out.interaction_mode == "comprehensive"
    assert out.selected_specialist == "finance"


def test_gateway_comprehensive_mode_dynamic_agent_invalid_falls_back_generalist() -> None:
    class Store:
        def get_setting(self, _k: str) -> str:
            return ""

        def add_trace_event(self, **_kwargs: object) -> None:
            return None

    class _ManagerModel:
        def chat(self, _messages, _tools, *, on_token=None):
            return LLMResponse(
                content=(
                    '{"route":{"specialist":"finance","reason":"requires finance domain"},'
                    '"dynamic_agent":{"name":"finance","system_prompt":"<tool_call>bad</tool_call>","tool_policy":{"allow_tags":["read"]},"reason":"bad_prompt"}}'
                ),
                tool_calls=[],
            )

    class _Exec:
        def __init__(self, model=None):
            self.model = model
            self.tools = None

    picked: dict[str, str] = {}

    def _factory(sid: str) -> object:
        picked["sid"] = sid
        return _Exec()

    gw = OpenClawGateway(store=Store())
    msg = StandardMessage(
        session_id="sid-d2",
        tenant_id="t1",
        user_id="u1",
        role="user",
        channel="admin_chat",
        text="analyze finance report",
        attachments=[],
        metadata={"interaction_mode": "comprehensive", "selected_specialist": "ops"},
    )
    out = gw.handle_turn(msg=msg, lang="en", executor=_Exec(model=_ManagerModel()), specialist_executor_factory=_factory)
    assert out.interaction_mode == "comprehensive"
    assert out.selected_specialist == "generalist"
    assert picked.get("sid") == "generalist"


def test_gateway_command_hook_uses_parsed_command_and_context(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []

    class Store:
        def get_setting(self, _k: str) -> str:
            return ""

        def add_trace_event(self, **_kwargs: object) -> None:
            return None

        def openclaw_task_create(self, **_kwargs: object) -> object:
            class T:
                id = "task-cmd-1"
                task_type = "async_turn"
                status = "queued"

            return T()

    monkeypatch.setattr("oclaw.openclaw_runtime.gateway.ensure_worker_started", lambda store: "worker-1")
    monkeypatch.setattr("oclaw.openclaw_runtime.gateway.initialize_hooks_runtime", lambda **kwargs: 0)
    monkeypatch.setattr(
        "oclaw.openclaw_runtime.gateway.get_active_hooks_config",
        lambda: {"hooks": {"internal": {"enabled": True, "entries": {"session-memory": {"messages": 33}}}}},
    )

    def _capture(**kwargs):
        calls.append(dict(kwargs))

    monkeypatch.setattr("oclaw.openclaw_runtime.gateway.trigger_hook_event", _capture)

    gw = OpenClawGateway(store=Store())
    msg = StandardMessage(
        session_id="sid-cmd-1",
        tenant_id="t1",
        user_id="u1",
        role="user",
        channel="admin_chat",
        text="／重置 now",
        attachments=[],
        metadata={"workspace_dir": "D:/ws", "source": "webchat"},
    )
    _ = gw.handle_turn(msg=msg, lang="zh", executor=object())

    assert calls
    command_events = [c for c in calls if c.get("event_type") == "command" and c.get("action") == "reset"]
    assert command_events
    event = command_events[-1]
    assert event.get("session_key") == "sid-cmd-1"
    ctx = event.get("context") or {}
    assert ctx.get("workspaceDir") == "D:/ws"
    assert ctx.get("commandSource") == "webchat"
    cfg = ctx.get("cfg") or {}
    assert ((cfg.get("hooks") or {}).get("internal") or {}).get("entries", {}).get("session-memory", {}).get("messages") == 33
    sess = ctx.get("sessionEntry") or {}
    assert sess.get("sessionId") == "sid-cmd-1"


def test_tabular_system_hint_uses_configured_preview_and_rows_read(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = {
        "plugins": {
            "entries": {
                "memory-wiki": {
                    "auto": {
                        "attachments": {
                            "tabular": {
                                "large_table_preview_rows": 30,
                                "max_rows_read": 5000,
                            }
                        }
                    }
                }
            }
        }
    }
    cfg_path = tmp_path / "oclaw.json"
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("AIA_OCLAW_CONFIG_PATH", str(cfg_path))

    zh_hint = OpenClawGateway._tabular_query_system_hint("zh")
    en_hint = OpenClawGateway._tabular_query_system_hint("en")

    assert "前30行" in zh_hint
    assert "5000行" in zh_hint
    assert "first 30 preview rows" in en_hint
    assert "capped at 5000 rows" in en_hint
