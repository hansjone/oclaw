from __future__ import annotations

import time
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


def _resolve_client_node_id(client: Any) -> str | None:
    if not isinstance(client, dict):
        return None
    connect = client.get("connect")
    if not isinstance(connect, dict):
        return None
    device = connect.get("device")
    client_info = connect.get("client")
    node_id = None
    if isinstance(device, dict):
        node_id = _norm_str(device.get("id"))
    if node_id:
        return node_id
    if isinstance(client_info, dict):
        return _norm_str(client_info.get("id"))
    return None


def _state(context: Any) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(context, dict):
        return {}
    st = context.get("_node_pending_work")
    if isinstance(st, dict):
        return st
    created: dict[str, list[dict[str, Any]]] = {}
    context["_node_pending_work"] = created
    return created


def _enqueue_work(context: Any, item: dict[str, Any]) -> dict[str, Any]:
    hook = context.get("enqueue_node_pending_work") if isinstance(context, dict) else None
    if callable(hook):
        out = hook(item)
        if isinstance(out, dict):
            return out
    st = _state(context)
    bucket = st.setdefault(item["nodeId"], [])
    deduped = any(x.get("type") == item["type"] for x in bucket)
    entry = {
        "id": f"npw_{int(time.time()*1000)}_{len(bucket)+1}",
        "nodeId": item["nodeId"],
        "type": item["type"],
        "priority": item.get("priority") or "normal",
        "createdAtMs": int(time.time() * 1000),
        "status": "queued",
    }
    if not deduped:
        bucket.append(entry)
    return {"deduped": deduped, "item": entry}


def _drain_work(context: Any, node_id: str, max_items: int | None) -> dict[str, Any]:
    hook = context.get("drain_node_pending_work") if isinstance(context, dict) else None
    if callable(hook):
        out = hook({"nodeId": node_id, "maxItems": max_items, "includeDefaultStatus": True})
        if isinstance(out, dict):
            return out
    st = _state(context)
    bucket = st.get(node_id, [])
    n = len(bucket) if max_items is None else max(0, int(max_items))
    drained = bucket[:n]
    st[node_id] = bucket[n:]
    return {"items": drained, "count": len(drained), "remaining": len(st[node_id]), "defaultStatusIncluded": True}


def _node_pending_drain_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    client = opts.get("client")
    context = opts.get("context")
    if params is not None and not isinstance(params, dict):
        _bad(respond, "invalid node.pending.drain params")
        return
    node_id = _resolve_client_node_id(client)
    if not node_id:
        _bad(respond, "node.pending.drain requires a connected device identity")
        return
    max_items = params.get("maxItems") if isinstance(params, dict) else None
    if max_items is not None and not isinstance(max_items, (int, float)):
        _bad(respond, "invalid node.pending.drain params")
        return
    drained = _drain_work(context, node_id, int(max_items) if isinstance(max_items, (int, float)) else None)
    _ok(respond, {"nodeId": node_id, **drained})


def _node_pending_enqueue_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid node.pending.enqueue params")
        return
    node_id = _norm_str(params.get("nodeId"))
    work_type = _norm_str(params.get("type"))
    if not node_id or not work_type:
        _bad(respond, "invalid node.pending.enqueue params")
        return
    item = {
        "nodeId": node_id,
        "type": work_type,
        "priority": _norm_str(params.get("priority")) or "normal",
        "expiresInMs": params.get("expiresInMs"),
    }
    try:
        queued = _enqueue_work(context, item)
    except Exception as exc:
        _unavailable(respond, str(exc))
        return

    wake_triggered = False
    if params.get("wake", True) is not False:
        wake_hook = context.get("wake_node_pending") if isinstance(context, dict) else None
        if callable(wake_hook):
            try:
                wake_triggered = bool(wake_hook({"nodeId": node_id, "reason": "node.pending", "requestId": queued.get("item", {}).get("id")}))
            except Exception:
                wake_triggered = False
        else:
            wake_triggered = True
    _ok(respond, {"queued": queued, "wakeTriggered": wake_triggered})


node_pending_handlers: GatewayRequestHandlers = {
    "node.pending.drain": _node_pending_drain_handler,
    "node.pending.enqueue": _node_pending_enqueue_handler,
}

