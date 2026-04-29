from __future__ import annotations

import json
from types import SimpleNamespace
import pytest

from oclaw.platform.llm.chat_models import LLMResponse
from oclaw.runtime.gateway import OclawGateway
from oclaw.runtime.types import StandardMessage


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

    monkeypatch.setattr("oclaw.runtime.gateway.ensure_worker_started", lambda store: "worker-1")

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

    monkeypatch.setattr("oclaw.runtime.gateway.ensure_worker_started", lambda store: "worker-1")

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

        def add_trace_event(self, **_kwargs: object) -> None:
            return None

        def oclaw_task_create(self, **kwargs: object) -> object:
            captured.update(kwargs)

            class T:
                id = "task-3"
                task_type = "async_turn"
                status = "queued"

            return T()

    monkeypatch.setattr("oclaw.runtime.gateway.ensure_worker_started", lambda store: "worker-1")
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

    monkeypatch.setattr("oclaw.runtime.gateway.ensure_worker_started", lambda store: "worker-1")
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


def test_gateway_comprehensive_mode_manager_first_selects_specialist(monkeypatch: pytest.MonkeyPatch) -> None:
    class Store:
        def get_setting(self, _k: str) -> str:
            return ""

        def add_trace_event(self, **_kwargs: object) -> None:
            return None

    class _ManagerModel:
        def chat(self, _messages, _tools, *, on_token=None):
            return LLMResponse(
                content='{"route":{"specialist":"generalist","reason":"needs image edits"},"dispatch":{"instruction_text":"Please edit the image background."}}',
                tool_calls=[],
            )

    class _Exec:
        def __init__(self, model=None):
            self.model = model
            self.tools = object()
            self.system_prompt = ""

    monkeypatch.setattr(
        "oclaw.runtime.gateway.get_manager_prompt_prebuild",
        lambda **kwargs: {
            "manager_context": "manager",
            "allowed_fixed": ("generalist", "ops", "memory"),
            "allowed_fixed_quoted": '"generalist", "ops", "memory"',
        },
    )
    captured: dict = {}

    def _run_agent_core(**kwargs):
        data = kwargs.get("data")
        captured["exec_text"] = getattr(getattr(data, "msg", None), "text", None)
        captured["persisted_user_text"] = getattr(data, "persisted_user_text", None)
        return SimpleNamespace(outcome=SimpleNamespace(final_text="specialist_answer"))

    monkeypatch.setattr("oclaw.runtime.gateway.run_agent_core", _run_agent_core)

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
    out = gw.handle_turn(msg=msg, lang="en", executor=_Exec(model=_ManagerModel()), specialist_executor_factory=_factory)
    assert out.interaction_mode == "comprehensive"
    assert out.selected_specialist == "generalist"
    assert chosen.get("sid") == "generalist"
    assert captured.get("exec_text") == "Please edit the image background."
    assert captured.get("persisted_user_text") == "edit this image background"


def test_gateway_comprehensive_mode_writes_task_assignment_reasoning(monkeypatch: pytest.MonkeyPatch) -> None:
    written: list[dict] = []

    class Store:
        def get_setting(self, _k: str) -> str:
            return ""

        def add_trace_event(self, **_kwargs: object) -> None:
            return None

        def add_message(self, **kwargs: object) -> None:
            written.append(dict(kwargs))

    class _ManagerModel:
        def chat(self, _messages, _tools, *, on_token=None):
            return LLMResponse(
                content='{"route":{"specialist":"ops","reason":"ops task"},"dispatch":{"instruction_text":"请检查并修复网关启动失败。"}}',
                tool_calls=[],
            )

    class _Exec:
        def __init__(self, model=None):
            self.model = model
            self.tools = object()
            self.system_prompt = ""

    monkeypatch.setattr(
        "oclaw.runtime.gateway.get_manager_prompt_prebuild",
        lambda **kwargs: {
            "manager_context": "manager",
            "allowed_fixed": ("generalist", "ops", "memory"),
            "allowed_fixed_quoted": '"generalist", "ops", "memory"',
        },
    )
    monkeypatch.setattr(
        "oclaw.runtime.gateway.run_agent_core",
        lambda **kwargs: SimpleNamespace(outcome=SimpleNamespace(final_text="specialist_answer")),
    )

    gw = OclawGateway(store=Store())
    msg = StandardMessage(
        session_id="sid-assign-1",
        tenant_id="t1",
        user_id="u1",
        role="user",
        channel="admin_chat",
        text="网关起不来，帮我修复",
        attachments=[],
        metadata={"interaction_mode": "comprehensive"},
    )
    _ = gw.handle_turn(msg=msg, lang="zh", executor=_Exec(model=_ManagerModel()))
    reasoning_rows = [x for x in written if str(x.get("event_type") or "") == "reasoning"]
    assert reasoning_rows, "expected task-assignment reasoning row"
    content = str(reasoning_rows[-1].get("content") or "")
    assert "任务分配" in content
    assert "specialist=ops" in content
    assert "请检查并修复网关启动失败" in content


