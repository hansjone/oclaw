"""Expert registry: netx builtin tools gated by OCLAW_NETX_BUILTIN_TOOLS."""

from __future__ import annotations

import os

import pytest

from runtime.tools import expert_registry


@pytest.fixture(autouse=True)
def _clear_expert_cache():
    expert_registry._CACHED_FACTORIES_BY_EXPERT = None
    expert_registry._CACHED_SPECS_BY_EXPERT = None
    yield
    expert_registry._CACHED_FACTORIES_BY_EXPERT = None
    expert_registry._CACHED_SPECS_BY_EXPERT = None


def test_netx_tools_skipped_when_builtin_disabled(monkeypatch):
    monkeypatch.delenv("OCLAW_NETX_BUILTIN_TOOLS", raising=False)
    factories = expert_registry.discover_expert_tool_factories()
    network_ops = factories.get("network_ops") or []
    names = {f().name for f in network_ops}
    assert not any(n.startswith("netx_") for n in names)


def test_netx_tools_registered_when_builtin_enabled(monkeypatch):
    monkeypatch.setenv("OCLAW_NETX_BUILTIN_TOOLS", "1")
    factories = expert_registry.discover_expert_tool_factories()
    network_ops = factories.get("network_ops") or []
    names = {f().name for f in network_ops}
    assert "netx_query_ume_alarms" in names
    assert "netx_exec_managed_ne" in names
