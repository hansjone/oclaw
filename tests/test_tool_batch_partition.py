from __future__ import annotations

from runtime.chat.tool_runtime import partition_tool_use_batches
from svc.llm.chat_models import LLMToolCall
from runtime.tools.base import ToolRegistry, ToolSpec


def _spec(name: str, *, read_only: bool) -> ToolSpec:
    return ToolSpec(
        name=name,
        description="t",
        parameters={"type": "object", "properties": {}},
        handler=lambda _a: {"ok": True},
        read_only=read_only,
    )


def test_partition_merges_consecutive_read_only() -> None:
    reg = ToolRegistry([_spec("a", read_only=True), _spec("b", read_only=True), _spec("c", read_only=False)])
    calls = [
        LLMToolCall(id="1", name="a", arguments={}),
        LLMToolCall(id="2", name="b", arguments={}),
        LLMToolCall(id="3", name="c", arguments={}),
        LLMToolCall(id="4", name="a", arguments={}),
    ]
    batches = partition_tool_use_batches(calls, reg)
    assert [len(b) for b in batches] == [2, 1, 1]
    assert [tc.id for b in batches for tc in b] == ["1", "2", "3", "4"]


def test_partition_unknown_tool_is_sequential_only() -> None:
    reg = ToolRegistry([_spec("a", read_only=True)])
    calls = [
        LLMToolCall(id="1", name="a", arguments={}),
        LLMToolCall(id="2", name="missing", arguments={}),
        LLMToolCall(id="3", name="a", arguments={}),
    ]
    batches = partition_tool_use_batches(calls, reg)
    assert [len(b) for b in batches] == [1, 1, 1]