def test_gateway_comprehensive_ignores_wiki_inject_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    class Store:
        def get_setting(self, _k: str) -> str:
            return ""

        def add_trace_event(self, **_kwargs: object) -> None:
            return None

    class _ManagerModel:
        def chat(self, _messages, _tools, *, on_token=None):
            return LLMResponse(
                content=(
                    '{"route":{"specialist":"generalist","reason":"general",'
                    '"need_wiki_inject":true,"wiki_query":"router issue"},'
                    '"dispatch":{"instruction_text":"请先分析问题并给出结论。",'
                    '"need_wiki_inject":true,"wiki_query":"router issue"}}'
                ),
                tool_calls=[],
            )

    class _Exec:
        def __init__(self, model=None):
            self.model = model
            self.tools = object()
            self.system_prompt = ""

    monkeypatch.setattr(
        "oclaw.runtime.gateway.get_manager_prompt_prebuild",
        lambda **kwargs: {
            "manager_context": "manager",
            "allowed_fixed": ("generalist", "ops", "memory"),
            "allowed_fixed_quoted": '"generalist", "ops", "memory"',
        },
    )
    captured: dict[str, object] = {}

    def _run_agent_core(**kwargs):
        data = kwargs.get("data")
        msg = getattr(data, "msg", None)
        captured["metadata"] = dict(getattr(msg, "metadata", {}) or {})
        return SimpleNamespace(outcome=SimpleNamespace(final_text="ok"))

    monkeypatch.setattr("oclaw.runtime.gateway.run_agent_core", _run_agent_core)

    gw = OclawGateway(store=Store())
    msg = StandardMessage(
        session_id="sid-wi-1",
        tenant_id="t1",
        user_id="u1",
        role="user",
        channel="admin_chat",
        text="分析一下",
        attachments=[],
        metadata={"interaction_mode": "comprehensive"},
    )
    out = gw.handle_turn(msg=msg, lang="zh", executor=_Exec(model=_ManagerModel()))
    assert out.interaction_mode == "comprehensive"
    md = captured.get("metadata") or {}
    assert isinstance(md, dict)
    assert "need_wiki_inject" not in md
    assert "wiki_query" not in md

def test_gateway_comprehensive_mode_has_manager_final_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    class Store:
        def get_setting(self, _k: str) -> str:
            return ""

        def add_trace_event(self, **_kwargs: object) -> None:
            return None

    class _ManagerModel:
        def __init__(self) -> None:
            self.calls = 0

        def chat(self, _messages, _tools, *, on_token=None):
            self.calls += 1
            if self.calls == 1:
                return LLMResponse(
                    content='{"route":{"specialist":"generalist","reason":"general"},"dispatch":{"instruction_text":"Analyze the finance report and provide key points."}}',
                    tool_calls=[],
                )
            return LLMResponse(content="final_from_manager", tool_calls=[])

    class _Exec:
        def __init__(self, model=None):
            self.model = model
            self.tools = object()
            self.system_prompt = ""

    monkeypatch.setattr(
        "oclaw.runtime.gateway.get_manager_prompt_prebuild",
        lambda **kwargs: {
            "manager_context": "manager",
            "allowed_fixed": ("generalist", "ops", "memory"),
            "allowed_fixed_quoted": '"generalist", "ops", "memory"',
        },
    )
    monkeypatch.setattr(
        "oclaw.runtime.gateway.run_agent_core",
        lambda **kwargs: SimpleNamespace(outcome=SimpleNamespace(final_text="specialist_answer")),
    )

    gw = OclawGateway(store=Store())
    model = _ManagerModel()
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
    out = gw.handle_turn(msg=msg, lang="en", executor=_Exec(model=model))
    assert out.interaction_mode == "comprehensive"
    assert out.selected_specialist == "generalist"
    assert out.reply_text == "final_from_manager"


