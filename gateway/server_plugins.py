from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .python_extensions_loader import build_python_extensions_registry

GatewayHandler = Callable[..., Any]
LogFn = Callable[[str], None]


@dataclass(frozen=True)
class GatewayPluginLoadResult:
    plugin_registry: dict[str, Any]
    gateway_methods: list[str]


def _apply_plugin_auto_enable(cfg: dict[str, Any]) -> dict[str, Any]:
    """Python rewrite placeholder for plugin auto-enable policy.

    Keep behavior deterministic: when no runtime policy engine is attached,
    the incoming config is treated as already normalized.
    """
    return dict(cfg or {})


def _resolve_gateway_startup_plugin_ids(
    *,
    config: dict[str, Any],
    workspace_dir: str,
) -> list[str]:
    ws_root = Path(workspace_dir).resolve()
    plugins = ((config.get("plugins") or {}).get("enabled") or []) if isinstance(config, dict) else []
    out = [str(x).strip() for x in plugins if str(x).strip()]
    slot_cfg = ((config.get("plugins") or {}).get("slots") or {}) if isinstance(config, dict) else {}
    memory_slot = str(slot_cfg.get("memory") or "").strip()
    memory_plugin_ids = {"memory-core", "memory-wiki", "memory-lancedb"}
    if out:
        if memory_slot:
            out = [x for x in out if x not in memory_plugin_ids]
            if memory_slot.lower() != "none":
                out.append(memory_slot)
        return out
    # Auto-discover local plugins when explicit list is absent.
    roots = [
        ws_root / "oclaw" / "extensions",
        ws_root / "extensions",
    ]
    seen: set[str] = set()
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        for child in root.iterdir():
            if not child.is_dir():
                continue
            pid = str(child.name or "").strip()
            if not pid or pid.startswith(".") or pid in seen:
                continue
            seen.add(pid)
            out.append(pid)
    if memory_slot:
        out = [x for x in out if x not in memory_plugin_ids]
        if memory_slot.lower() != "none":
            out.append(memory_slot)
    return out


def _load_openclaw_plugins(
    *,
    config: dict[str, Any],
    workspace_dir: str,
    only_plugin_ids: list[str],
    core_gateway_handlers: dict[str, GatewayHandler] | None = None,
) -> dict[str, Any]:
    """Minimal Python replacement for loadOpenClawPlugins.

    This function intentionally returns a stable registry shape that matches
    the gateway startup contract used by this project.
    """
    core_gateway_handlers = dict(core_gateway_handlers or {})
    registry = build_python_extensions_registry(
        app_config=dict(config or {}),
        workspace_dir=workspace_dir,
        only_plugin_ids=list(only_plugin_ids or []),
    )
    registry["gateway_handlers"] = {k: v for k, v in core_gateway_handlers.items()}
    registry["workspace_dir"] = workspace_dir
    return registry


def load_gateway_plugins(
    *,
    cfg: dict[str, Any],
    workspace_dir: str,
    log: dict[str, LogFn],
    core_gateway_handlers: dict[str, GatewayHandler],
    base_methods: list[str],
    plugin_ids: list[str] | None = None,
) -> GatewayPluginLoadResult:
    """Python rewrite of `gateway/server-plugins.ts::loadGatewayPlugins`.

    Behavior:
    - Resolve startup plugin ids
    - Load plugin registry
    - Merge plugin gateway handlers into gateway methods
    """
    resolved_cfg = _apply_plugin_auto_enable(cfg)
    chosen_plugin_ids = list(
        plugin_ids or _resolve_gateway_startup_plugin_ids(config=resolved_cfg, workspace_dir=workspace_dir)
    )
    if not chosen_plugin_ids:
        plugin_registry = {"plugins": [], "gateway_handlers": {}, "http_routes": [], "diagnostics": []}
        return GatewayPluginLoadResult(plugin_registry=plugin_registry, gateway_methods=list(base_methods))

    plugin_registry = _load_openclaw_plugins(
        config=resolved_cfg,
        workspace_dir=workspace_dir,
        only_plugin_ids=chosen_plugin_ids,
        core_gateway_handlers=core_gateway_handlers,
    )
    plugin_methods = list((plugin_registry.get("gateway_handlers") or {}).keys())
    merged_methods: list[str] = []
    seen: set[str] = set()
    for method in [*base_methods, *plugin_methods]:
        if method not in seen:
            seen.add(method)
            merged_methods.append(method)

    info = log.get("info")
    if callable(info):
        info(f"[gateway] loaded {len(chosen_plugin_ids)} plugins for workspace={workspace_dir}")

    return GatewayPluginLoadResult(plugin_registry=plugin_registry, gateway_methods=merged_methods)

