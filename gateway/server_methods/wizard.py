from __future__ import annotations

from uuid import uuid4
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


def _sessions(context: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(context, dict):
        return {}
    sessions = context.get("wizardSessions")
    if isinstance(sessions, dict):
        return sessions
    created: dict[str, dict[str, Any]] = {}
    context["wizardSessions"] = created
    return created


def _find_running(context: Any) -> str | None:
    for sid, session in _sessions(context).items():
        if isinstance(session, dict) and session.get("status") == "running":
            return sid
    return None


def _wizard_start_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid wizard.start params")
        return
    mode = _norm_str(params.get("mode"))
    if not mode:
        _bad(respond, "invalid wizard.start params")
        return
    running = _find_running(context)
    if running:
        _unavailable(respond, "wizard already running")
        return
    session_id = str(uuid4())
    session = {
        "status": "running",
        "error": None,
        "mode": mode,
        "workspace": _norm_str(params.get("workspace")),
        "step": 0,
        "history": [],
    }
    _sessions(context)[session_id] = session
    _ok(
        respond,
        {
            "sessionId": session_id,
            "done": False,
            "step": {"id": "step-1", "kind": "input", "prompt": "Provide first value"},
        },
    )


def _wizard_next_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid wizard.next params")
        return
    session_id = _norm_str(params.get("sessionId"))
    if not session_id:
        _bad(respond, "invalid wizard.next params")
        return
    session = _sessions(context).get(session_id)
    if not isinstance(session, dict):
        _bad(respond, "wizard not found")
        return
    answer = params.get("answer")
    if answer is not None:
        if session.get("status") != "running":
            _bad(respond, "wizard not running")
            return
        session["history"].append(answer)
    step = int(session.get("step") or 0) + 1
    session["step"] = step
    if step >= 2:
        session["status"] = "done"
        _sessions(context).pop(session_id, None)
        _ok(respond, {"done": True, "result": {"ok": True}})
        return
    _ok(
        respond,
        {
            "done": False,
            "step": {"id": f"step-{step+1}", "kind": "input", "prompt": "Provide next value"},
        },
    )


def _wizard_cancel_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid wizard.cancel params")
        return
    session_id = _norm_str(params.get("sessionId"))
    if not session_id:
        _bad(respond, "invalid wizard.cancel params")
        return
    session = _sessions(context).get(session_id)
    if not isinstance(session, dict):
        _bad(respond, "wizard not found")
        return
    session["status"] = "cancelled"
    _sessions(context).pop(session_id, None)
    _ok(respond, {"status": "cancelled", "error": None})


def _wizard_status_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid wizard.status params")
        return
    session_id = _norm_str(params.get("sessionId"))
    if not session_id:
        _bad(respond, "invalid wizard.status params")
        return
    session = _sessions(context).get(session_id)
    if not isinstance(session, dict):
        _bad(respond, "wizard not found")
        return
    status = str(session.get("status") or "unknown")
    out = {"status": status, "error": session.get("error")}
    if status != "running":
        _sessions(context).pop(session_id, None)
    _ok(respond, out)


wizard_handlers: GatewayRequestHandlers = {
    "wizard.start": _wizard_start_handler,
    "wizard.next": _wizard_next_handler,
    "wizard.cancel": _wizard_cancel_handler,
    "wizard.status": _wizard_status_handler,
}

