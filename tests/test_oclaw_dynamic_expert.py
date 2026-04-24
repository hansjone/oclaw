from __future__ import annotations

from oclaw.runtime.tools.base import ToolSpec
from oclaw.runtime.tools.catalog import _apply_declared_tool_policy


def _tool(name: str, tags: set[str]) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=name,
        parameters={"type": "object", "properties": {}},
        handler=lambda _args: {"ok": True},
        tags=frozenset(tags),
    )


def test_declared_tool_policy_filters_by_tags_and_names() -> None:
    tools = [
        _tool("search_workspace", {"search", "read"}),
        _tool("run_command", {"shell", "exec"}),
        _tool("read_file", {"read", "fs"}),
    ]
    out = _apply_declared_tool_policy(
        tools,
        allow_tags=["read"],
        allow_tools=["run_command"],
    )
    names = {t.name for t in out}
    assert "search_workspace" in names
    assert "read_file" in names
    assert "run_command" in names


def test_declared_tool_policy_empty_rules_returns_original() -> None:
    tools = [_tool("a", {"x"}), _tool("b", {"y"})]
    out = _apply_declared_tool_policy(tools, allow_tags=[], allow_tools=[])
    assert [t.name for t in out] == ["a", "b"]

