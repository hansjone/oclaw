from __future__ import annotations

from oclaw.interfaces.admin.chat_api import (
    _persist_session_dialog_chat_settings,
    _persist_user_menu_chat_settings,
    _resolve_mode_settings,
)


class _DummyStore:
    def __init__(self) -> None:
        self._settings: dict[str, str] = {}

    def get_setting(self, key: str) -> str:
        return str(self._settings.get(key) or "")

    def set_setting(self, key: str, value: str) -> None:
        self._settings[str(key)] = str(value)


def test_mode_session_and_user_prefs_merge_for_gateway() -> None:
    store = _DummyStore()
    _persist_session_dialog_chat_settings(
        store=store,
        tenant_id="t1",
        user_id="u1",
        session_id="s1",
        memory_mode="default",
        execution_mode="plan",
    )
    _persist_user_menu_chat_settings(
        store=store,
        tenant_id="t1",
        user_id="u1",
        interaction_mode="expert",
        specialist="generalist",
        confirm_strategy="auto",
        plan_agent_version="v2",
    )
    interaction_mode, specialist, memory_mode, execution_mode, confirm_strategy, plan_agent_version = (
        _resolve_mode_settings(store=store, tenant_id="t1", user_id="u1", session_id="s1")
    )
    assert interaction_mode == "expert"
    assert specialist == "generalist"
    assert memory_mode == "default"
    assert execution_mode == "plan"
    assert confirm_strategy == "auto"
    assert plan_agent_version == "v2"


def test_mode_session_defaults_when_session_keys_missing() -> None:
    store = _DummyStore()
    store.set_setting("chat.user.mode.t1.u1.confirm_strategy", "invalid")
    interaction_mode, specialist, memory_mode, execution_mode, confirm_strategy, plan_agent_version = (
        _resolve_mode_settings(store=store, tenant_id="t1", user_id="u1", session_id="s1")
    )
    assert interaction_mode == "expert"
    assert specialist == "generalist"
    assert memory_mode == "default"
    assert execution_mode == "agent"
    assert confirm_strategy == "strict"
    assert plan_agent_version == "v1"


def test_invalid_execution_mode_on_session_dialog_falls_back_to_agent() -> None:
    store = _DummyStore()
    store.set_setting("chat.session.mode.t1.u1.s1.execution_mode", "invalid")
    interaction_mode, specialist, memory_mode, execution_mode, confirm_strategy, plan_agent_version = (
        _resolve_mode_settings(store=store, tenant_id="t1", user_id="u1", session_id="s1")
    )
    assert execution_mode == "agent"
    assert interaction_mode == "expert"


def test_invalid_confirm_strategy_on_user_menu_falls_back_to_strict() -> None:
    store = _DummyStore()
    store.set_setting("chat.user.mode.t1.u1.confirm_strategy", "invalid")
    interaction_mode, specialist, memory_mode, execution_mode, confirm_strategy, plan_agent_version = (
        _resolve_mode_settings(store=store, tenant_id="t1", user_id="u1", session_id="s1")
    )
    assert confirm_strategy == "strict"
    assert specialist == "generalist"
