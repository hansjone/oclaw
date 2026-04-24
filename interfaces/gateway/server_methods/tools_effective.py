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


def _is_admin(client: Any) -> bool:
    if not isinstance(client, dict):
        return False
    connect = client.get("connect")
    if not isinstance(connect, dict):
        return False
    scopes = connect.get("scopes")
    return isinstance(scopes, list) and "operator.admin" in [x for x in scopes if isinstance(x, str)]


def _tools_effective_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    client = opts.get("client")
    if not isinstance(params, dict):
        _bad(respond, "invalid tools.effective params")
        return
    session_key = _norm_str(params.get("sessionKey"))
    if not session_key:
        _bad(respond, "invalid tools.effective params: sessionKey required")
        return
    requested_agent_id = _norm_str(params.get("agentId"))
    if requested_agent_id:
        list_agents = context.get("list_agent_ids") if isinstance(context, dict) else None
        if callable(list_agents):
            try:
                known = list_agents()
            except Exception:
                known = None
            if isinstance(known, list) and requested_agent_id not in [x for x in known if isinstance(x, str)]:
                _bad(respond, f'unknown agent id "{requested_agent_id}"')
                return

    hook = context.get("resolve_effective_tool_inventory") if isinstance(context, dict) else None
    if callable(hook):
        try:
            out = hook(
                {
                    "sessionKey": session_key,
                    "agentId": requested_agent_id,
                    "senderIsOwner": _is_admin(client),
                }
            )
            _ok(respond, out if isinstance(out, dict) else {"tools": []})
            return
        except Exception as exc:
            _bad(respond, str(exc))
            return

    _ok(
        respond,
        {
            "sessionKey": session_key,
            "agentId": requested_agent_id or "main",
            "tools": [],
            "policy": {
                "senderIsOwner": _is_admin(client),
            },
        },
    )


tools_effective_handlers: GatewayRequestHandlers = {
    "tools.effective": _tools_effective_handler,
}

