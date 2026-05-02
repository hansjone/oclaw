from __future__ import annotations

from pathlib import Path

from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.runtime.plan_agent_v2_gateway_cutover import maybe_handle_expert_turn_v2_draft
from oclaw.runtime.types import StandardMessage


def _msg(text: str) -> StandardMessage:
    return StandardMessage(
        session_id="cutover-s1",
        tenant_id="t1",
        user_id="u1",
        role="user",
        channel="chat",
        text=text,
        attachments=[],
        metadata={},
    )


def test_cutover_draft_off_by_default(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    out = maybe_handle_expert_turn_v2_draft(
        store=store,
        msg=_msg("hello"),
        lang="zh",
        interaction_mode="expert",
        requested_specialist="generalist",
        base_system_prompt="base",
        force_flag=False,
    )
    assert out.handled is False
    assert out.result is None


def test_cutover_draft_plan_reply_when_forced(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    store.set_setting("AIA_EXPERT_PLAN_FILE_DIR", str(tmp_path / "plans"))
    out = maybe_handle_expert_turn_v2_draft(
        store=store,
        msg=_msg("我要做改造"),
        lang="zh",
        interaction_mode="expert",
        requested_specialist="generalist",
        base_system_prompt="base",
        force_flag=True,
    )
    assert out.handled is False
    assert out.result is None
    assert out.decision_action == "run_agent"
    assert "base" in str(out.system_prompt_override or "")


def test_cutover_draft_run_agent_returns_prompt_override(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    store.set_setting("AIA_EXPERT_PLAN_FILE_DIR", str(tmp_path / "plans"))
    _ = maybe_handle_expert_turn_v2_draft(
        store=store,
        msg=_msg("先给个计划"),
        lang="zh",
        interaction_mode="expert",
        requested_specialist="generalist",
        base_system_prompt="base",
        force_flag=True,
    )
    out = maybe_handle_expert_turn_v2_draft(
        store=store,
        msg=_msg("确认"),
        lang="zh",
        interaction_mode="expert",
        requested_specialist="generalist",
        base_system_prompt="base",
        force_flag=True,
    )
    assert out.decision_action == "stay_plan"
    assert out.handled is True
    assert out.result is not None

