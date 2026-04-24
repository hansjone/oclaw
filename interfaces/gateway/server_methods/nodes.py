from __future__ import annotations

import time
from typing import Any

from .shared_types import GatewayRequestHandlers
from .validation import error_shape

NODE_WAKE_RECONNECT_WAIT_MS = 3_000
NODE_WAKE_RECONNECT_RETRY_WAIT_MS = 12_000


def _ok(respond, payload: Any) -> None:
    if callable(respond):
        respond(True, payload, None, None)


def _bad(respond, message: str, *, code: str = "INVALID_REQUEST", details: dict[str, Any] | None = None) -> None:
    if callable(respond):
        respond(False, None, error_shape(code, message, {"details": details} if details else None), None)


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
        return {"pair_requests": {}, "paired": {}, "pending_actions": {}}
    st = context.get("_nodes_state")
    if isinstance(st, dict):
        return st
    created = {"pair_requests": {}, "paired": {}, "pending_actions": {}}
    context["_nodes_state"] = created
    return created


def _resolve_client_node_id(client: Any) -> str | None:
    if not isinstance(client, dict):
        return None
    connect = client.get("connect")
    if not isinstance(connect, dict):
        return None
    device = connect.get("device")
    client_info = connect.get("client")
    if isinstance(device, dict):
        got = _norm_str(device.get("id"))
        if got:
            return got
    if isinstance(client_info, dict):
        return _norm_str(client_info.get("id"))
    return None


def _node_pair_request_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid node.pair.request params")
        return
    node_id = _norm_str(params.get("nodeId"))
    if not node_id:
        _bad(respond, "invalid node.pair.request params")
        return
    st = _state(context)
    req_id = f"npr_{int(time.time()*1000)}"
    request = {
        "requestId": req_id,
        "nodeId": node_id,
        "displayName": _norm_str(params.get("displayName")) or node_id,
        "platform": _norm_str(params.get("platform")),
        "ts": int(time.time() * 1000),
    }
    st["pair_requests"][req_id] = request
    _ok(respond, {"status": "pending", "created": True, "request": request})


def _node_pair_list_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    context = opts.get("context")
    st = _state(context)
    _ok(respond, {"pending": list(st["pair_requests"].values()), "paired": list(st["paired"].values())})


def _node_pair_approve_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid node.pair.approve params")
        return
    req_id = _norm_str(params.get("requestId"))
    if not req_id:
        _bad(respond, "invalid node.pair.approve params")
        return
    st = _state(context)
    req = st["pair_requests"].pop(req_id, None)
    if not isinstance(req, dict):
        _bad(respond, "unknown requestId")
        return
    node = {"nodeId": req["nodeId"], "displayName": req.get("displayName") or req["nodeId"], "platform": req.get("platform")}
    st["paired"][node["nodeId"]] = node
    _ok(respond, {"requestId": req_id, "node": node})


def _node_pair_reject_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid node.pair.reject params")
        return
    req_id = _norm_str(params.get("requestId"))
    if not req_id:
        _bad(respond, "invalid node.pair.reject params")
        return
    st = _state(context)
    req = st["pair_requests"].pop(req_id, None)
    if not isinstance(req, dict):
        _bad(respond, "unknown requestId")
        return
    _ok(respond, {"requestId": req_id, "nodeId": req.get("nodeId"), "decision": "rejected"})


def _node_pair_verify_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid node.pair.verify params")
        return
    node_id = _norm_str(params.get("nodeId"))
    token = _norm_str(params.get("token"))
    if not node_id or not token:
        _bad(respond, "invalid node.pair.verify params")
        return
    st = _state(context)
    ok = node_id in st["paired"]
    _ok(respond, {"ok": ok, "nodeId": node_id})


def _node_rename_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid node.rename params")
        return
    node_id = _norm_str(params.get("nodeId"))
    display_name = _norm_str(params.get("displayName"))
    if not node_id or not display_name:
        _bad(respond, "displayName required")
        return
    st = _state(context)
    node = st["paired"].get(node_id)
    if not isinstance(node, dict):
        _bad(respond, "unknown nodeId")
        return
    node["displayName"] = display_name
    _ok(respond, {"nodeId": node_id, "displayName": display_name})


def _node_list_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    context = opts.get("context")
    st = _state(context)
    nodes = list(st["paired"].values())
    _ok(respond, {"ts": int(time.time() * 1000), "nodes": nodes})


def _node_describe_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid node.describe params")
        return
    node_id = _norm_str(params.get("nodeId"))
    if not node_id:
        _bad(respond, "nodeId required")
        return
    st = _state(context)
    node = st["paired"].get(node_id)
    if not isinstance(node, dict):
        _bad(respond, "unknown nodeId")
        return
    _ok(respond, {"ts": int(time.time() * 1000), **node})


