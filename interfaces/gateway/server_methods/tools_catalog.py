from __future__ import annotations

from typing import Any

from .shared_types import GatewayRequestHandlers
from .validation import error_shape


def _ok(respond, payload: Any) -> None:
    if callable(respond):
        respond(True, payload, None, None)


def _bad(respond, message: str) -> None:
    if callable(respond):
        respond(False, None, error_shape("INVALID_REQUEST", message), None)


def _norm_str(v: Any) -> str | None:
    if isinstance(v, str):
        s = v.strip()
        return s or None
    return None


def _tools_catalog_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid tools.catalog params")
        return

    include_plugins = params.get("includePlugins")
    include_plugins = bool(include_plugins) if include_plugins is not None else True

    agent_id = _norm_str(params.get("agentId")) or "main"
    # Optional agent validation hook.
    known_agents = None
    list_agents = context.get("list_agent_ids") if isinstance(context, dict) else None
    if callable(list_agents):
        try:
            known_agents = list_agents()
        except Exception:
            known_agents = None
    if isinstance(known_agents, list) and agent_id and agent_id not in [x for x in known_agents if isinstance(x, str)]:
        _bad(respond, f'unknown agent id "{agent_id}"')
        return

    hook = context.get("build_tools_catalog") if isinstance(context, dict) else None
    if callable(hook):
        try:
            out = hook({"agentId": agent_id, "includePlugins": include_plugins})
            _ok(respond, out if isinstance(out, dict) else {"agentId": agent_id, "profiles": [], "groups": []})
            return
        except Exception as exc:
            _bad(respond, str(exc))
            return

    _ok(
        respond,
        {
            "agentId": agent_id,
            "profiles": [
                {"id": "minimal", "label": "Minimal"},
                {"id": "coding", "label": "Coding"},
                {"id": "messaging", "label": "Messaging"},
                {"id": "full", "label": "Full"},
            ],
            "groups": [
                {
                    "id": "core:default",
                    "label": "Core",
                    "source": "core",
                    "tools": [
                        {
                            "id": "tool.echo",
                            "label": "Echo",
                            "description": "Staging tool entry",
                            "source": "core",
                            "defaultProfiles": ["minimal", "full"],
                        }
                    ],
                }
            ]
            if not include_plugins
            else [
                {
                    "id": "core:default",
                    "label": "Core",
                    "source": "core",
                    "tools": [
                        {
                            "id": "tool.echo",
                            "label": "Echo",
                            "description": "Staging tool entry",
                            "source": "core",
                            "defaultProfiles": ["minimal", "full"],
                        }
                    ],
                },
                {
                    "id": "plugin:example",
                    "label": "example",
                    "source": "plugin",
                    "pluginId": "example",
                    "tools": [],
                },
            ],
        },
    )


tools_catalog_handlers: GatewayRequestHandlers = {
    "tools.catalog": _tools_catalog_handler,
}

