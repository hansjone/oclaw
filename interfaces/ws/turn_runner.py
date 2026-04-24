from __future__ import annotations

import asyncio
import threading
import uuid
from typing import Any, Callable

from oclaw.runtime.agents.factory import build_gateway_executor
from oclaw.runtime.gateway import OclawGateway
from oclaw.runtime.types import StandardMessage
from oclaw.platform.config.paths import db_path
from oclaw.platform.persistence.sqlite_store import SqliteStore


async def run_agent_turn_via_bridge(
    *,
    conn: Any,
    req_id: str,
    p: dict[str, Any],
    session_id: str,
    send_response: bool,
    normalize_ws_attachments: Callable[[Any], list[dict[str, Any]]],
    validate_relay_share_envelope: Callable[[dict[str, Any]], tuple[bool, str, dict[str, Any]]],
    now_ms: Callable[[], int],
    error_shape: Callable[[str, str], dict[str, Any]],
) -> None:
    msg_text = str(p.get("message") or "").strip()
    attachments = list(p.get("attachments") or [])
    store = SqliteStore(db_path())
    gw = OclawGateway(store=store)

    ctx = conn.auth_ctx or {}
    tenant_id = str(ctx.get("tenant_id") or "")
    user_id = str(ctx.get("user_id") or "")
    lang = "zh"

    manager_agent = build_gateway_executor(
        store,
        lang=lang,
        specialist="generalist",
        viewer_user_id=user_id or None,
        viewer_username=str(ctx.get("username") or "") or None,
        viewer_tenant_id=tenant_id or None,
        policy_session_id=session_id,
        path_policy_tenant_id=tenant_id or None,
        path_policy_user_id=user_id or None,
    )
    specialist_factory = lambda sid: build_gateway_executor(
        store,
        lang=lang,
        specialist=sid,
        viewer_user_id=user_id or None,
        viewer_username=str(ctx.get("username") or "") or None,
        viewer_tenant_id=tenant_id or None,
        policy_session_id=session_id,
        path_policy_tenant_id=tenant_id or None,
        path_policy_user_id=user_id or None,
    )

    run_id_holder: dict[str, str] = {"run_id": str(p.get("runId") or uuid.uuid4().hex)}
    loop = asyncio.get_running_loop()
    run_id = str(run_id_holder.get("run_id") or "")
    if run_id:
        with conn._abort_lock:
            conn._active_run_session[run_id] = str(session_id)

    buf_lock = threading.Lock()
    token_chunks: list[str] = []
    marker_turn_count = 0
    marker_session_count = 0
    marker_keep_count = 0

    def _schedule(coro: Any) -> None:
        try:
            loop.call_soon_threadsafe(lambda: asyncio.create_task(coro))
        except Exception:
            pass

    def on_token(tok: str) -> None:
        token_text = str(tok)
        rid = run_id_holder.get("run_id") or ""
        if rid:
            with conn._abort_lock:
                if rid in conn._aborted_run_ids:
                    return
        if rid and not conn._is_webchat_client:
            _schedule(conn.emit_agent_event(run_id=rid, stream="assistant", data={"event": "delta", "delta": token_text}))
        with buf_lock:
            token_chunks.append(token_text)
        _schedule(
            conn.emit_chat_event(
                run_id=rid,
                state="delta",
                delta=token_text,
                session_key=str(session_id),
            )
        )

    def on_progress(text: str) -> None:
        rid = run_id_holder.get("run_id") or ""
        if rid:
            with conn._abort_lock:
                if rid in conn._aborted_run_ids:
                    return
            _schedule(conn.emit_agent_event(run_id=rid, stream="lifecycle", data={"phase": "running", "message": str(text)}))

    def on_tool_ui(name: str, payload: dict[str, Any]) -> None:
        rid = run_id_holder.get("run_id") or ""
        if rid:
            with conn._abort_lock:
                if rid in conn._aborted_run_ids:
                    return
            pl = {"runId": rid, "sessionKey": str(session_id), "name": str(name), "payload": dict(payload or {}), "ts": now_ms()}
            _schedule(conn.send_event("session.tool", pl))

    msg = StandardMessage(
        session_id=session_id,
        tenant_id=tenant_id,
        user_id=user_id,
        role=str(p.get("role") or "member"),
        channel=str(p.get("channel") or "ws"),
        text=msg_text,
        attachments=attachments,
        metadata={
            "interaction_mode": str(p.get("interaction_mode") or "comprehensive"),
            "selected_specialist": str(p.get("specialist") or "generalist"),
            "relay_share_envelope": dict(p.get("relay_share_envelope") or {})
            if isinstance(p.get("relay_share_envelope"), dict)
            else {},
            "acp_parent_run_id": str(p.get("acp_parent_run_id") or ""),
            "acp_child_run_id": str(p.get("acp_child_run_id") or ""),
        },
    )

    await conn.emit_agent_event(run_id=run_id_holder["run_id"], stream="lifecycle", data={"phase": "start", "status": "accepted"})
    try:
        relay_env = p.get("relay_share_envelope") if isinstance(p.get("relay_share_envelope"), dict) else {}
        relay_pointers = 0
        relay_turn = 0
        relay_session = 0
        relay_keep = 0
        if isinstance(relay_env, dict):
            ad = relay_env.get("attachments") if isinstance(relay_env.get("attachments"), dict) else {}
            ps = ad.get("pointers") if isinstance(ad.get("pointers"), list) else []
            relay_pointers = len(ps)
            for item in ps:
                if not isinstance(item, dict):
                    continue
                ttl = str(item.get("ttl_policy") or "").strip().lower()
                if ttl == "turn":
                    relay_turn += 1
                elif ttl == "session":
                    relay_session += 1
                elif ttl == "keep":
                    relay_keep += 1
        marker_turn_count = int(relay_turn)
        marker_session_count = int(relay_session)
        marker_keep_count = int(relay_keep)
        await conn.send_event(
            "session.marker",
            {
                "runId": run_id_holder["run_id"],
                "sessionKey": str(session_id),
                "action": "ingress",
                "relayPointerCount": int(relay_pointers),
                "relayEnvelopePresent": bool(isinstance(relay_env, dict) and bool(relay_env)),
                "relayEnvelopePointerCount": int(relay_pointers),
                "relayTtlTurnCount": int(relay_turn),
                "relayTtlSessionCount": int(relay_session),
                "relayTtlKeepCount": int(relay_keep),
            },
        )
    except Exception:
        pass

    def _run_turn_sync() -> Any:
        return gw.handle_turn(
            msg=msg,
            lang=lang,
            executor=manager_agent,
            specialist_executor_factory=specialist_factory,
            run_id=run_id_holder.get("run_id") or None,
            on_token=on_token,
            on_progress=on_progress,
            on_tool_ui=on_tool_ui,
        )

    try:
        result = await asyncio.to_thread(_run_turn_sync)
    except Exception as exc:
        if send_response:
            await conn.send_res(req_id, ok=False, error=error_shape("UNAVAILABLE", str(exc or "agent_failed")))
        await conn.emit_agent_event(
            run_id=run_id_holder.get("run_id") or "",
            stream="lifecycle",
            data={"phase": "error", "status": "error", "error": str(exc or "agent_failed")},
        )
        await conn.emit_chat_event(run_id=run_id_holder.get("run_id") or "", state="error", error=str(exc or "agent_failed"))
        try:
            await conn.send_event(
                "session.marker",
                {
                    "runId": run_id_holder.get("run_id") or "",
                    "sessionKey": str(session_id),
                    "action": "turn_reclaimed",
                    "reclaimedTurnPointers": int(marker_turn_count),
                    "relayTtlTurnCount": int(marker_turn_count),
                    "relayTtlSessionCount": int(marker_session_count),
                    "relayTtlKeepCount": int(marker_keep_count),
                },
            )
        except Exception:
            pass
        return
    finally:
        _rid0 = str(run_id_holder.get("run_id") or "")
        if _rid0:
            with conn._abort_lock:
                conn._active_run_session.pop(_rid0, None)
                conn._aborted_run_ids.discard(_rid0)

    rid = str(getattr(result, "run_id", "") or run_id_holder.get("run_id") or "")
    with conn._abort_lock:
        if rid and rid in conn._aborted_run_ids:
            try:
                await conn.send_event(
                    "session.marker",
                    {
                        "runId": rid,
                        "sessionKey": str(session_id),
                        "action": "turn_reclaimed",
                        "reclaimedTurnPointers": int(marker_turn_count),
                        "relayTtlTurnCount": int(marker_turn_count),
                        "relayTtlSessionCount": int(marker_session_count),
                        "relayTtlKeepCount": int(marker_keep_count),
                    },
                )
            except Exception:
                pass
            return
    if send_response:
        await conn.send_res(
            req_id,
            ok=True,
            payload={
                "runId": rid,
                "acceptedAt": now_ms(),
                "mode": str(getattr(result, "mode", "sync_direct") or "sync_direct"),
                "taskId": str(getattr(result, "task_id", "") or ""),
                "traceId": str(getattr(result, "trace_id", "") or ""),
                "reply": str(getattr(result, "reply_text", "") or ""),
                "selectedSpecialist": str(getattr(result, "selected_specialist", "generalist") or "generalist"),
                "interactionMode": str(getattr(result, "interaction_mode", "comprehensive") or "comprehensive"),
                "dispatchReason": str(getattr(result, "dispatch_reason", "") or ""),
                "managerSelectedSpecialist": str(getattr(result, "manager_selected_specialist", "generalist") or "generalist"),
                "requestedSpecialist": str(getattr(result, "requested_specialist", "generalist") or "generalist"),
                "dynamicAgentUsed": bool(getattr(result, "dynamic_agent_used", False) or False),
                "dynamicAgentName": str(getattr(result, "dynamic_agent_name", "") or ""),
                "relayPointerCount": int(getattr(result, "relay_pointer_count", 0) or 0),
                "relayEnvelopePresent": bool(getattr(result, "relay_envelope_present", False) or False),
                "relayEnvelopePointerCount": int(getattr(result, "relay_envelope_pointer_count", 0) or 0),
                "relayTtlTurnCount": int(getattr(result, "relay_ttl_turn_count", 0) or 0),
                "relayTtlSessionCount": int(getattr(result, "relay_ttl_session_count", 0) or 0),
                "relayTtlKeepCount": int(getattr(result, "relay_ttl_keep_count", 0) or 0),
            },
        )
    await conn.emit_agent_event(
        run_id=rid,
        stream="lifecycle",
        data={
            "phase": "end",
            "status": "ok",
            "reply": str(getattr(result, "reply_text", "") or ""),
            "elapsedMs": int(getattr(result, "elapsed_ms", 0) or 0),
            "mode": str(getattr(result, "mode", "sync_direct") or "sync_direct"),
            "taskId": str(getattr(result, "task_id", "") or ""),
            "traceId": str(getattr(result, "trace_id", "") or ""),
        },
    )
    final_text = str(getattr(result, "reply_text", "") or "")
    if not final_text:
        with buf_lock:
            final_text = "".join(token_chunks)
    final_msg: dict[str, Any] = {"role": "assistant", "content": final_text, "timestamp": now_ms()}
    try:
        persisted = store.get_messages(session_id=session_id, limit=12)
        for m in reversed(list(persisted or [])):
            if str(getattr(m, "role", "") or "").lower() != "assistant":
                continue
            content = str(getattr(m, "content", "") or "")
            if not content.strip():
                continue
            final_text = content
            final_msg = {
                "id": int(getattr(m, "id", 0) or 0),
                "role": "assistant",
                "content": content,
                "timestamp": str(getattr(m, "timestamp", "") or ""),
                "tool_calls": getattr(m, "tool_calls", None),
                "attachments": getattr(m, "attachments", None),
            }
            break
    except Exception:
        pass

    await conn.emit_chat_event(run_id=rid, state="final", reply=str(final_text or ""), message=final_msg, session_key=str(session_id))
    try:
        await conn.send_event(
            "session.marker",
            {
                "runId": rid,
                "sessionKey": str(session_id),
                "action": "turn_reclaimed",
                "reclaimedTurnPointers": int(marker_turn_count),
                "relayTtlTurnCount": int(marker_turn_count),
                "relayTtlSessionCount": int(marker_session_count),
                "relayTtlKeepCount": int(marker_keep_count),
            },
        )
    except Exception:
        pass
    await conn.send_event("session.message", {"sessionKey": str(session_id), "message": final_msg})
    if conn._subscribed_sessions_changed:
        await conn.send_event("sessions.changed", {"sessionKey": str(session_id), "reason": "send", "ts": now_ms()})


__all__ = ["run_agent_turn_via_bridge"]

