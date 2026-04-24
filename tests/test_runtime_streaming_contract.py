from __future__ import annotations

from pathlib import Path

from oclaw.runtime.direct_loop import run_oclaw_direct_loop
from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.runtime.tools.base import ToolRegistry, ToolSpec
from oclaw.platform.llm.transports.base import LLMResponse, LLMToolCall


class _TwoChunkModel:
    def chat(self, messages, tools, *, on_token=None):
        if on_token:
            on_token("A")
            on_token("B")
        return LLMResponse(content="AB", tool_calls=[])


class _OneToolThenFinalModel:
    def __init__(self) -> None:
        self._n = 0

    def chat(self, messages, tools, *, on_token=None):
        self._n += 1
        if self._n == 1:
            return LLMResponse(
                content="",
                tool_calls=[LLMToolCall(id="call_1", name="echo_tool", arguments={"x": "ok"})],
            )
        if on_token:
            on_token("done")
        return LLMResponse(content="done", tool_calls=[])


def test_direct_loop_propagates_on_token_streaming(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "s.sqlite"))
    sess = store.create_session("t")
    seen: list[str] = []
    out = run_oclaw_direct_loop(
        store=store,
        session_id=sess.id,
        lang="zh",
        system_prompt="sys",
        model=_TwoChunkModel(),
        tools=ToolRegistry([]),
        user_text="hi",
        on_token=seen.append,
    )
    assert out.final_text == "AB"
    assert "".join(seen) == "AB"


def test_direct_loop_supports_multi_round_tool_then_final(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "t.sqlite"))
    sess = store.create_session("t")

    def _echo(args):
        return {"ok": True, "echo": args.get("x")}

    tools = ToolRegistry(
        [
            ToolSpec(
                name="echo_tool",
                description="echo",
                parameters={"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]},
                handler=_echo,
                tags=frozenset({"test"}),
            )
        ]
    )
    out = run_oclaw_direct_loop(
        store=store,
        session_id=sess.id,
        lang="zh",
        system_prompt="sys",
        model=_OneToolThenFinalModel(),
        tools=tools,
        user_text="hi",
        max_tool_rounds=3,
    )
    assert out.final_text == "done"

