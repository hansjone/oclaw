from __future__ import annotations

import asyncio
import uuid
from typing import Any, Callable

from oclaw.platform.config.paths import db_path
from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.interfaces.gateway.context_builder import build_common_gateway_context


def build_gateway_context(
    *,
    conn_id: str,
    subscribed_sessions_changed: bool,
    subscribed_message_keys: set[str],
    abort_lock: Any,
    active_run_session: dict[str, str],
    aborted_run_ids: set[str],
    run_agent_turn: Callable[..., Any],
    normalize_ws_attachments: Callable[[Any], list[dict[str, Any]]],
    validate_relay_share_envelope: Callable[[dict[str, Any]], tuple[bool, str, dict[str, Any]]],
    now_ms: Callable[[], int],
) -> dict[str, Any]:
    store = SqliteStore(db_path())

    def _abort_chat_run(run_id: str) -> bool:
        rid = str(run_id or "").strip()
        if not rid:
            return False
        with abort_lock:
            if rid not in active_run_session:
                return False
            aborted_run_ids.add(rid)
        return True

    def _enqueue_chat_send(session_key: str, message: str, run_id: str | None, params: dict[str, Any]) -> bool:
        sid = str(session_key or "").strip()
        txt = str(message or "").strip()
        if not sid or not txt:
            return False
        rid = str(run_id or "").strip() or uuid.uuid4().hex
        try:
            existing = store.oclaw_run_get(run_id=rid)
            if existing is not None:
                return True
        except Exception:
            pass
        with abort_lock:
            active_run_session[rid] = sid
        p = dict(params or {})
        interaction_mode = str(p.get("interaction_mode") or "comprehensive").strip().lower() or "comprehensive"
        specialist = str(p.get("specialist") or "generalist").strip().lower() or "generalist"
        if interaction_mode != "expert":
            specialist = "generalist"
        raw_env = dict(p.get("relay_share_envelope") or {}) if isinstance(p.get("relay_share_envelope"), dict) else {}
        ok_env, _err_env, norm_env = validate_relay_share_envelope(raw_env) if raw_env else (False, "", {})
        agent_params = {
            "message": txt,
            "sessionId": sid,
            "attachments": normalize_ws_attachments(p.get("attachments")),
            "idempotencyKey": str(p.get("idempotencyKey") or uuid.uuid4().hex),
            "interaction_mode": interaction_mode,
            "specialist": specialist,
            "relay_share_envelope": norm_env if ok_env else {},
            "acp_parent_run_id": str(p.get("acp_parent_run_id") or ""),
            "acp_child_run_id": str(p.get("acp_child_run_id") or ""),
            "runId": rid,
        }
        async def _delayed() -> None:
            await asyncio.sleep(0.05)
            await run_agent_turn("server_methods.chat.send", agent_params, session_id=sid, send_response=False)

        asyncio.create_task(_delayed())
        return True

    def _run_agent(params: dict[str, Any]) -> dict[str, Any]:
        p = dict(params or {})
        session_id = str(p.get("sessionId") or p.get("sessionKey") or "").strip()
        run_id = str(p.get("idempotencyKey") or "").strip() or uuid.uuid4().hex
        message = str(p.get("message") or "").strip()
        interaction_mode = str(p.get("interaction_mode") or "comprehensive").strip().lower() or "comprehensive"
        specialist = str(p.get("specialist") or "generalist").strip().lower() or "generalist"
        if interaction_mode != "expert":
            specialist = "generalist"
        raw_env = dict(p.get("relay_share_envelope") or {}) if isinstance(p.get("relay_share_envelope"), dict) else {}
        ok_env, _err_env, norm_env = validate_relay_share_envelope(raw_env) if raw_env else (False, "", {})
        agent_params = {
            "message": message,
            "sessionId": session_id,
            "attachments": normalize_ws_attachments(p.get("attachments")),
            "idempotencyKey": run_id,
            "interaction_mode": interaction_mode,
            "specialist": specialist,
            "relay_share_envelope": norm_env if ok_env else {},
            "acp_parent_run_id": str(p.get("acp_parent_run_id") or ""),
            "acp_child_run_id": str(p.get("acp_child_run_id") or ""),
            "runId": run_id,
        }
        with abort_lock:
            active_run_session[str(run_id)] = str(session_id)
        async def _delayed() -> None:
            await asyncio.sleep(0.05)
            await run_agent_turn("server_methods.agent", agent_params, session_id=session_id, send_response=False)

        asyncio.create_task(_delayed())
        return {"runId": run_id, "status": "started"}

    def _enqueue_session_send(session_key: str, message: str, params: dict[str, Any]) -> dict[str, Any]:
        sid = str(session_key or "").strip()
        txt = str(message or "").strip()
        if not sid or not txt:
            return {"sent": False}
        run_id = str((params or {}).get("idempotencyKey") or "").strip() or uuid.uuid4().hex
        queued = _enqueue_chat_send(sid, txt, run_id, dict(params or {}))
        return {"queued": bool(queued), "runId": run_id, "sent": bool(queued)}

    def _wait_for_agent_job(run_id: str, params: dict[str, Any]) -> dict[str, Any]:
        rid = str(run_id or "").strip()
        if not rid:
            return {"status": "error", "runId": rid, "summary": "runId required"}
        run = store.oclaw_run_get(run_id=rid)
        if not run:
            return {"status": "pending", "runId": rid, "summary": "run not finished", "pollAfterMs": 250}
        status = str(run.status or "").strip().lower()
        if status == "success":
            return {"status": "ok", "runId": rid}
        if status == "failed":
            return {"status": "error", "runId": rid}
        return {"status": "pending", "runId": rid, "summary": "run still processing", "pollAfterMs": 250}

    context = build_common_gateway_context(store=store)
    context.update({
        "abort_chat_run": _abort_chat_run,
        "enqueue_chat_send": _enqueue_chat_send,
        "run_agent": _run_agent,
        "enqueue_session_send": _enqueue_session_send,
        "wait_for_agent_job": _wait_for_agent_job,
        "session_event_subscribers": {conn_id} if subscribed_sessions_changed else set(),
        "session_message_subscribers": {k: {conn_id} for k in subscribed_message_keys},
    })
    return context


