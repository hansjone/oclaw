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


def _unavailable(respond, message: str) -> None:
    if callable(respond):
        respond(False, None, error_shape("UNAVAILABLE", message), None)


def _norm_str(v: Any) -> str | None:
    if isinstance(v, str):
        s = v.strip()
        return s or None
    return None


def _state(context: Any) -> dict[str, Any]:
    if not isinstance(context, dict):
        return {"path": ".openclaw/exec-approvals.json", "exists": False, "hash": None, "file": {}}
    st = context.get("_exec_approvals_state")
    if isinstance(st, dict):
        return st
    created = {"path": ".openclaw/exec-approvals.json", "exists": False, "hash": None, "file": {}}
    context["_exec_approvals_state"] = created
    return created


def _payload(st: dict[str, Any]) -> dict[str, Any]:
    file_obj = st.get("file")
    file_obj = dict(file_obj) if isinstance(file_obj, dict) else {}
    socket = file_obj.get("socket")
    if isinstance(socket, dict):
        path = _norm_str(socket.get("path"))
        file_obj["socket"] = {"path": path} if path else None
    return {
        "path": st.get("path"),
        "exists": bool(st.get("exists", False)),
        "hash": st.get("hash"),
        "file": file_obj,
    }


def _require_base_hash(params: dict[str, Any], st: dict[str, Any], respond) -> bool:
    if not bool(st.get("exists")):
        return True
    snap_hash = _norm_str(st.get("hash"))
    if not snap_hash:
        _bad(respond, "exec approvals base hash unavailable; re-run exec.approvals.get and retry")
        return False
    base_hash = _norm_str(params.get("baseHash"))
    if not base_hash:
        _bad(respond, "exec approvals base hash required; re-run exec.approvals.get and retry")
        return False
    if base_hash != snap_hash:
        _bad(respond, "exec approvals changed since last load; re-run exec.approvals.get and retry")
        return False
    return True


def _resolve_node_id_or_error(raw: Any, respond) -> str | None:
    node_id = _norm_str(raw)
    if not node_id:
        _bad(respond, "nodeId required")
        return None
    return node_id


def _exec_approvals_get_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    context = opts.get("context")
    hook = context.get("read_exec_approvals_snapshot") if isinstance(context, dict) else None
    if callable(hook):
        try:
            snap = hook()
            if isinstance(snap, dict):
                _ok(respond, _payload(snap))
                return
        except Exception as exc:
            _unavailable(respond, str(exc))
            return
    st = _state(context)
    _ok(respond, _payload(st))


def _exec_approvals_set_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid exec.approvals.set params")
        return
    st = _state(context)
    if not _require_base_hash(params, st, respond):
        return
    incoming = params.get("file")
    if not isinstance(incoming, dict):
        _bad(respond, "exec approvals file is required")
        return
    hook = context.get("write_exec_approvals") if isinstance(context, dict) else None
    if callable(hook):
        try:
            next_snap = hook({"file": incoming, "baseHash": params.get("baseHash")})
            if isinstance(next_snap, dict):
                _ok(respond, _payload(next_snap))
                return
        except Exception as exc:
            _unavailable(respond, str(exc))
            return
    st["file"] = dict(incoming)
    st["exists"] = True
    st["hash"] = f"h{abs(hash(str(incoming))) % 1000000}"
    _ok(respond, _payload(st))


def _exec_approvals_node_get_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid exec.approvals.node.get params")
        return
    node_id = _resolve_node_id_or_error(params.get("nodeId"), respond)
    if not node_id:
        return
    hook = context.get("node_exec_approvals_get") if isinstance(context, dict) else None
    if callable(hook):
        try:
            payload = hook({"nodeId": node_id})
            _ok(respond, payload if payload is not None else {})
            return
        except Exception as exc:
            _unavailable(respond, str(exc))
            return
    _ok(respond, {"nodeId": node_id, "path": None, "exists": False, "hash": None, "file": {}})


def _exec_approvals_node_set_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid exec.approvals.node.set params")
        return
    node_id = _resolve_node_id_or_error(params.get("nodeId"), respond)
    if not node_id:
        return
    file_obj = params.get("file")
    if not isinstance(file_obj, dict):
        _bad(respond, "exec approvals file is required")
        return
    hook = context.get("node_exec_approvals_set") if isinstance(context, dict) else None
    if callable(hook):
        try:
            payload = hook({"nodeId": node_id, "file": file_obj, "baseHash": params.get("baseHash")})
            _ok(respond, payload if payload is not None else {})
            return
        except Exception as exc:
            _unavailable(respond, str(exc))
            return
    _ok(
        respond,
        {
            "nodeId": node_id,
            "path": None,
            "exists": True,
            "hash": f"h{abs(hash(str(file_obj))) % 1000000}",
            "file": dict(file_obj),
        },
    )


exec_approvals_handlers: GatewayRequestHandlers = {
    "exec.approvals.get": _exec_approvals_get_handler,
    "exec.approvals.set": _exec_approvals_set_handler,
    "exec.approvals.node.get": _exec_approvals_node_get_handler,
    "exec.approvals.node.set": _exec_approvals_node_set_handler,
}

