from __future__ import annotations

from pathlib import Path

from oclaw.openclaw_runtime.system_prompt import build_openclaw_executor_system_prompt
from oclaw.openclaw_runtime.types import OpenClawMemoryContext
from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.tools.base import ToolRegistry, ToolSpec


def _spec(name: str) -> ToolSpec:
    return ToolSpec(
        name=name,
        description="d",
        parameters={"type": "object", "properties": {}},
        handler=lambda _a: {"ok": True},
        read_only=True,
    )


def test_build_openclaw_executor_system_prompt_includes_skills_block(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "sp.sqlite"))
    store.create_session("s")
    reg = ToolRegistry([_spec("demo_tool")])
    out = build_openclaw_executor_system_prompt(
        store=store,
        tools=reg,
        base_url="",
        base_system="You are helpful.",
        memory_context=OpenClawMemoryContext(),
        lang="zh",
    )
    assert "<available_skills>" in out


def test_build_openclaw_executor_system_prompt_without_tools_has_no_skills_block(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "sp1.sqlite"))
    store.create_session("s")
    out = build_openclaw_executor_system_prompt(
        store=store,
        tools=None,
        base_url="",
        base_system="  plain  ",
        memory_context=OpenClawMemoryContext(),
        lang="zh",
    )
    assert "<available_skills>" not in out


def test_build_openclaw_executor_system_prompt_with_tools_has_skills(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "sp2.sqlite"))
    store.create_session("s")
    reg = ToolRegistry([_spec("x")])
    out = build_openclaw_executor_system_prompt(
        store=store,
        tools=reg,
        base_url="",
        base_system="base",
        memory_context=OpenClawMemoryContext(),
        lang="zh",
    )
    assert "<available_skills>" in out
