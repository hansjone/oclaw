from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from oclaw.platform.config.paths import PROJECT_ROOT
from oclaw.tools.base import ToolSpec


def _plugin_cfg() -> dict[str, Any]:
    cfg_path = (PROJECT_ROOT / "oclaw" / "oclaw.json").resolve()
    if not cfg_path.exists():
        return {}
    try:
        import json

        obj = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    plugins = obj.get("plugins") if isinstance(obj, dict) else {}
    entries = plugins.get("entries") if isinstance(plugins, dict) else {}
    entry = entries.get("memory-wiki") if isinstance(entries, dict) else {}
    return entry if isinstance(entry, dict) else {}


def _wiki_handlers() -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
    api_path = (PROJECT_ROOT / "oclaw" / "extensions" / "memory-wiki" / "api.py").resolve()
    spec = importlib.util.spec_from_file_location("memory_curator_wiki_api", str(api_path))
    if spec is None or spec.loader is None:
        return {}
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[assignment]
    fn = getattr(mod, "build_wiki_tool_specs", None)
    if not callable(fn):
        return {}
    specs = fn(SimpleNamespace(plugin_config=_plugin_cfg()))
    out: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}
    for spec_item in specs:
        if not isinstance(spec_item, dict):
            continue
        name = str(spec_item.get("name") or "").strip()
        handler = spec_item.get("handler")
        if name and callable(handler):
            out[name] = handler
    return out


def _delegate(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    handlers = _wiki_handlers()
    h = handlers.get(tool_name)
    if not callable(h):
        return {"ok": False, "error": f"wiki handler unavailable: {tool_name}"}
    try:
        return h(dict(args or {}))
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def memory_curator_wiki_status_tool() -> ToolSpec:
    return ToolSpec(
        name="memory_curator_wiki_status",
        description="Read wiki runtime status for memory curation.",
        parameters={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        handler=lambda args: _delegate("wiki_status", args),
        tags=frozenset({"memory", "wiki", "curator"}),
        read_only=True,
    )


def memory_curator_wiki_get_tool() -> ToolSpec:
    return ToolSpec(
        name="memory_curator_wiki_get",
        description="Read a markdown file from wiki for curation.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "start_line": {"type": "integer"},
                "end_line": {"type": "integer"},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        handler=lambda args: _delegate("wiki_get", args),
        tags=frozenset({"memory", "wiki", "curator"}),
        read_only=True,
    )


def memory_curator_wiki_search_tool() -> ToolSpec:
    return ToolSpec(
        name="memory_curator_wiki_search",
        description="Search wiki markdown for memory curation.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
                "is_regex": {"type": "boolean"},
                "case_sensitive": {"type": "boolean"},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=lambda args: _delegate("wiki_search", args),
        tags=frozenset({"memory", "wiki", "curator"}),
        read_only=True,
    )


def memory_curator_wiki_lint_tool() -> ToolSpec:
    return ToolSpec(
        name="memory_curator_wiki_lint",
        description="Lint wiki markdown structure for curation quality.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": [],
            "additionalProperties": False,
        },
        handler=lambda args: _delegate("wiki_lint", args),
        tags=frozenset({"memory", "wiki", "curator"}),
        read_only=True,
    )


def memory_curator_wiki_apply_tool() -> ToolSpec:
    return ToolSpec(
        name="memory_curator_wiki_apply",
        description="Apply curated write/append/delete changes to wiki markdown.",
        parameters={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["write", "append", "delete"]},
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["action", "path"],
            "additionalProperties": False,
        },
        handler=lambda args: _delegate("wiki_apply", args),
        tags=frozenset({"memory", "wiki", "curator", "write"}),
        risk_level="high",
        read_only=False,
    )


__all__ = [
    "memory_curator_wiki_status_tool",
    "memory_curator_wiki_get_tool",
    "memory_curator_wiki_search_tool",
    "memory_curator_wiki_lint_tool",
    "memory_curator_wiki_apply_tool",
]