def _node_canvas_capability_refresh_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    client = opts.get("client")
    if not isinstance(client, dict):
        _unavailable(respond, "canvas host unavailable for this node session")
        return
    base = _norm_str(client.get("canvas_host_url"))
    if not base:
        _unavailable(respond, "canvas host unavailable for this node session")
        return
    cap = f"cap_{int(time.time()*1000)}"
    exp = int(time.time() * 1000) + 5 * 60_000
    client["canvas_capability"] = cap
    client["canvas_capability_expires_at_ms"] = exp
    _ok(respond, {"canvasCapability": cap, "canvasCapabilityExpiresAtMs": exp, "canvasHostUrl": f"{base.rstrip('/')}/scoped/{cap}"})


def _node_pending_pull_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    client = opts.get("client")
    context = opts.get("context")
    node_id = _resolve_client_node_id(client)
    if not node_id:
        _bad(respond, "nodeId required")
        return
    st = _state(context)
    actions = st["pending_actions"].get(node_id, [])
    _ok(
        respond,
        {
            "nodeId": node_id,
            "actions": [
                {"id": x.get("id"), "command": x.get("command"), "paramsJSON": x.get("paramsJSON"), "enqueuedAtMs": x.get("enqueuedAtMs")}
                for x in actions
            ],
        },
    )


def _node_pending_ack_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    client = opts.get("client")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid node.pending.ack params")
        return
    node_id = _resolve_client_node_id(client)
    if not node_id:
        _bad(respond, "nodeId required")
        return
    ids_raw = params.get("ids")
    ids = []
    if isinstance(ids_raw, list):
        ids = [x for x in {_norm_str(i) for i in ids_raw} if x]
    st = _state(context)
    current = st["pending_actions"].get(node_id, [])
    remaining = [x for x in current if x.get("id") not in set(ids)]
    st["pending_actions"][node_id] = remaining
    _ok(respond, {"nodeId": node_id, "ackedIds": ids, "remainingCount": len(remaining)})


def _node_invoke_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid node.invoke params")
        return
    node_id = _norm_str(params.get("nodeId"))
    command = _norm_str(params.get("command"))
    if not node_id or not command:
        _bad(respond, "nodeId and command required")
        return
    if command in {"system.execApprovals.get", "system.execApprovals.set"}:
        _bad(respond, "node.invoke does not allow system.execApprovals.*; use exec.approvals.node.*", details={"command": command})
        return
    # optional hook
    hook = context.get("node_invoke") if isinstance(context, dict) else None
    if callable(hook):
        try:
            res = hook({"nodeId": node_id, "command": command, "params": params.get("params"), "timeoutMs": params.get("timeoutMs"), "idempotencyKey": params.get("idempotencyKey")})
            if isinstance(res, dict):
                if not bool(res.get("ok", True)):
                    _unavailable(respond, str((res.get("error") or {}).get("message") or "node not connected"))
                    return
                payload = res.get("payload")
                _ok(respond, {"ok": True, "nodeId": node_id, "command": command, "payload": payload, "payloadJSON": res.get("payloadJSON")})
                return
        except Exception as exc:
            _unavailable(respond, str(exc))
            return
    _ok(respond, {"ok": True, "nodeId": node_id, "command": command, "payload": {"ok": True}, "payloadJSON": None})


def _node_invoke_result_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    # staging ack
    _ok(respond, {"ok": True})


def _node_event_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    client = opts.get("client")
    if not isinstance(params, dict):
        _bad(respond, "invalid node.event params")
        return
    event = _norm_str(params.get("event"))
    if not event:
        _bad(respond, "invalid node.event params")
        return
    node_id = _resolve_client_node_id(client) or "node"
    # optional hook
    hook = context.get("handle_node_event") if isinstance(context, dict) else None
    if callable(hook):
        try:
            hook({"nodeId": node_id, "event": event, "payload": params.get("payload"), "payloadJSON": params.get("payloadJSON")})
        except Exception as exc:
            _unavailable(respond, str(exc))
            return
    _ok(respond, {"ok": True})


node_handlers: GatewayRequestHandlers = {
    "node.pair.request": _node_pair_request_handler,
    "node.pair.list": _node_pair_list_handler,
    "node.pair.approve": _node_pair_approve_handler,
    "node.pair.reject": _node_pair_reject_handler,
    "node.pair.verify": _node_pair_verify_handler,
    "node.rename": _node_rename_handler,
    "node.list": _node_list_handler,
    "node.describe": _node_describe_handler,
    "node.canvas.capability.refresh": _node_canvas_capability_refresh_handler,
    "node.pending.pull": _node_pending_pull_handler,
    "node.pending.ack": _node_pending_ack_handler,
    "node.invoke": _node_invoke_handler,
    "node.invoke.result": _node_invoke_result_handler,
    "node.event": _node_event_handler,
}

