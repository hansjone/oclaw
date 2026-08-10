from __future__ import annotations

import json
from types import SimpleNamespace
import pytest

from svc.llm.chat_models import LLMResponse
from runtime.gateway import OclawGateway
from runtime.tools.base import ToolRegistry, ToolSpec
from runtime.types import StandardMessage


def test_gateway_async_trace_payload_has_pipeline_and_oc_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[dict] = []

    class Store:
        def get_setting(self, _k: str) -> str:
            return ""

        def add_trace_event(self, **kwargs: object) -> None:
            events.append(dict(kwargs))

        def oclaw_task_create(self, **_kwargs: object) -> object:
            class T:
                id = "task-1"
                task_type = "async_turn"
                status = "queued"

            return T()

    monkeypatch.setattr("runtime.gateway.ensure_worker_started", lambda store: "worker-1")

    gw = OclawGateway(store=Store())
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
    assert payload.get("pipeline") == "oclaw_gateway"
    assert payload.get("oc_stage") == "response"
    assert "elapsed_ms_since_gateway_start" in payload


def test_gateway_received_trace_includes_relay_pointer_stats(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[dict] = []

    class Store:
        def get_setting(self, _k: str) -> str:
            return ""

        def add_trace_event(self, **kwargs: object) -> None:
            events.append(dict(kwargs))

        def oclaw_task_create(self, **_kwargs: object) -> object:
            class T:
                id = "task-2"
                task_type = "async_turn"
                status = "queued"

            return T()

    monkeypatch.setattr("runtime.gateway.ensure_worker_started", lambda store: "worker-1")

    gw = OclawGateway(store=Store())
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

        def set_setting(self, _k: str, _v: str) -> None:
            return None

        def add_trace_event(self, **_kwargs: object) -> None:
            return None

        def oclaw_task_create(self, **kwargs: object) -> object:
            captured.update(kwargs)

            class T:
                id = "task-3"
                task_type = "async_turn"
                status = "queued"

            return T()

    monkeypatch.setattr("runtime.gateway.ensure_worker_started", lambda store: "worker-1")
    gw = OclawGateway(store=Store())
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

        def oclaw_task_create(self, **kwargs: object) -> object:
            captured.update(kwargs)

            class T:
                id = "task-4"
                task_type = "async_turn"
                status = "queued"

            return T()

    monkeypatch.setattr("runtime.gateway.ensure_worker_started", lambda store: "worker-1")
    gw = OclawGateway(store=Store())
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

    gw = OclawGateway(store=Store())
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


def test_gateway_expert_plan_execution_mode_ignored_without_plan_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    class Store:
        def get_setting(self, _k: str) -> str:
            return ""

        def set_setting(self, _k: str, _v: str) -> None:
            return None

        def add_trace_event(self, **_kwargs: object) -> None:
            return None

        def add_trace_events_batch(self, _rows: list[dict[str, object]]) -> None:
            return None

    class _Exec:
        model = object()
        tools = object()
        system_prompt = "base-system"

    captured: dict[str, object] = {}

    def _run_agent_core_ok(**kwargs: object) -> object:
        data = kwargs.get("data")
        captured["system_prompt"] = str(getattr(data, "system_prompt", "") or "")
        return SimpleNamespace(outcome=SimpleNamespace(final_text="agent_reply", turn_uuid="turn-1"))

    monkeypatch.setattr("runtime.gateway.run_agent_core", _run_agent_core_ok)

    gw = OclawGateway(store=Store())
    msg = StandardMessage(
        session_id="sid-plan-1",
        tenant_id="t1",
        user_id="u1",
        role="user",
        channel="admin_chat",
        text="先给我一个执行计划",
        attachments=[],
        metadata={"interaction_mode": "expert", "selected_specialist": "generalist", "execution_mode": "plan"},
    )
    out = gw.handle_turn(msg=msg, lang="zh", executor=_Exec())
    assert out.interaction_mode == "expert"
    assert out.dispatch_reason == "expert_direct"
    assert str(out.reply_text or "") == "agent_reply"
    prompt_text = str(captured.get("system_prompt") or "")
    assert "plan 模式" not in prompt_text
    assert "Plan mode is active" not in prompt_text



def test_gateway_forces_expert_when_comprehensive_requested(monkeypatch: pytest.MonkeyPatch) -> None:
    """Manager/comprehensive mode is removed; inbound comprehensive metadata must not change routing."""

    class Store:
        def get_setting(self, _k: str) -> str:
            return ""

        def add_trace_event(self, **_kwargs: object) -> None:
            return None

        def add_message(self, **_kwargs: object) -> None:
            raise AssertionError("comprehensive assignment message must not be written")

    class _Exec:
        def __init__(self, model=None):
            self.model = model
            self.tools = object()
            self.system_prompt = ""

    captured: dict = {}

    def _run_agent_core(**kwargs):
        data = kwargs.get("data")
        captured["exec_text"] = getattr(getattr(data, "msg", None), "text", None)
        captured["wire_policy_role"] = getattr(data, "wire_policy_role", None)
        return SimpleNamespace(outcome=SimpleNamespace(final_text="specialist_answer", turn_uuid="tu-1"), run_state=None)

    monkeypatch.setattr("runtime.gateway.run_agent_core", _run_agent_core)

    chosen: dict[str, str] = {}

    def _factory(sid: str) -> object:
        chosen["sid"] = sid
        return _Exec(model=object())

    gw = OclawGateway(store=Store())
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
    out = gw.handle_turn(msg=msg, lang="en", executor=_Exec(model=object()), specialist_executor_factory=_factory)
    assert out.interaction_mode == "expert"
    assert out.dispatch_reason == "expert_direct"
    assert out.selected_specialist == "ops"
    assert chosen.get("sid") == "ops"
    assert captured.get("exec_text") == "edit this image background"
    assert captured.get("wire_policy_role") == "ops"
    assert out.reply_text == "specialist_answer"


def test_gateway_command_hook_uses_parsed_command_and_context(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []

    class Store:
        def get_setting(self, _k: str) -> str:
            return ""

        def add_trace_event(self, **_kwargs: object) -> None:
            return None

        def oclaw_task_create(self, **_kwargs: object) -> object:
            class T:
                id = "task-cmd-1"
                task_type = "async_turn"
                status = "queued"

            return T()

    monkeypatch.setattr("runtime.gateway.ensure_worker_started", lambda store: "worker-1")
    monkeypatch.setattr("runtime.gateway.initialize_hooks_runtime", lambda **kwargs: 0)
    monkeypatch.setattr(
        "runtime.gateway.get_active_hooks_config",
        lambda: {"hooks": {"internal": {"enabled": True, "entries": {"session-memory": {"messages": 33}}}}},
    )

    def _capture(**kwargs):
        calls.append(dict(kwargs))

    monkeypatch.setattr("runtime.gateway.trigger_hook_event", _capture)

    gw = OclawGateway(store=Store())
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

    zh_hint = OclawGateway._tabular_query_system_hint("zh")
    en_hint = OclawGateway._tabular_query_system_hint("en")

    assert "前30行" in zh_hint
    assert "5000行" in zh_hint
    assert "first 30 preview rows" in en_hint
    assert "capped at 5000 rows" in en_hint


def test_channel_file_delivery_hint_goes_to_system_not_user_message() -> None:
    from runtime.types import StandardMessage

    zh_hint = OclawGateway._channel_file_delivery_system_hint("zh")
    assert "save_deliverable_attachment" in zh_hint
    msg = StandardMessage(
        session_id="s1",
        tenant_id="t1",
        user_id="u1",
        role="member",
        channel="weixin",
        text="hi",
        attachments=[],
        metadata={},
    )
    assert OclawGateway._is_channel_delivery_channel(msg)
    msg_admin = StandardMessage(
        session_id="s1",
        tenant_id="t1",
        user_id="u1",
        role="member",
        channel="admin",
        text="hi",
        attachments=[],
        metadata={},
    )
    assert not OclawGateway._is_channel_delivery_channel(msg_admin)


def test_group_focus_system_hint_only_for_shared_group_scope() -> None:
    from runtime.types import StandardMessage

    shared = StandardMessage(
        session_id="s1",
        tenant_id="t1",
        user_id="u1",
        role="member",
        channel="whatsapp",
        text="@bot alarms",
        attachments=[],
        metadata={"is_group": True, "group_session_scope": "chat"},
    )
    per_user = StandardMessage(
        session_id="s1",
        tenant_id="t1",
        user_id="u1",
        role="member",
        channel="whatsapp",
        text="@bot alarms",
        attachments=[],
        metadata={"is_group": True, "group_session_scope": "user_in_chat"},
    )
    dm = StandardMessage(
        session_id="s1",
        tenant_id="t1",
        user_id="u1",
        role="member",
        channel="whatsapp",
        text="alarms",
        attachments=[],
        metadata={"is_group": False},
    )
    hint = OclawGateway._group_focus_system_hint(shared, "en")
    assert "current sender" in hint
    assert OclawGateway._group_focus_system_hint(per_user, "en") == ""
    assert OclawGateway._group_focus_system_hint(dm, "en") == ""


def test_ops_short_intent_caps_tool_rounds(tmp_path) -> None:
    from runtime.types import StandardMessage
    from svc.persistence.sqlite_store import SqliteStore

    store = SqliteStore(str(tmp_path / "rounds.sqlite"))
    gw = OclawGateway(store=store)
    short = StandardMessage(
        session_id="s1",
        tenant_id="t1",
        user_id="u1",
        role="member",
        channel="whatsapp",
        text="fiber cut report",
        attachments=[],
        metadata={},
    )
    long = StandardMessage(
        session_id="s1",
        tenant_id="t1",
        user_id="u1",
        role="member",
        channel="whatsapp",
        text="Please investigate the full OSPF adjacency flap history across all PE routers and draft a long RCA.",
        attachments=[],
        metadata={},
    )
    admin = StandardMessage(
        session_id="s1",
        tenant_id="t1",
        user_id="u1",
        role="member",
        channel="admin",
        text="fiber cut report",
        attachments=[],
        metadata={},
    )
    assert gw._resolve_max_tool_rounds(short, base=200) == 200
    assert gw._resolve_max_tool_rounds(long, base=200) == 200
    assert gw._resolve_max_tool_rounds(admin, base=200) == 200

    store.set_setting("AIA_OPS_SHORT_INTENT_MAX_TOOL_ROUNDS", "12")
    assert gw._resolve_max_tool_rounds(short, base=200) == 12
    assert gw._resolve_max_tool_rounds(long, base=200) == 200
