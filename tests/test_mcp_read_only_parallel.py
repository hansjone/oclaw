from __future__ import annotations

from runtime.tools.base import ToolRegistry, ToolSpec
from runtime.tools.mcp.adapter import _MCP_READ_ONLY_TOOLS, _McpBoundTool, mcp_timeout_for_tool


def test_list_query_mcp_tools_marked_read_only() -> None:
    for name in ("listManagedNe", "queryUmeAlarmsRaw", "listCliTargets", "findTopologyPaths"):
        assert name in _MCP_READ_ONLY_TOOLS
        spec = _McpBoundTool(
            server_id="netx",
            tool_name=name,
            description="t",
            parameters={"type": "object", "properties": {}},
            command=["echo"],
        ).to_spec()
        assert spec.read_only is True
        assert spec.name == f"mcp__netx__{name}"


def test_exec_managed_ne_not_read_only_use_batch_instead() -> None:
    assert "execManagedNe" not in _MCP_READ_ONLY_TOOLS
    spec = _McpBoundTool(
        server_id="netx",
        tool_name="execManagedNe",
        description="t",
        parameters={"type": "object", "properties": {}},
        command=["echo"],
    ).to_spec()
    assert spec.read_only is False


def test_exec_managed_ne_timeout_allows_batch_wall_clock() -> None:
    assert mcp_timeout_for_tool("execManagedNe", 30.0) >= 600.0


def test_partition_would_parallelize_consecutive_list_tools() -> None:
    from runtime.chat.tool_runtime import partition_tool_use_batches
    from svc.llm.chat_models import LLMToolCall

    reg = ToolRegistry(
        [
            ToolSpec(
                name="mcp__netx__listManagedNe",
                description="a",
                parameters={},
                handler=lambda _a: {"ok": True},
                read_only=True,
            ),
            ToolSpec(
                name="mcp__netx__queryUmeAlarmsRaw",
                description="b",
                parameters={},
                handler=lambda _a: {"ok": True},
                read_only=True,
            ),
        ]
    )
    calls = [
        LLMToolCall(id="1", name="mcp__netx__listManagedNe", arguments={}),
        LLMToolCall(id="2", name="mcp__netx__queryUmeAlarmsRaw", arguments={}),
    ]
    batches = partition_tool_use_batches(calls, reg)
    assert len(batches) == 1
    assert len(batches[0]) == 2
