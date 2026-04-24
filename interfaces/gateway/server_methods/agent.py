from __future__ import annotations

from typing import Any

from oclaw.runtime.agents.agent_scope import resolve_agent_id_from_session_key, resolve_session_agent_id

from .shared_types import GatewayRequestHandlers
from .validation import error_shape


def _bad(respond, message: str) -> None:
    if callable(respond):
        respond(False, None, error_shape("INVALID_REQUEST", message), None)


def _ok(respond, payload: dict[str, Any] | None = None) -> None:
    if callable(respond):
        respond(True, payload or {"ok": True}, None, None)


def _agent_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid agent params")
        return
    message = params.get("message")
    idem = params.get("idempotencyKey")
    if not isinstance(message, str) or not message.strip():
        _bad(respond, "invalid agent params: message required")
        return
    if not isinstance(idem, str) or not idem.strip():
        _bad(respond, "invalid agent params: idempotencyKey required")
        return
    dedupe_key = f"agent:{idem.strip()}"
    if isinstance(context, dict):
        dedupe = context.get("dedupe")
        if isinstance(dedupe, dict) and dedupe_key in dedupe:
            cached = dedupe.get(dedupe_key) or {}
            if callable(respond):
                respond(bool(cached.get("ok")), cached.get("payload"), cached.get("error"), {"cached": True})
            return
    payload = {
        "runId": idem.strip(),
        "status": "queued",
        "summary": "agent request accepted",
    }
    if isinstance(context, dict):
        run_fn = context.get("run_agent")
        if callable(run_fn):
            try:
                run_out = run_fn(dict(params))
                if isinstance(run_out, dict):
                    payload = run_out
            except Exception as exc:
                _bad(respond, f"agent run failed: {exc}")
                return
    if isinstance(context, dict):
        dedupe = context.get("dedupe")
        if isinstance(dedupe, dict):
            dedupe[dedupe_key] = {"ok": True, "payload": payload, "error": None}
    _ok(respond, payload)


def _agent_identity_get_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    if not isinstance(params, dict):
        _bad(respond, "invalid agent.identity.get params")
        return
    agent_id = params.get("agentId")
    session_key = params.get("sessionKey")
    if agent_id is not None and not isinstance(agent_id, str):
        _bad(respond, "invalid agent.identity.get params: agentId must be string")
        return
    if session_key is not None and not isinstance(session_key, str):
        _bad(respond, "invalid agent.identity.get params: sessionKey must be string")
        return
    cfg = params.get("config") if isinstance(params.get("config"), dict) else None
    resolved_agent_id = ""
    if isinstance(agent_id, str) and agent_id.strip():
        resolved_agent_id = agent_id.strip()
    elif isinstance(session_key, str) and session_key.strip():
        if isinstance(cfg, dict) and cfg:
            resolved_agent_id = resolve_session_agent_id(session_key=session_key.strip(), config=cfg)
        else:
            resolved_agent_id = resolve_agent_id_from_session_key(session_key.strip())
    if not resolved_agent_id:
        resolved_agent_id = "main"
    _ok(
        respond,
        {
            "agentId": resolved_agent_id,
            "displayName": "Oclaw Assistant",
            "avatarUrl": None,
        },
    )


def _agent_wait_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid agent.wait params")
        return
    run_id = params.get("runId")
    if not isinstance(run_id, str) or not run_id.strip():
        _bad(respond, "invalid agent.wait params: runId required")
        return
    run_id = run_id.strip()
    if isinstance(context, dict):
        waiter = context.get("wait_for_agent_job")
        if callable(waiter):
            try:
                waited = waiter(run_id, params)
                if isinstance(waited, dict):
                    _ok(respond, waited)
                    return
            except Exception as exc:
                _bad(respond, f"agent.wait failed: {exc}")
                return
        dedupe = context.get("dedupe")
        if isinstance(dedupe, dict):
            cached = dedupe.get(f"agent:{run_id}")
            if isinstance(cached, dict):
                payload = cached.get("payload")
                if isinstance(payload, dict):
                    _ok(
                        respond,
                        {
                            "runId": run_id,
                            "status": payload.get("status") or "completed",
                            "summary": payload.get("summary") or "dedupe hit",
                        },
                    )
                    return
    _ok(
        respond,
        {
            "runId": run_id,
            "status": "completed",
            "summary": "placeholder wait result",
        },
    )


agent_handlers: GatewayRequestHandlers = {
    "agent": _agent_handler,
    "agent.identity.get": _agent_identity_get_handler,
    "agent.wait": _agent_wait_handler,
}
