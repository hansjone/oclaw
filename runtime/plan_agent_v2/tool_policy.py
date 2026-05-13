from __future__ import annotations

from typing import Iterable

from .models import PLAN_MODE_PLAN
from runtime.tools.base import ToolRegistry, ToolSpec


_DEFAULT_PLAN_ALLOWLIST = frozenset(
    {
        "read_file",
        "search_files",
        "glob",
        "list_directory",
        "list_workspace_tree",
        "search_files_context",
        "system_time",
        # Plan-mode control tools are non-read-only by design, but must stay callable.
        "enter_plan_mode_v2",
        "exit_plan_mode_v2",
    }
)


def plan_mode_allowed_tool_names(extra_allowed: Iterable[str] | None = None) -> set[str]:
    out = set(_DEFAULT_PLAN_ALLOWLIST)
    for x in (extra_allowed or []):
        n = str(x or "").strip()
        if n:
            out.add(n)
    return out


def filter_tools_for_mode(
    *,
    registry: ToolRegistry,
    mode: str,
    extra_allowed: Iterable[str] | None = None,
) -> list[ToolSpec]:
    tools = list(registry.list())
    if str(mode or "").strip().lower() != PLAN_MODE_PLAN:
        return tools
    allow = plan_mode_allowed_tool_names(extra_allowed=extra_allowed)
    out: list[ToolSpec] = []
    for t in tools:
        if t.name in allow or bool(t.is_read_only()):
            out.append(t)
    return out


__all__ = ["filter_tools_for_mode", "plan_mode_allowed_tool_names"]

