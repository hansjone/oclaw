from __future__ import annotations

from runtime.agents import specialists as specialists_mod


def test_unknown_dynamic_specialist_defaults_to_minimum_expert_permissions(monkeypatch) -> None:
    monkeypatch.setattr(specialists_mod, "discover_specialist_ids", lambda: ("generalist", "qa"))
    assert specialists_mod.expert_name_for_specialist("qa") == "generalist"


def test_agent_role_ids_uses_runtime_discovery(monkeypatch) -> None:
    monkeypatch.setattr(specialists_mod, "discover_specialist_ids", lambda: ("generalist", "ops", "qa"))
    got = specialists_mod.agent_role_ids()
    assert got[0] == specialists_mod.MANAGER_AGENT_ID
    assert "qa" in set(got)


def test_builtin_specialists_include_memory_tools() -> None:
    assert "memory" in specialists_mod.expert_name_for_specialist("generalist")
    assert "memory" in specialists_mod.expert_name_for_specialist("ops")
