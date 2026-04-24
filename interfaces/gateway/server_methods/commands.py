from __future__ import annotations

from typing import Any

from .shared_types import GatewayRequestHandlers
from .validation import error_shape


def _validate_commands_list_params(params: Any) -> bool:
    if not isinstance(params, dict):
        return False
    for k in ("agentId", "provider", "scope"):
        if k in params and params[k] is not None and not isinstance(params[k], str):
            return False
    if "includeArgs" in params and params["includeArgs"] is not None and not isinstance(params["includeArgs"], bool):
        return False
    return True


def build_commands_list_result(
    *,
    cfg: dict[str, Any],
    agent_id: str,
    provider: str | None = None,
    scope: str | None = None,
    include_args: bool | None = None,
) -> dict[str, Any]:
    _ = cfg, agent_id, provider, scope, include_args
    return {"commands": []}


def _commands_list_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    if not callable(respond):
        return
    if not _validate_commands_list_params(params):
        respond(False, None, error_shape("INVALID_REQUEST", "invalid commands.list params"), None)
        return
    p = params if isinstance(params, dict) else {}
    agent_id = str(p.get("agentId") or "main").strip() or "main"
    provider = str(p.get("provider") or "").strip() or None
    scope = str(p.get("scope") or "").strip() or None
    include_args = p.get("includeArgs")
    include_args = bool(include_args) if include_args is not None else None
    respond(
        True,
        build_commands_list_result(
            cfg={},
            agent_id=agent_id,
            provider=provider,
            scope=scope,
            include_args=include_args,
        ),
        None,
        None,
    )


commands_handlers: GatewayRequestHandlers = {
    "commands.list": _commands_list_handler,
}