async def dispatch_via_server_methods(
    *,
    req_id: str,
    method: str,
    params: Any,
    conn_id: str,
    is_webchat_client: bool,
    handlers: dict[str, Any],
    context: dict[str, Any],
    send_res: Callable[..., Any],
    error_shape: Callable[[str, str], dict[str, Any]],
) -> bool:
    handler = handlers.get(str(method or ""))
    if not callable(handler):
        return False

    responded = False
    response_packet: tuple[bool, Any | None, Any | None] | None = None
    sync_response = str(method or "") == "chat.send"

    def _respond(ok: bool, payload: Any | None, error: Any | None, _meta: dict[str, Any] | None) -> None:
        nonlocal responded, response_packet
        responded = True
        if sync_response:
            response_packet = (bool(ok), payload, error)
            return

        async def _send() -> None:
            await send_res(req_id, ok=bool(ok), payload=payload, error=error)

        asyncio.create_task(_send())

    opts = {
        "req": {"id": req_id, "method": method, "params": params},
        "params": dict(params) if isinstance(params, dict) else {},
        "client": {"conn_id": conn_id, "internal": {}},
        "respond": _respond,
        "context": context,
        "is_webchat_connect": lambda _p: bool(is_webchat_client),
    }
    try:
        handler(opts)
    except Exception as exc:
        await send_res(
            req_id,
            ok=False,
            error=error_shape("UNAVAILABLE", f"server method failed: {type(exc).__name__}: {exc}"),
        )
        return True
    if sync_response and responded and response_packet is not None:
        ok, payload, error = response_packet
        await send_res(req_id, ok=ok, payload=payload, error=error)
        return True
    if responded:
        return True
    if not responded:
        await send_res(req_id, ok=False, error=error_shape("UNAVAILABLE", f"server method did not respond: {method}"))
    return True


__all__ = ["build_gateway_context", "dispatch_via_server_methods"]

