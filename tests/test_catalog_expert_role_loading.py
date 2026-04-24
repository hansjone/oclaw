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