def test_gateway_comprehensive_mode_dynamic_agent_dispatches_instruction_only(monkeypatch: pytest.MonkeyPatch) -> None:
    class Store:
        def get_setting(self, _k: str) -> str:
            return ""

        def add_trace_event(self, **_kwargs: object) -> None:
            return None

    class _ManagerModel:
        def chat(self, _messages, _tools, *, on_token=None):
            return LLMResponse(
                content=(
                    '{"route":{"specialist":"dyn:sql","reason":"needs ad-hoc expert"},'
                    '"dispatch":{"instruction_text":"Write a SQL query to compute daily active users."},'
                    '"dynamic_agent":{"name":"dyn:sql","system_prompt":"You are a SQL expert.","tool_policy":{"allow_tags":[],"allow_tools":[]},"reason":"dynamic"}}'
                ),
                tool_calls=[],
            )

    class _Exec:
        def __init__(self, model=None):
            self.model = model
            self.tools = object()
            self.system_prompt = ""

    monkeypatch.setattr(
        "oclaw.runtime.gateway.get_manager_prompt_prebuild",
        lambda **kwargs: {
            "manager_context": "manager",
            "allowed_fixed": ("generalist", "ops", "memory"),
            "allowed_fixed_quoted": '"generalist", "ops", "memory"',
        },
    )
    monkeypatch.setattr("oclaw.runtime.gateway.build_ephemeral_executor", lambda *args, **kwargs: _Exec(model=object()))

    captured: dict = {}

    def _run_agent_core(**kwargs):
        data = kwargs.get("data")
        captured["exec_text"] = getattr(getattr(data, "msg", None), "text", None)
        return SimpleNamespace(outcome=SimpleNamespace(final_text="dynamic_specialist_answer"))

    monkeypatch.setattr("oclaw.runtime.gateway.run_agent_core", _run_agent_core)

    gw = OclawGateway(store=Store())
    msg = StandardMessage(
        session_id="sid-dyn-1",
        tenant_id="t1",
        user_id="u1",
        role="user",
        channel="admin_chat",
        text="How do I compute DAU from events table?",
        attachments=[],
        metadata={"interaction_mode": "comprehensive"},
    )
    out = gw.handle_turn(msg=msg, lang="en", executor=_Exec(model=_ManagerModel()))
    assert out.interaction_mode == "comprehensive"
    assert out.selected_specialist == "dyn:sql"
    assert captured.get("exec_text") == "Write a SQL query to compute daily active users."


def test_gateway_comprehensive_mode_ignores_manager_self_and_dispatches_specialist(monkeypatch: pytest.MonkeyPatch) -> None:
    class Store:
        def get_setting(self, _k: str) -> str:
            return ""

        def add_trace_event(self, **_kwargs: object) -> None:
            return None

    class _ManagerModel:
        def __init__(self) -> None:
            self.calls = 0

        def chat(self, _messages, _tools, *, on_token=None):
            self.calls += 1
            if self.calls == 1:
                return LLMResponse(
                    content='{"route":{"kind":"manager_self","specialist":"generalist","reason":"can answer directly"},"dispatch":{"instruction_text":"请直接给用户简明答案。"}}',
                    tool_calls=[],
                )
            return LLMResponse(content="manager_self_final", tool_calls=[])

    class _Exec:
        def __init__(self, model=None):
            self.model = model
            self.tools = object()
            self.system_prompt = ""

    monkeypatch.setattr(
        "oclaw.runtime.gateway.get_manager_prompt_prebuild",
        lambda **kwargs: {
            "manager_context": "manager",
            "allowed_fixed": ("generalist", "ops", "memory"),
            "allowed_fixed_quoted": '"generalist", "ops", "memory"',
        },
    )

    captured: dict[str, str] = {}

    def _run_agent_core(**kwargs):
        data = kwargs["data"]
        captured["exec_text"] = str(getattr(data.msg, "text", ""))

        class _Outcome:
            final_text = "specialist_result"

        class _Out:
            outcome = _Outcome()

        return _Out()

    monkeypatch.setattr("oclaw.runtime.gateway.run_agent_core", _run_agent_core)

    gw = OclawGateway(store=Store())
    msg = StandardMessage(
        session_id="sid-self-1",
        tenant_id="t1",
        user_id="u1",
        role="user",
        channel="admin_chat",
        text="请直接回答这个简单问题",
        attachments=[],
        metadata={"interaction_mode": "comprehensive"},
    )
    out = gw.handle_turn(msg=msg, lang="zh", executor=_Exec(model=_ManagerModel()))
    assert out.interaction_mode == "comprehensive"
    assert out.selected_specialist == "generalist"
    assert captured.get("exec_text") == "请直接给用户简明答案。"
    assert out.reply_text == "manager_self_final"


