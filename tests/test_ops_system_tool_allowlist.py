from __future__ import annotations

from runtime.tools.base import ToolSpec
from runtime.tools.ops_system_tool_allowlist import (
    filter_collected_tool_sources,
    filter_system_tool_specs,
    ops_system_tool_allowlist,
    should_slim_system_tools_for_specialist,
)


def _spec(name: str) -> ToolSpec:
    return ToolSpec(
        name=name,
        description="t",
        parameters={"type": "object", "properties": {}},
        handler=lambda _a: {"ok": True},
    )


def test_ops_slim_applies_only_to_ops(monkeypatch) -> None:
    monkeypatch.delenv("AIA_OPS_SYSTEM_TOOL_SLIM", raising=False)
    assert should_slim_system_tools_for_specialist("ops")
    assert not should_slim_system_tools_for_specialist("generalist")
    assert not should_slim_system_tools_for_specialist("memory")


def test_ops_slim_can_disable(monkeypatch) -> None:
    monkeypatch.setenv("AIA_OPS_SYSTEM_TOOL_SLIM", "0")
    assert not should_slim_system_tools_for_specialist("ops")


def test_filter_system_keeps_allowlisted_only() -> None:
    tools = [
        _spec("write_xlsx"),
        _spec("git_status"),
        _spec("bailian_webparser"),
        _spec("fetch_tool_result"),
        _spec("system_time"),
    ]
    kept = filter_system_tool_specs(tools, specialist="ops")
    names = {t.name for t in kept}
    assert names == {"write_xlsx", "fetch_tool_result", "system_time"}
    assert len(filter_system_tool_specs(tools, specialist="generalist")) == 5


def test_filter_collected_keeps_mcp_and_expert() -> None:
    collected = [
        ("public", _spec("git_status")),
        ("public", _spec("write_xlsx")),
        ("expert", _spec("ume_alarm_xlsx_report")),
        ("mcp", _spec("mcp__netx__execManagedNe")),
        ("plugin", _spec("cloudflare_image_generate")),
    ]
    out = filter_collected_tool_sources(collected, specialist="ops")
    names = [(s, t.name) for s, t in out]
    assert ("mcp", "mcp__netx__execManagedNe") in names
    assert ("expert", "ume_alarm_xlsx_report") in names
    assert ("public", "write_xlsx") in names
    assert ("public", "git_status") not in names
    assert ("plugin", "cloudflare_image_generate") not in names


def test_allowlist_env_override(monkeypatch) -> None:
    monkeypatch.setenv("AIA_OPS_SYSTEM_TOOL_ALLOWLIST", "system_time,write_xlsx")
    assert ops_system_tool_allowlist() == frozenset({"system_time", "write_xlsx"})
