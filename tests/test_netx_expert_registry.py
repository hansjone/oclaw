"""Expert registry: inline netx_* tools removed; MCP only."""

from __future__ import annotations

import pytest

from runtime.tools import expert_registry


@pytest.fixture(autouse=True)
def _clear_expert_cache():
    expert_registry._CACHED_FACTORIES_BY_EXPERT = None
    expert_registry._CACHED_SPECS_BY_EXPERT = None
    yield
    expert_registry._CACHED_FACTORIES_BY_EXPERT = None
    expert_registry._CACHED_SPECS_BY_EXPERT = None


def test_netx_inline_tools_never_registered(monkeypatch):
    monkeypatch.setenv("OCLAW_NETX_BUILTIN_TOOLS", "1")
    factories = expert_registry.discover_expert_tool_factories()
    network_ops = factories.get("network_ops") or []
    names = {f().name for f in network_ops}
    assert not any(n.startswith("netx_") for n in names)
    assert "ume_alarm_xlsx_report" in names