def test_gateway_comprehensive_mode_suppresses_instruction_echo(monkeypatch: pytest.MonkeyPatch) -> None:
    class Store:
        def get_setting(self, _k: str) -> str:
            return ""

        def add_trace_event(self, **_kwargs: object) -> None:
            return None

    instruction = "用户说厉害；请友好回应，表达感谢并询问是否有具体问题。"

    class _ManagerModel:
        def __init__(self) -> None:
            self.calls = 0

        def chat(self, _messages, _tools, *, on_token=None):
            self.calls += 1
            if self.calls == 1:
                return LLMResponse(
                    content=(
                        '{"route":{"specialist":"generalist","reason":"smalltalk"},'
                        f'"dispatch":{{"instruction_text":"{instruction}"}}'
                        "}"
                    ),
                    tool_calls=[],
                )
            # Simulate finalize path echoing instruction.
            return LLMResponse(content=instruction, tool_calls=[])

    class _Exec:
        def __init__(self, model=None):
            self.model = model
            self.tools = object()
            self.system_prompt = ""

    monkeypatch.setattr(
        "oclaw.runtime.gateway.get_manager_prompt_prebuild",
        lambda **kwargs: {
            "manager_context": "manager",
            "allowed_fixed": ("generalist", "ops", "memory"),
            "allowed_fixed_quoted": '"generalist", "ops", "memory"',
        },
    )

    # Specialist output also echoes instruction -> should still be suppressed.
    def _run_agent_core(**kwargs):
        class _Outcome:
            final_text = instruction

        class _Out:
            outcome = _Outcome()

        return _Out()

    monkeypatch.setattr("oclaw.runtime.gateway.run_agent_core", _run_agent_core)

    gw = OclawGateway(store=Store())
    msg = StandardMessage(
        session_id="sid-echo-1",
        tenant_id="t1",
        user_id="u1",
        role="user",
        channel="admin_chat",
        text="你真厉害",
        attachments=[],
        metadata={"interaction_mode": "comprehensive"},
    )
    out = gw.handle_turn(msg=msg, lang="zh", executor=_Exec(model=_ManagerModel()))
    assert out.interaction_mode == "comprehensive"
    assert "用户说厉害" not in out.reply_text
    assert "请友好回应" not in out.reply_text
    assert out.reply_text == "抱歉，我暂时无法给出可展示的结果，请稍后再试。"


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

    monkeypatch.setattr("oclaw.runtime.gateway.ensure_worker_started", lambda store: "worker-1")
    monkeypatch.setattr("oclaw.runtime.gateway.initialize_hooks_runtime", lambda **kwargs: 0)
    monkeypatch.setattr(
        "oclaw.runtime.gateway.get_active_hooks_config",
        lambda: {"hooks": {"internal": {"enabled": True, "entries": {"session-memory": {"messages": 33}}}}},
    )

    def _capture(**kwargs):
        calls.append(dict(kwargs))

    monkeypatch.setattr("oclaw.runtime.gateway.trigger_hook_event", _capture)

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
