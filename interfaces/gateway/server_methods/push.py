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


def _push_test_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params")
    respond = opts.get("respond")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid push.test params")
        return

    node_id = _norm_str(params.get("nodeId")) or ""
    if not node_id:
        _bad(respond, "nodeId required")
        return

    title = _norm_str(params.get("title")) or "Oclaw"
    body = _norm_str(params.get("body")) or f"Push test for node {node_id}"
    environment = _norm_str(params.get("environment"))

    # Expected context hook for runtime implementation.
    sender = context.get("send_push_test") if isinstance(context, dict) else None
    if not callable(sender):
        _ok(
            respond,
            {
                "ok": True,
                "nodeId": node_id,
                "title": title,
                "body": body,
                "environment": environment,
                "transport": "staging",
            },
        )
        return

    try:
        result = sender(
            {
                "nodeId": node_id,
                "title": title,
                "body": body,
                "environment": environment,
            }
        )
    except Exception as exc:
        _unavailable(respond, str(exc))
        return

    if not result:
        _bad(respond, f"node {node_id} has no APNs registration (connect iOS node first)")
        return
    _ok(respond, result if isinstance(result, dict) else {"ok": True})


push_handlers: GatewayRequestHandlers = {
    "push.test": _push_test_handler,
}

