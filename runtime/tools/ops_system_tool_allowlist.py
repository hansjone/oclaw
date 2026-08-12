"""Slim system (public/plugin) tools for field ops; MCP remains unbound by this list.

Allowlist from production ops usage: deliverable/xlsx, light FS read, memory wiki core,
schedule/jobs (live field cron), and fetch_tool_result. Drop web/sleep/process and
low-use attachment helpers from the model wire.
"""

from __future__ import annotations

import os
from typing import Any, Iterable

# Roles that get the slim public/plugin surface. MCP + expert tools are never filtered here.
_OPS_SLIM_SPECIALISTS = frozenset({"ops"})

# Field ops essentials (non-MCP). Keep schedule/jobs for live field cron management.
# Omit web_*, sleep, list_processes, image helpers, and wiki lint/status.
_OPS_SYSTEM_TOOL_ALLOWLIST = frozenset(
    {
        # Deliverables / tabular (top field volume)
        "write_xlsx",
        "save_deliverable_attachment",
        "attachment_local_url",
        "run_tabular_sql",
        "query_tabular_attachment",
        "query_text_attachment",
        # Memory wiki core
        "memory_wiki_search",
        "memory_wiki_apply",
        "memory_wiki_get",
        # Light workspace read (for CLI/report side artifacts)
        "read_file",
        "glob",
        "grep",
        "get_cwd",
        "list_directory",
        "search_files",
        # Schedule / jobs — field runs cron live; keep full manage surface
        "schedule_list",
        "schedule_create",
        "schedule_propose",
        "schedule_delete",
        "schedule_run_now",
        "schedule_update",
        "schedule_resume",
        "schedule_pause",
        "get_job",
        "list_jobs",
        # Misc
        "system_time",
        "get_env",
        # Compact tool-result refetch
        "fetch_tool_result",
        # Background NE CLI poll
        "get_ne_exec_job",
    }
)


def ops_system_tool_slim_enabled() -> bool:
    raw = str(os.getenv("AIA_OPS_SYSTEM_TOOL_SLIM") or "").strip().lower()
    if not raw:
        return True
    return raw in {"1", "true", "yes", "on"}


def should_slim_system_tools_for_specialist(specialist: str | None) -> bool:
    if not ops_system_tool_slim_enabled():
        return False
    return str(specialist or "").strip().lower() in _OPS_SLIM_SPECIALISTS


def ops_system_tool_allowlist() -> frozenset[str]:
    """Allowlist; optional env override replaces the default set entirely."""
    raw = str(os.getenv("AIA_OPS_SYSTEM_TOOL_ALLOWLIST") or "").strip()
    if raw:
        return frozenset(x.strip() for x in raw.split(",") if x.strip())
    return _OPS_SYSTEM_TOOL_ALLOWLIST


def is_ops_system_tool_allowed(name: str) -> bool:
    return str(name or "").strip() in ops_system_tool_allowlist()


def filter_system_tool_specs(
    tools: Iterable[Any],
    *,
    specialist: str | None,
) -> list[Any]:
    """Drop public/plugin ToolSpecs not on the ops allowlist. No-op for other roles."""
    if not should_slim_system_tools_for_specialist(specialist):
        return list(tools or [])
    allow = ops_system_tool_allowlist()
    out: list[Any] = []
    for spec in tools or []:
        name = str(getattr(spec, "name", "") or "").strip()
        if name in allow:
            out.append(spec)
    return out


def filter_collected_tool_sources(
    collected: list[tuple[str, Any]],
    *,
    specialist: str | None,
) -> list[tuple[str, Any]]:
    """Filter (source, spec) pairs: only slim ``public`` / ``plugin``; keep mcp/expert."""
    if not should_slim_system_tools_for_specialist(specialist):
        return list(collected or [])
    allow = ops_system_tool_allowlist()
    out: list[tuple[str, Any]] = []
    for source, spec in collected or []:
        src = str(source or "").strip().lower()
        if src in {"mcp", "expert"}:
            out.append((source, spec))
            continue
        name = str(getattr(spec, "name", "") or "").strip()
        if name in allow:
            out.append((source, spec))
    return out


__all__ = [
    "filter_collected_tool_sources",
    "filter_system_tool_specs",
    "is_ops_system_tool_allowed",
    "ops_system_tool_allowlist",
    "ops_system_tool_slim_enabled",
    "should_slim_system_tools_for_specialist",
]
