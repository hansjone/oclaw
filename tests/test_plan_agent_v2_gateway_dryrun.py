from __future__ import annotations

from pathlib import Path

from svc.persistence.sqlite_store import SqliteStore
from runtime.gateway import OclawGatewayResult
from runtime.plan_agent_v2 import (
    build_shadow_gateway_result,
    evaluate_gateway_expert_turn_shadow,
    legacy_gateway_result_keys,
)
from runtime.types import StandardMessage


def _msg(text: str) -> StandardMessage:
    return StandardMessage(
        session_id="sess-dryrun",
        tenant_id="tenant-1",
        user_id="user-1",
        role="user",
        channel="chat",
        text=text,
        attachments=[],
        metadata={},
    )


def test_gateway_shadow_stays_off_without_force_or_flag(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    out = evaluate_gateway_expert_turn_shadow(
        store=store,
        msg=_msg("实现一个功能"),
        lang="zh",
        interaction_mode="expert",
        requested_specialist="generalist",
        base_system_prompt="base-system",
        force_flag=False,
    )
    assert out.used_v2 is False
    assert out.decision is None


def test_gateway_shadow_force_path_matches_legacy_shape(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    store.set_setting("AIA_EXPERT_PLAN_FILE_DIR", str(tmp_path / "plans"))
    out = evaluate_gateway_expert_turn_shadow(
        store=store,
        msg=_msg("请先给计划"),
        lang="zh",
        interaction_mode="expert",
        requested_specialist="generalist",
        base_system_prompt="base-system",
        force_flag=True,
    )
    assert out.used_v2 is True
    assert out.decision is not None

    shadow_row = build_shadow_gateway_result(
        decision=out.decision,
        run_id="run-1",
        trace_id="trace-1",
        elapsed_ms=9,
        requested_specialist="generalist",
    )
    assert set(shadow_row.keys()) == legacy_gateway_result_keys()

    baseline = OclawGatewayResult(run_id="run-1", reply_text="", trace_id="trace-1", elapsed_ms=9)
    assert shadow_row["mode"] == baseline.mode
    assert shadow_row["task_id"] == baseline.task_id
    assert shadow_row["dynamic_agent_used"] == baseline.dynamic_agent_used
    assert shadow_row["relay_pointer_count"] == baseline.relay_pointer_count


def test_gateway_shadow_confirm_path_builds_compatible_result(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    store.set_setting("AIA_EXPERT_PLAN_FILE_DIR", str(tmp_path / "plans"))

    # Enter plan
    first = evaluate_gateway_expert_turn_shadow(
        store=store,
        msg=_msg("我要改造一下"),
        lang="zh",
        interaction_mode="expert",
        requested_specialist="generalist",
        base_system_prompt="base-system",
        force_flag=True,
    )
    assert first.used_v2 is True
    assert first.decision is not None
    assert first.decision.action == "run_agent"
    assert "base-system" in str(first.decision.system_prompt_override or "")

    # Confirm plan
    second = evaluate_gateway_expert_turn_shadow(
        store=store,
        msg=_msg("确认"),
        lang="zh",
        interaction_mode="expert",
        requested_specialist="generalist",
        base_system_prompt="base-system",
        force_flag=True,
    )
    assert second.used_v2 is True
    assert second.decision is not None
    assert second.decision.action == "stay_plan"
    assert "切换到 agent 模式" in str(second.decision.reply_text or "")

    row = build_shadow_gateway_result(
        decision=second.decision,
        run_id="run-2",
        trace_id="trace-2",
        elapsed_ms=12,
        requested_specialist="generalist",
    )
    assert row["interaction_mode"] == "expert"
    assert str(row["dispatch_reason"]).startswith("plan_agent_v2:")


def test_gateway_shadow_skips_v2_when_metadata_plan_agent_version_v1(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    store.set_setting("AIA_EXPERT_PLAN_FILE_DIR", str(tmp_path / "plans"))
    out = evaluate_gateway_expert_turn_shadow(
        store=store,
        msg=StandardMessage(
            session_id="sess-dryrun",
            tenant_id="tenant-1",
            user_id="user-1",
            role="user",
            channel="chat",
            text="请先给计划",
            attachments=[],
            metadata={"plan_agent_version": "v1"},
        ),
        lang="zh",
        interaction_mode="expert",
        requested_specialist="generalist",
        base_system_prompt="base-system",
        force_flag=True,
    )
    assert out.used_v2 is False
    assert out.decision is None

