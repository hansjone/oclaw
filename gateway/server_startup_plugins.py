from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from oclaw.agents.agent_scope import resolve_agent_workspace_dir, resolve_default_agent_id
from oclaw.agents.subagent_registry import init_subagent_registry

from .server_plugins import GatewayPluginLoadResult, load_gateway_plugins

LogFn = Callable[[str], None]


@dataclass(frozen=True)
class GatewayPluginBootstrapResult:
    gateway_plugin_config_at_start: dict[str, Any]
    default_workspace_dir: str
    deferred_configured_channel_plugin_ids: list[str]
    startup_plugin_ids: list[str]
    base_methods: list[str]
    plugin_registry: dict[str, Any]
    base_gateway_methods: list[str]


def _resolve_default_workspace_dir(cfg: dict[str, Any]) -> str:
    default_agent_id = resolve_default_agent_id(cfg)
    workspace_dir = resolve_agent_workspace_dir(cfg, default_agent_id)
    return str(workspace_dir or ".").strip() or "."


def _resolve_deferred_configured_channel_plugin_ids(cfg: dict[str, Any]) -> list[str]:
    channels = (cfg.get("channels") or {}) if isinstance(cfg, dict) else {}
    deferred = channels.get("deferred_plugins")
    if not isinstance(deferred, list):
        return []
    return [str(x).strip() for x in deferred if str(x).strip()]


def _resolve_gateway_startup_plugin_ids(cfg: dict[str, Any]) -> list[str]:
    plugins = (cfg.get("plugins") or {}) if isinstance(cfg, dict) else {}
    enabled = plugins.get("enabled")
    if not isinstance(enabled, list):
        return []
    return [str(x).strip() for x in enabled if str(x).strip()]


def prepare_gateway_plugin_bootstrap(
    *,
    cfg_at_start: dict[str, Any],
    startup_runtime_config: dict[str, Any],
    minimal_test_gateway: bool,
    log: dict[str, LogFn],
    core_gateway_handlers: dict[str, Callable[..., Any]],
    base_methods: list[str],
) -> GatewayPluginBootstrapResult:
    _ = startup_runtime_config
    init_subagent_registry()
    gateway_plugin_config_at_start = dict(cfg_at_start or {})
    default_workspace_dir = _resolve_default_workspace_dir(gateway_plugin_config_at_start)
    deferred_configured_channel_plugin_ids = (
        [] if minimal_test_gateway else _resolve_deferred_configured_channel_plugin_ids(gateway_plugin_config_at_start)
    )
    startup_plugin_ids = [] if minimal_test_gateway else _resolve_gateway_startup_plugin_ids(gateway_plugin_config_at_start)

    if minimal_test_gateway:
        plugin_registry = {"plugins": [], "gateway_handlers": {}, "http_routes": [], "diagnostics": []}
        base_gateway_methods = list(base_methods)
    else:
        loaded: GatewayPluginLoadResult = load_gateway_plugins(
            cfg=gateway_plugin_config_at_start,
            workspace_dir=default_workspace_dir,
            log=log,
            core_gateway_handlers=core_gateway_handlers,
            base_methods=base_methods,
            plugin_ids=startup_plugin_ids,
        )
        plugin_registry = loaded.plugin_registry
        base_gateway_methods = loaded.gateway_methods

    return GatewayPluginBootstrapResult(
        gateway_plugin_config_at_start=gateway_plugin_config_at_start,
        default_workspace_dir=default_workspace_dir,
        deferred_configured_channel_plugin_ids=deferred_configured_channel_plugin_ids,
        startup_plugin_ids=startup_plugin_ids,
        base_methods=list(base_methods),
        plugin_registry=plugin_registry,
        base_gateway_methods=base_gateway_methods,
    )
