from __future__ import annotations

from pathlib import Path

from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.runtime.plan_agent_v2_adapter import evaluate_for_expert_mode
from oclaw.runtime.plan_agent_v2_compat import build_shadow_gateway_result, legacy_gateway_result_keys
from oclaw.runtime.plan_agent_v2_gateway_adapter import evaluate_gateway_expert_turn_shadow
from oclaw.runtime.plan_agent_v2_manager import PlanModeManagerV2
from oclaw.runtime.plan_agent_v2_models import PLAN_MODE_PLAN, PlanAgentStateV2
from oclaw.runtime.plan_agent_v2_prompt_injector import build_plan_mode_prefix
from oclaw.runtime.plan_agent_v2_state_store import PlanAgentStateStoreV2
from oclaw.runtime.plan_agent_v2_switch import should_route_to_v2, v2_feature_enabled
from oclaw.runtime.plan_agent_v2_tool_specs import materialize_plan_mode_v2_tools
from oclaw.runtime.plan_agent_v2_tool_policy import filter_tools_for_mode
from oclaw.runtime.plan_agent_v2_trace import emit_plan_agent_v2_trace
from oclaw.runtime.plan_agent_v2 import should_route_to_v2 as should_route_to_v2_pkg
from oclaw.runtime.gateway import OclawGatewayResult
from oclaw.runtime.tools.base import ToolRegistry, ToolSpec
from oclaw.runtime.types import StandardMessage


def _dummy_tool(name: str, read_only: bool) -> ToolSpec:
    def _handler(args):
        return {"ok": True, "echo": args}

    return ToolSpec(
        name=name,
        description=name,
        parameters={"type": "object", "properties": {}, "additionalProperties": True},
        handler=_handler,
        read_only=read_only,
    )


