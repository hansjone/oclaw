from __future__ import annotations

from oclaw.runtime.agent_core_attempt import _should_after_turn_memory
from oclaw.runtime.types import StandardMessage


def _msg(interaction_mode: str, extra: dict | None = None) -> StandardMessage:
    md = {"interaction_mode": interaction_mode}
    if isinstance(extra, dict):
        md.update(extra)
    return StandardMessage(
        session_id="s1",
        tenant_id="t1",
        user_id="u1",
        role="member",
        channel="admin_chat",
        text="hello",
        attachments=[],
        metadata=md,
    )


def test_after_turn_memory_disabled_for_comprehensive_mode() -> None:
    assert _should_after_turn_memory(_msg("comprehensive")) is False


def test_after_turn_memory_disabled_for_expert_mode_by_default() -> None:
    assert _should_after_turn_memory(_msg("expert")) is False


def test_after_turn_memory_cannot_be_forced_by_metadata() -> None:
    assert _should_after_turn_memory(_msg("expert", {"enable_after_turn_memory": True})) is False

