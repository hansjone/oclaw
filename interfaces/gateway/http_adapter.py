from __future__ import annotations

from typing import Any

from svc.persistence.assistant_store import get_assistant_store

from .context_builder import build_common_gateway_context
from .dispatcher import build_gateway_method_handlers


def _build_http_context() -> dict[str, Any]:
    store = get_assistant_store()
    context = build_common_gateway_context(store=store)
    context["session_event_subscribers"] = set()
    context["session_message_subscribers"] = {}
    return context


def dispatch_gateway_http_method(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    handlers = build_gateway_method_handlers()
    m = str(method or "").strip()
    handler = handlers.get(m)
    if not callable(handler):
        return {"ok": False, "payload": None, "error": {"code": "INVALID_REQUEST", "message": f"unknown method: {m}"}}

    result: dict[str, Any] = {"ok": False, "payload": None, "error": {"code": "UNAVAILABLE", "message": "no response"}}

    def _respond(ok: bool, payload: Any | None, error: dict[str, Any] | None, _meta: dict[str, Any] | None) -> None:
        result["ok"] = bool(ok)
        result["payload"] = payload
        result["error"] = error

    opts = {
        "req": {"id": "http", "method": m, "params": dict(params or {})},
        "params": dict(params or {}),
        "client": {"conn_id": "http", "internal": {}},
        "respond": _respond,
        "context": _build_http_context(),
        "is_webchat_connect": lambda _p: False,
    }
    try:
        handler(opts)
    except Exception as exc:
        return {"ok": False, "payload": None, "error": {"code": "UNAVAILABLE", "message": f"{type(exc).__name__}: {exc}"}}
    return result


__all__ = ["dispatch_gateway_http_method"]

