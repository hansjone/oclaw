from __future__ import annotations

from runtime.tools.catalog import default_registry


def test_skill_install_public_tools_hidden_for_specialist_auto_only() -> None:
    names = [t.name for t in default_registry(expert="network_ops+memory", specialist="ops").list()]
    assert "skill_market_install" not in names
    assert "skill_registry_install" not in names

