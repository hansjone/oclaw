from __future__ import annotations

from unittest.mock import patch

from oclaw.runtime.tools.base import ToolSpec
from oclaw.runtime.tools.catalog import materialize_tool_specs


def _mk_spec(name: str) -> ToolSpec:
    return ToolSpec(
        name=name,
        description="d",
        parameters={"type": "object", "properties": {}},
        handler=lambda _args: {"ok": True},
        tags=frozenset({"internal"}),
    )


def _mk_spec_with_risk(name: str, *, risk: str, tags: set[str] | None = None) -> ToolSpec:
    return ToolSpec(
        name=name,
        description="d",
        parameters={"type": "object", "properties": {}},
        handler=lambda _args: {"ok": True},
        tags=frozenset(tags or {"internal"}),
        risk_level=risk,
    )


def test_catalog_loads_role_scoped_expert_tools() -> None:
    with patch(
        "oclaw.runtime.tools.catalog.materialize_tools_for_expert",
        return_value=[_mk_spec("custom_tool_a"), _mk_spec("custom_tool_b")],
    ):
        with patch("oclaw.runtime.tools.catalog.materialize_public_tools", return_value=[_mk_spec("system_time")]):
            specs = materialize_tool_specs(expert="generalist")
    names = {x.name for x in specs}
    assert "system_time" in names
    assert "custom_tool_a" in names
    assert "custom_tool_b" in names


def test_catalog_deduplicates_same_tool_name() -> None:
    with patch(
        "oclaw.runtime.tools.catalog.materialize_tools_for_expert",
        return_value=[_mk_spec("system_time"), _mk_spec("custom_tool_a")],
    ):
        with patch("oclaw.runtime.tools.catalog.materialize_public_tools", return_value=[_mk_spec("system_time")]):
            specs = materialize_tool_specs(expert="generalist")
    names = [x.name for x in specs]
    assert names.count("system_time") == 1
    assert "custom_tool_a" in set(names)


def test_catalog_prefers_lower_risk_on_name_conflict() -> None:
    with patch(
        "oclaw.runtime.tools.catalog.materialize_tools_for_expert",
        return_value=[_mk_spec_with_risk("dup_tool", risk="high")],
    ):
        with patch(
            "oclaw.runtime.tools.catalog.materialize_public_tools",
            return_value=[_mk_spec_with_risk("dup_tool", risk="low")],
        ):
            specs = materialize_tool_specs(expert="generalist")
    matched = [x for x in specs if x.name == "dup_tool"]
    assert len(matched) == 1
    assert str(matched[0].risk_level) == "low"


def test_catalog_prefers_expert_when_risk_equal() -> None:
    with patch(
        "oclaw.runtime.tools.catalog.materialize_tools_for_expert",
        return_value=[_mk_spec_with_risk("dup_tool", risk="low", tags={"expert"})],
    ):
        with patch(
            "oclaw.runtime.tools.catalog.materialize_public_tools",
            return_value=[_mk_spec_with_risk("dup_tool", risk="low", tags={"public"})],
        ):
            specs = materialize_tool_specs(expert="generalist")
    matched = [x for x in specs if x.name == "dup_tool"]
    assert len(matched) == 1
    # expert source should win tie-break.
    assert "expert" in set(matched[0].tags or frozenset())