def test_state_store_roundtrip(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    ss = PlanAgentStateStoreV2(store)
    st = ss.load(session_id="s1")
    assert st.mode == "normal"
    saved = ss.save(session_id="s1", state=st)
    loaded = ss.load(session_id="s1")
    assert loaded.mode == saved.mode


def test_manager_enter_and_confirm(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    plan_root = tmp_path / "plans"
    store.set_setting("AIA_EXPERT_PLAN_FILE_DIR", str(plan_root))
    mgr = PlanModeManagerV2(store=store)
    st1 = mgr.enter(session_id="sess-1", owner_specialist="generalist")
    assert st1.mode == PLAN_MODE_PLAN
    assert st1.plan_path
    assert Path(st1.plan_path).exists()
    st2 = mgr.confirm(session_id="sess-1")
    assert st2.mode == "normal"
    assert st2.plan_confirmed is True
    assert "## Goal" in str(st2.plan_content or "")


def test_tool_policy_filters_non_readonly_in_plan_mode() -> None:
    reg = ToolRegistry([_dummy_tool("read_a", True), _dummy_tool("write_a", False)])
    out = filter_tools_for_mode(registry=reg, mode="plan")
    names = {t.name for t in out}
    assert "read_a" in names
    assert "write_a" not in names


def test_tool_policy_keeps_plan_mode_control_tools() -> None:
    reg = ToolRegistry([_dummy_tool("exit_plan_mode_v2", False), _dummy_tool("write_a", False)])
    out = filter_tools_for_mode(registry=reg, mode="plan")
    names = {t.name for t in out}
    assert "exit_plan_mode_v2" in names
    assert "write_a" not in names


def test_adapter_agent_mode_repeated_user_injects_stall_guard(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    store.set_setting("AIA_EXPERT_PLAN_FILE_DIR", str(tmp_path / "plans"))
    sid = store.create_session("stall-test").id
    duplicate_line = "please handle this request"
    store.add_message(session_id=sid, role="user", content=duplicate_line, event_type="user_text")
    store.add_message(session_id=sid, role="assistant", content="I will analyze first…", event_type="assistant_text")
    dec = evaluate_for_expert_mode(
        store=store,
        session_id=sid,
        lang="en",
        requested_specialist="generalist",
        user_text=duplicate_line,
        execution_mode="agent",
        base_system_prompt="base",
    )
    assert dec.action == "run_agent"
    assert "Conversation stall guard" in str(dec.system_prompt_override or "")
    assert "base" in str(dec.system_prompt_override or "")


def test_adapter_plan_flow(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    store.set_setting("AIA_EXPERT_PLAN_FILE_DIR", str(tmp_path / "plans"))

    d1 = evaluate_for_expert_mode(
        store=store,
        session_id="s1",
        lang="zh",
        requested_specialist="generalist",
        user_text="帮我做一个功能",
        execution_mode="plan",
        base_system_prompt="base",
    )
    assert d1.action == "run_agent"
    assert isinstance(d1.plan_state, dict)
    assert str(d1.plan_state.get("mode") or "") == "plan"
    assert "base" in str(d1.system_prompt_override or "")

    d2 = evaluate_for_expert_mode(
        store=store,
        session_id="s1",
        lang="zh",
        requested_specialist="generalist",
        user_text="确认",
        execution_mode="agent",
        base_system_prompt="base",
    )
    assert d2.action == "run_agent"
    assert "base" in str(d2.system_prompt_override or "")


def test_adapter_confirm_blocked_until_agent_mode(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    store.set_setting("AIA_EXPERT_PLAN_FILE_DIR", str(tmp_path / "plans"))

    _ = evaluate_for_expert_mode(
        store=store,
        session_id="s2",
        lang="zh",
        requested_specialist="generalist",
        user_text="先给计划",
        execution_mode="plan",
        base_system_prompt="base",
    )
    d2 = evaluate_for_expert_mode(
        store=store,
        session_id="s2",
        lang="zh",
        requested_specialist="generalist",
        user_text="确认",
        execution_mode="plan",
        base_system_prompt="base",
    )
    assert d2.action == "stay_plan"
    assert "切换到 agent 模式" in str(d2.reply_text or "")


def test_adapter_confirm_strategy_auto_allows_confirm_in_plan_mode(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    store.set_setting("AIA_EXPERT_PLAN_FILE_DIR", str(tmp_path / "plans"))
    store.set_setting("AIA_EXPERT_PLAN_CONFIRM_STRATEGY", "auto")
    _ = evaluate_for_expert_mode(
        store=store,
        session_id="s-auto",
        lang="zh",
        requested_specialist="generalist",
        user_text="先给计划",
        execution_mode="plan",
        base_system_prompt="base",
    )
    d2 = evaluate_for_expert_mode(
        store=store,
        session_id="s-auto",
        lang="zh",
        requested_specialist="generalist",
        user_text="确认",
        execution_mode="plan",
        base_system_prompt="base",
    )
    assert d2.action == "run_agent"
    assert "已确认计划" in str(d2.reply_text or "")


def test_adapter_confirm_strategy_off_allows_confirm_in_plan_mode(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    store.set_setting("AIA_EXPERT_PLAN_FILE_DIR", str(tmp_path / "plans"))
    store.set_setting("AIA_EXPERT_PLAN_CONFIRM_STRATEGY", "off")
    _ = evaluate_for_expert_mode(
        store=store,
        session_id="s-off",
        lang="zh",
        requested_specialist="generalist",
        user_text="先给计划",
        execution_mode="plan",
        base_system_prompt="base",
    )
    d2 = evaluate_for_expert_mode(
        store=store,
        session_id="s-off",
        lang="zh",
        requested_specialist="generalist",
        user_text="确认",
        execution_mode="plan",
        base_system_prompt="base",
    )
    assert d2.action == "run_agent"
    assert "已确认计划" in str(d2.reply_text or "")


def test_adapter_plan_loop_guard_blocks_repeated_input(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    store.set_setting("AIA_EXPERT_PLAN_FILE_DIR", str(tmp_path / "plans"))
    common = dict(
        store=store,
        session_id="s-loop",
        lang="zh",
        requested_specialist="generalist",
        execution_mode="plan",
        base_system_prompt="base",
    )
    _ = evaluate_for_expert_mode(user_text="继续", **common)
    d2 = evaluate_for_expert_mode(user_text="继续", **common)
    assert d2.action == "stay_plan"
    assert "低信息续写" in str(d2.reply_text or "")


def test_adapter_plan_low_signal_continue_short_circuit(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    store.set_setting("AIA_EXPERT_PLAN_FILE_DIR", str(tmp_path / "plans"))
    _ = evaluate_for_expert_mode(
        store=store,
        session_id="s-low",
        lang="zh",
        requested_specialist="generalist",
        user_text="先给我一版计划",
        execution_mode="plan",
        base_system_prompt="base",
    )
    d2 = evaluate_for_expert_mode(
        store=store,
        session_id="s-low",
        lang="zh",
        requested_specialist="generalist",
        user_text="继续",
        execution_mode="plan",
        base_system_prompt="base",
    )
    assert d2.action == "stay_plan"
    assert "低信息续写" in str(d2.reply_text or "")


def test_prompt_prefix_uses_ccmini_like_phases(tmp_path: Path) -> None:
    plan_file = tmp_path / "plan.md"
    plan_file.write_text("# Plan\n", encoding="utf-8")
    st = PlanAgentStateV2(mode="plan", plan_path=str(plan_file))
    zh = build_plan_mode_prefix(state=st, lang="zh")
    en = build_plan_mode_prefix(state=st, lang="en")
    assert "阶段1：理解问题" in zh
    assert "计划工作流" in zh
    assert "计划模式工具" in zh
    assert "执行纪律" in zh
    assert "enter_plan_mode_v2" in zh
    assert "Phase 1: Initial Understanding" in en
    assert "Plan Workflow" in en
    assert "Plan mode tools" in en
    assert "Execution discipline" in en
    assert "enter_plan_mode_v2" in en


def test_shadow_tool_specs_work(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    store.set_setting("AIA_EXPERT_PLAN_FILE_DIR", str(tmp_path / "plans"))
    tools = materialize_plan_mode_v2_tools(store=store)
    assert len(tools) == 2
    enter = next(t for t in tools if t.name == "enter_plan_mode_v2")
    exit_tool = next(t for t in tools if t.name == "exit_plan_mode_v2")
    out1 = enter.handler({"session_id": "s-1", "owner_specialist": "generalist"})
    assert out1.get("ok") is True
    out2 = exit_tool.handler({"session_id": "s-1", "confirm": True})
    assert out2.get("ok") is True
    assert bool((out2.get("state") or {}).get("plan_confirmed")) is True


def test_shadow_plan_tools_emit_trace_when_trace_id(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    store.set_setting("AIA_EXPERT_PLAN_FILE_DIR", str(tmp_path / "plans"))
    tools = materialize_plan_mode_v2_tools(store=store)
    enter = next(t for t in tools if t.name == "enter_plan_mode_v2")
    exit_tool = next(t for t in tools if t.name == "exit_plan_mode_v2")
    enter.handler(
        {
            "session_id": "s-tr",
            "owner_specialist": "generalist",
            "trace_id": "tid-1",
            "parent_span_id": "ps-9",
        }
    )
    exit_tool.handler({"session_id": "s-tr", "confirm": False, "trace_id": "tid-1"})
    rows = store.list_trace_events_for_trace(session_id="s-tr", trace_id="tid-1")
    types = [r.get("event_type") for r in rows]
    assert "plan_mode_tool_enter" in types
    assert "plan_mode_tool_exit" in types
    enter_ev = next(r for r in rows if r.get("event_type") == "plan_mode_tool_enter")
    exit_ev = next(r for r in rows if r.get("event_type") == "plan_mode_tool_exit")
    assert (enter_ev.get("payload") or {}).get("tool") == "enter_plan_mode_v2"
    assert (exit_ev.get("payload") or {}).get("tool") == "exit_plan_mode_v2"
    assert (exit_ev.get("payload") or {}).get("confirmed") is False


def test_shadow_tool_specs_can_use_default_session_key(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    store.set_setting("AIA_EXPERT_PLAN_FILE_DIR", str(tmp_path / "plans"))
    store.set_setting("AIA_PLAN_AGENT_V2_DEFAULT_SESSION_ID", "s-default")
    tools = materialize_plan_mode_v2_tools(store=store)
    enter = next(t for t in tools if t.name == "enter_plan_mode_v2")
    out = enter.handler({})
    assert out.get("ok") is True
    st = out.get("state") or {}
    assert str(st.get("mode") or "") == "plan"


def test_switch_default_off_and_opt_in(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    assert v2_feature_enabled(store=store) is False
    assert should_route_to_v2(store=store, interaction_mode="expert") is False
    assert should_route_to_v2(store=store, interaction_mode="expert", force_flag=True) is True
    store.set_setting("AIA_EXPERT_PLAN_AGENT_V2_ENABLED", "1")
    assert v2_feature_enabled(store=store) is True
    assert should_route_to_v2(store=store, interaction_mode="expert") is True
    assert should_route_to_v2(store=store, interaction_mode="comprehensive") is False


def test_gateway_adapter_shadow_force_flag(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    store.set_setting("AIA_EXPERT_PLAN_FILE_DIR", str(tmp_path / "plans"))
    msg = StandardMessage(
        session_id="s1",
        tenant_id="t1",
        user_id="u1",
        role="user",
        channel="chat",
        text="帮我实现一个功能",
        attachments=[],
        metadata={},
    )
    out = evaluate_gateway_expert_turn_shadow(
        store=store,
        msg=msg,
        lang="zh",
        interaction_mode="expert",
        requested_specialist="generalist",
        base_system_prompt="base",
        force_flag=True,
    )
    assert out.used_v2 is True
    assert out.decision is not None
    assert out.decision.action == "run_agent"


def test_shadow_compat_result_shape(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    store.set_setting("AIA_EXPERT_PLAN_FILE_DIR", str(tmp_path / "plans"))
    dec = evaluate_for_expert_mode(
        store=store,
        session_id="s1",
        lang="zh",
        requested_specialist="generalist",
        user_text="我要改造",
        base_system_prompt="base",
    )
    row = build_shadow_gateway_result(
        decision=dec,
        run_id="r1",
        trace_id="t1",
        elapsed_ms=12,
        requested_specialist="generalist",
    )
    assert set(row.keys()) == legacy_gateway_result_keys()


def test_trace_helper_no_crash() -> None:
    events = []

    class _S:
        def add_trace_event(self, **kwargs):
            events.append(kwargs)

    emit_plan_agent_v2_trace(
        store=_S(),
        session_id="s1",
        trace_id="t1",
        parent_span_id=None,
        event_type="plan_mode_entered",
        payload={"x": 1},
    )
    assert len(events) == 1
    assert events[0].get("event_type") == "plan_mode_entered"


def test_shadow_gateway_result_defaults_align_legacy_baseline(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    store.set_setting("AIA_EXPERT_PLAN_FILE_DIR", str(tmp_path / "plans"))
    dec = evaluate_for_expert_mode(
        store=store,
        session_id="s1",
        lang="zh",
        requested_specialist="generalist",
        user_text="继续",
        base_system_prompt="base",
    )
    row = build_shadow_gateway_result(
        decision=dec,
        run_id="r1",
        trace_id="t1",
        elapsed_ms=1,
        requested_specialist="generalist",
    )
    # Baseline invariant fields expected by legacy result dataclass.
    baseline = OclawGatewayResult(run_id="r1", reply_text="", trace_id="t1", elapsed_ms=1)
    assert row["mode"] == baseline.mode
    assert row["task_id"] == baseline.task_id
    assert row["dynamic_agent_used"] == baseline.dynamic_agent_used
    assert row["dynamic_agent_name"] == baseline.dynamic_agent_name
    assert row["relay_pointer_count"] == baseline.relay_pointer_count
    assert row["relay_envelope_present"] == baseline.relay_envelope_present
    assert row["relay_envelope_pointer_count"] == baseline.relay_envelope_pointer_count
    assert row["relay_ttl_turn_count"] == baseline.relay_ttl_turn_count
    assert row["relay_ttl_session_count"] == baseline.relay_ttl_session_count
    assert row["relay_ttl_keep_count"] == baseline.relay_ttl_keep_count
    # Package export should be wired and callable.
    assert callable(should_route_to_v2_pkg)


def test_package_exports_stable_symbols() -> None:
    import oclaw.runtime.plan_agent_v2 as p

    required = [
        "PlanAgentStateV2",
        "PlanAgentStateStoreV2",
        "PlanModeManagerV2",
        "PlanAgentV2Decision",
        "GatewayPlanV2AdapterOutput",
        "evaluate_for_expert_mode",
        "evaluate_gateway_expert_turn_shadow",
        "should_route_to_v2",
        "v2_feature_enabled",
        "emit_plan_agent_v2_trace",
        "build_shadow_gateway_result",
        "legacy_gateway_result_keys",
    ]
    for name in required:
        assert hasattr(p, name), name

