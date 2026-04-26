from __future__ import annotations

from typing import Any

from .shared_types import GatewayRequestHandlers
from .validation import error_shape

DEFAULT_AGENT_ID = "main"
ALLOWED_FILE_NAMES = {
    "SOUL.md",
    "TOOLS.md",
    "ROLE_SYSTEM.md",
    "HEARTBEAT.md",
    "BOOTSTRAP.md",
    "memory/README.md",
    "memory.md",
}


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
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        s = str(v).strip()
        return s or None
    return None


def _normalize_agent_id(raw: str) -> str:
    return raw.strip().lower().replace(" ", "-")


def _list_agent_ids(context: Any) -> list[str]:
    hook = context.get("list_agent_ids") if isinstance(context, dict) else None
    if callable(hook):
        out = hook()
        if isinstance(out, list):
            vals = [str(x) for x in out if isinstance(x, str) and x.strip()]
            if vals:
                return vals
    return [DEFAULT_AGENT_ID]


def _resolve_agent_or_error(raw: Any, context: Any, respond) -> str | None:
    requested = _norm_str(raw)
    agent_id = _normalize_agent_id(requested) if requested else DEFAULT_AGENT_ID
    allowed = set(_list_agent_ids(context))
    if agent_id not in allowed:
        _bad(respond, f'agent "{agent_id}" not found')
        return None
    return agent_id


def _agents_list_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid agents.list params")
        return
    hook = context.get("list_agents_for_gateway") if isinstance(context, dict) else None
    if callable(hook):
        out = hook()
        _ok(respond, out if isinstance(out, dict) else {"agents": []})
        return
    ids = _list_agent_ids(context)
    _ok(respond, {"agents": [{"id": aid, "name": aid} for aid in ids]})


def _agents_create_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid agents.create params")
        return
    name = _norm_str(params.get("name"))
    workspace = _norm_str(params.get("workspace"))
    if not name or not workspace:
        _bad(respond, "invalid agents.create params")
        return
    agent_id = _normalize_agent_id(name)
    if agent_id == DEFAULT_AGENT_ID:
        _bad(respond, f'"{DEFAULT_AGENT_ID}" is reserved')
        return
    if agent_id in set(_list_agent_ids(context)):
        _bad(respond, f'agent "{agent_id}" already exists')
        return
    hook = context.get("create_agent") if isinstance(context, dict) else None
    if callable(hook):
        out = hook(dict(params))
        _ok(respond, out if isinstance(out, dict) else {"ok": True, "agentId": agent_id})
        return
    _ok(respond, {"ok": True, "agentId": agent_id, "name": name, "workspace": workspace, "model": _norm_str(params.get("model"))})


def _agents_update_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid agents.update params")
        return
    agent_id = _resolve_agent_or_error(params.get("agentId"), context, respond)
    if not agent_id:
        return
    hook = context.get("update_agent") if isinstance(context, dict) else None
    if callable(hook):
        out = hook(dict(params))
        _ok(respond, out if isinstance(out, dict) else {"ok": True, "agentId": agent_id})
        return
    _ok(respond, {"ok": True, "agentId": agent_id})


def _agents_delete_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid agents.delete params")
        return
    agent_id = _norm_str(params.get("agentId"))
    if not agent_id:
        _bad(respond, "invalid agents.delete params")
        return
    agent_id = _normalize_agent_id(agent_id)
    if agent_id == DEFAULT_AGENT_ID:
        _bad(respond, f'"{DEFAULT_AGENT_ID}" cannot be deleted')
        return
    if agent_id not in set(_list_agent_ids(context)):
        _bad(respond, f'agent "{agent_id}" not found')
        return
    hook = context.get("delete_agent") if isinstance(context, dict) else None
    if callable(hook):
        out = hook(dict(params))
        _ok(respond, out if isinstance(out, dict) else {"ok": True, "agentId": agent_id, "removedBindings": []})
        return
    _ok(respond, {"ok": True, "agentId": agent_id, "removedBindings": []})


def _agents_files_list_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid agents.files.list params")
        return
    agent_id = _resolve_agent_or_error(params.get("agentId"), context, respond)
    if not agent_id:
        return
    hook = context.get("agents_files_list") if isinstance(context, dict) else None
    if callable(hook):
        out = hook({"agentId": agent_id})
        _ok(respond, out if isinstance(out, dict) else {"agentId": agent_id, "workspace": ".", "files": []})
        return
    files = [{"name": n, "path": f"./{n}", "missing": True} for n in sorted(ALLOWED_FILE_NAMES)]
    _ok(respond, {"agentId": agent_id, "workspace": ".", "files": files})


def _agents_files_get_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid agents.files.get params")
        return
    agent_id = _resolve_agent_or_error(params.get("agentId"), context, respond)
    if not agent_id:
        return
    name = _norm_str(params.get("name")) or ""
    if name not in ALLOWED_FILE_NAMES:
        _bad(respond, f'unsupported file "{name}"')
        return
    hook = context.get("agents_files_get") if isinstance(context, dict) else None
    if callable(hook):
        out = hook({"agentId": agent_id, "name": name})
        _ok(
            respond,
            out
            if isinstance(out, dict)
            else {"agentId": agent_id, "workspace": ".", "file": {"name": name, "path": f"./{name}", "missing": True}},
        )
        return
    _ok(respond, {"agentId": agent_id, "workspace": ".", "file": {"name": name, "path": f"./{name}", "missing": True}})


def _agents_files_set_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid agents.files.set params")
        return
    agent_id = _resolve_agent_or_error(params.get("agentId"), context, respond)
    if not agent_id:
        return
    name = _norm_str(params.get("name")) or ""
    content = params.get("content")
    if name not in ALLOWED_FILE_NAMES or not isinstance(content, str):
        _bad(respond, "invalid agents.files.set params")
        return
    hook = context.get("agents_files_set") if isinstance(context, dict) else None
    if callable(hook):
        out = hook({"agentId": agent_id, "name": name, "content": content})
        _ok(
            respond,
            out
            if isinstance(out, dict)
            else {
                "ok": True,
                "agentId": agent_id,
                "workspace": ".",
                "file": {"name": name, "path": f"./{name}", "missing": False, "content": content},
            },
        )
        return
    _ok(
        respond,
        {
            "ok": True,
            "agentId": agent_id,
            "workspace": ".",
            "file": {"name": name, "path": f"./{name}", "missing": False, "content": content},
        },
    )


agents_handlers: GatewayRequestHandlers = {
    "agents.list": _agents_list_handler,
    "agents.create": _agents_create_handler,
    "agents.update": _agents_update_handler,
    "agents.delete": _agents_delete_handler,
    "agents.files.list": _agents_files_list_handler,
    "agents.files.get": _agents_files_get_handler,
    "agents.files.set": _agents_files_set_handler,
}

