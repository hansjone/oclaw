from __future__ import annotations

from pathlib import Path

from oclaw.runtime.system_prompt import build_oclaw_executor_system_prompt
from oclaw.runtime.types import OclawMemoryContext
from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.runtime.tools.base import ToolRegistry, ToolSpec


def _spec(name: str) -> ToolSpec:
    return ToolSpec(
        name=name,
        description="d",
        parameters={"type": "object", "properties": {}},
        handler=lambda _a: {"ok": True},
        read_only=True,
    )


def test_build_oclaw_executor_system_prompt_includes_skills_block(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "sp.sqlite"))
    store.create_session("s")
    reg = ToolRegistry([_spec("demo_tool")])
    out = build_oclaw_executor_system_prompt(
        store=store,
        tools=reg,
        base_url="",
        base_system="You are helpful.",
        memory_context=OclawMemoryContext(),
        lang="zh",
    )
    assert "<available_skills>" in out


def test_build_oclaw_executor_system_prompt_without_tools_has_no_skills_block(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "sp1.sqlite"))
    store.create_session("s")
    out = build_oclaw_executor_system_prompt(
        store=store,
        tools=None,
        base_url="",
        base_system="  plain  ",
        memory_context=OclawMemoryContext(),
        lang="zh",
    )
    assert "<available_skills>" not in out


def test_build_oclaw_executor_system_prompt_with_tools_has_skills(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "sp2.sqlite"))
    store.create_session("s")
    reg = ToolRegistry([_spec("x")])
    out = build_oclaw_executor_system_prompt(
        store=store,
        tools=reg,
        base_url="",
        base_system="base",
        memory_context=OclawMemoryContext(),
        lang="zh",
    )
    assert "<available_skills>" in out
