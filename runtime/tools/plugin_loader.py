from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from runtime.tools.base import ToolSpec

logger = logging.getLogger(__name__)

ToolFactory = Callable[[], ToolSpec]


@dataclass(frozen=True)
class PluginTool:
    tool: ToolSpec
    plugin_name: str
    plugin_version: str
    entry_point: str


def _iter_entry_points() -> list[Any]:
    try:
        from importlib.metadata import entry_points  # py3.10+
    except Exception:
        return []
    try:
        eps = entry_points()
        # py3.10+ returns EntryPoints with .select
        groups = []
        for g in ("ai_ops_assistant.tools", "chatgpt.tools"):
            try:
                groups.extend(list(eps.select(group=g)))
            except Exception:
                pass
        return groups
    except Exception:
        return []


def discover_plugin_tool_factories() -> list[tuple[str, str, str, ToolFactory]]:
    """Return (plugin_name, plugin_version, ep_name, factory)."""
    out: list[tuple[str, str, str, ToolFactory]] = []
    for ep in _iter_entry_points():
        ep_name = f"{getattr(ep, 'group', '')}:{getattr(ep, 'name', '')}"
        try:
            obj = ep.load()
        except Exception as exc:
            logger.warning("skip plugin entry point %s: %s", ep_name, exc)
            continue
        factory: ToolFactory | None = None
        if callable(obj):
            factory = obj  # type: ignore[assignment]
        if not factory:
            logger.warning("skip plugin entry point %s: not callable", ep_name)
            continue
        dist_name = ""
        dist_ver = ""
        try:
            dist = getattr(ep, "dist", None)
            if dist is not None:
                dist_name = str(getattr(dist, "name", "") or "")
                dist_ver = str(getattr(dist, "version", "") or "")
        except Exception:
            dist_name = ""
            dist_ver = ""
        out.append((dist_name or "unknown", dist_ver or "", ep_name, factory))
    return out


def materialize_plugin_tools() -> list[PluginTool]:
    tools: list[PluginTool] = []
    for plugin_name, plugin_version, ep_name, factory in discover_plugin_tool_factories():
        try:
            spec = factory()
        except Exception as exc:
            logger.warning("skip plugin tool %s (%s): %s", ep_name, plugin_name, exc)
            continue
        if not isinstance(spec, ToolSpec):
            logger.warning("skip plugin tool %s (%s): factory did not return ToolSpec", ep_name, plugin_name)
            continue
        # Tag plugin tools and default them to higher risk unless explicitly configured otherwise.
        try:
            spec = ToolSpec(
                name=spec.name,
                description=spec.description,
                parameters=spec.parameters,
                handler=spec.handler,
                tags=frozenset(set(spec.tags) | {"plugin"}),
                version=getattr(spec, "version", "v1"),
                risk_level=getattr(spec, "risk_level", "high") or "high",
                timeout_s=getattr(spec, "timeout_s", None),
                rate_limit=getattr(spec, "rate_limit", None),
                required_permissions=getattr(spec, "required_permissions", frozenset()),
                execution_mode=getattr(spec, "execution_mode", "in_process"),
                read_only=bool(spec.is_read_only()),
            )
        except Exception:
            # If wrapping fails, keep original spec.
            pass
        tools.append(
            PluginTool(
                tool=spec,
                plugin_name=plugin_name,
                plugin_version=plugin_version,
                entry_point=ep_name,
            )
        )
    return tools


def sync_plugin_metadata(store: Any) -> int:
    """Persist discovered plugin metadata into store (best-effort)."""
    count = 0
    try:
        rows = discover_plugin_tool_factories()
    except Exception:
        rows = []
    for plugin_name, plugin_version, ep_name, _factory in rows:
        try:
            store.upsert_tool_plugin(
                plugin_name=plugin_name,
                plugin_version=plugin_version,
                entry_point=ep_name,
                enabled=True,
            )
            count += 1
        except Exception:
            continue
    return count


__all__ = ["PluginTool", "discover_plugin_tool_factories", "materialize_plugin_tools", "sync_plugin_metadata"]

