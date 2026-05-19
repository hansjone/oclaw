from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from datetime import datetime
from typing import Any, Callable

from runtime.agents.factory import build_gateway_executor
from runtime.chat.persist_terminal_fallback import persist_assistant_text_if_turn_missing
from runtime.gateway import OclawGateway
from runtime.lang import resolve_runtime_lang
from runtime.types import StandardMessage
from svc.config.paths import db_path
from svc.persistence.sqlite_store import SqliteStore
from svc.persistence.assistant_store import get_assistant_store

_LOG = logging.getLogger(__name__)


def _persisted_chat_attachments_nonempty(raw: Any) -> bool:
    """True when chat_message.attachments has at least one JSON object (list or dict or encoded string)."""
    if raw is None:
        return False
    if isinstance(raw, list):
        return len(raw) > 0
    if isinstance(raw, dict):
        return bool(raw)
    s = str(raw).strip()
    if not s or s.lower() == "null":
        return False
    try:
        parsed = json.loads(s)
        if isinstance(parsed, list):
            return len(parsed) > 0
        if isinstance(parsed, dict):
            return bool(parsed)
    except Exception:
        return bool(s)
    return False


def _assistant_row_meaningful_for_terminal_snapshot(m: Any) -> bool:
    """Whether an assistant row should participate in WS ``final`` snapshot selection.

    Rows with ``content`` empty but ``tool_calls`` + ``event_payload.reasoning_content`` (common right
    before tool execution finishes) were previously skipped, so the bridge picked an older assistant
    row or only token fallback — matching \"reasoning then nothing\" when the post-tool reply never
    landed in DB in time.
    """
    if str(getattr(m, "role", "") or "").lower() != "assistant":
        return False
    if str(getattr(m, "content", "") or "").strip():
        return True
    if _persisted_chat_attachments_nonempty(getattr(m, "attachments", None)):
        return True
    tc = getattr(m, "tool_calls", None)
    if tc is not None:
        s = str(tc).strip()
        if not s or s.lower() == "null":
            pass
        else:
            try:
                parsed = json.loads(s) if isinstance(tc, str) else tc
            except Exception:
                return True
            if isinstance(parsed, list) and len(parsed) > 0:
                return True
            if isinstance(parsed, dict) and parsed:
                return True
    ep = getattr(m, "event_payload", None)
    if ep is None:
        return False
    es = str(ep).strip()
    return bool(es) and es.lower() != "null"


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
    def _to_ms(v: Any) -> int | None:
        s = str(v or "").strip()
        if not s:
            return None
        try:
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            return int(datetime.fromisoformat(s).timestamp() * 1000)
        except Exception:
            return None

    def _delta(a: int | None, b: int | None) -> int | None:
        if a is None or b is None:
            return None
        d = int(b - a)
        return d if d >= 0 else None

    def _compute_ttft(trace_rows: list[dict[str, Any]], *, accepted_ms: int | None) -> dict[str, Any]:
        ws_accepted_ms = accepted_ms
        gateway_received_ms = None
        model_chat_start_ms = None
        ws_first_token_ms = None
        for row in trace_rows or []:
            if not isinstance(row, dict):
                continue
            et = str(row.get("event_type") or "").strip()
            payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
            rts = _to_ms(row.get("timestamp"))
            if et == "gateway_received":
                gateway_received_ms = rts if rts is not None else gateway_received_ms
                if ws_accepted_ms is None:
                    try:
                        vv = payload.get("ws_client_send_ms")
                        if vv is not None:
                            ws_accepted_ms = int(vv)
                    except Exception:
                        pass
            elif et == "model_chat_start":
                model_chat_start_ms = rts if rts is not None else model_chat_start_ms
            elif et == "ws_first_token":
                if ws_first_token_ms is None:
                    try:
                        vf = payload.get("ws_first_token_ms")
                        if vf is not None:
                            ws_first_token_ms = int(vf)
                    except Exception:
                        pass
                if ws_first_token_ms is None:
                    ws_first_token_ms = rts if rts is not None else ws_first_token_ms
        return {
            "ws_accepted_ms": ws_accepted_ms,
            "gateway_received_ms": gateway_received_ms,
            "model_chat_start_ms": model_chat_start_ms,
            "ws_first_token_ms": ws_first_token_ms,
            "accepted_to_gateway_ms": _delta(ws_accepted_ms, gateway_received_ms),
            "gateway_to_model_start_ms": _delta(gateway_received_ms, model_chat_start_ms),
            "model_start_to_first_token_ms": _delta(model_chat_start_ms, ws_first_token_ms),
            "gateway_to_first_token_ms": _delta(gateway_received_ms, ws_first_token_ms),
            "accepted_to_first_token_ms": _delta(ws_accepted_ms, ws_first_token_ms),
        }

    accepted_ms = now_ms()
    msg_text = str(p.get("message") or "").strip()
    attachments = normalize_ws_attachments(p.get("attachments"))
    execution_mode = str(p.get("execution_mode") or "agent").strip().lower() or "agent"
    if execution_mode not in {"agent", "plan"}:
        execution_mode = "agent"
    plan_agent_version = str(p.get("plan_agent_version") or "v1").strip().lower() or "v1"
    if plan_agent_version not in {"v1", "v2"}:
        plan_agent_version = "v1"
    store = get_assistant_store()
    gw = OclawGateway(store=store)

    ctx = conn.auth_ctx or {}
    tenant_id = str(ctx.get("tenant_id") or "")
    user_id = str(ctx.get("user_id") or "")
    lang = resolve_runtime_lang(
        store=store,
        hint=str(p.get("lang") or ""),
        user_text=msg_text,
    )

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
    first_token_ms_holder: dict[str, int | None] = {"ms": None}
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
        if first_token_ms_holder["ms"] is None and token_text:
            first_token_ms_holder["ms"] = now_ms()
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
            "execution_mode": execution_mode,
            "plan_agent_version": plan_agent_version,
            "relay_share_envelope": dict(p.get("relay_share_envelope") or {})
            if isinstance(p.get("relay_share_envelope"), dict)
            else {},
            "acp_parent_run_id": str(p.get("acp_parent_run_id") or ""),
            "acp_child_run_id": str(p.get("acp_child_run_id") or ""),
            "ws_accepted_ms": int(accepted_ms),
        },
    )

    await conn.emit_agent_event(run_id=run_id_holder["run_id"], stream="lifecycle", data={"phase": "start", "status": "accepted"})
    if send_response:
        try:
            await conn.send_event(
                "session.turn_started",
                {"runId": run_id_holder["run_id"], "sessionKey": str(session_id), "acceptedAt": int(accepted_ms)},
            )
        except Exception:
            pass
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

    async def _heartbeat_during_turn(stop_evt: asyncio.Event) -> None:
        # Keep WS active while model/tool pipeline is still preparing first token.
        # Some proxies/load balancers close idle WS in 20-30s without downstream frames.
        while not stop_evt.is_set():
            try:
                await asyncio.wait_for(stop_evt.wait(), timeout=4.0)
                break
            except asyncio.TimeoutError:
                rid = run_id_holder.get("run_id") or ""
                if not rid:
                    continue
                with conn._abort_lock:
                    if rid in conn._aborted_run_ids:
                        continue
                try:
                    await conn.emit_agent_event(
                        run_id=rid,
                        stream="lifecycle",
                        data={"phase": "running", "event": "heartbeat"},
                    )
                except Exception:
                    # Best-effort keepalive; never fail the turn on heartbeat errors.
                    pass

    hb_stop = asyncio.Event()
    hb_task: asyncio.Task[Any] | None = asyncio.create_task(_heartbeat_during_turn(hb_stop))
    try:
        result = await asyncio.to_thread(_run_turn_sync)
    except Exception as exc:
        hb_stop.set()
        if hb_task is not None:
            try:
                await hb_task
            except Exception:
                pass
        err_text = str(exc or "agent_failed")
        user_facing_error = (
            "本轮执行失败：工具不可用或执行异常。"
            f"\n\n错误信息：{err_text}\n\n请重试，或改用其它可用工具。"
        )
        fail_msg: dict[str, Any] = {
            "role": "assistant",
            "content": user_facing_error,
            "timestamp": now_ms(),
        }
        try:
            store.add_message(
                session_id=str(session_id),
                role="assistant",
                content=str(user_facing_error),
                turn_uuid=None,
                event_type="assistant_text",
            )
        except Exception:
            _LOG.exception(
                "turn_runner_failed_reply_persist_failed session_id=%s run_id=%s",
                str(session_id),
                str(run_id_holder.get("run_id") or ""),
            )
        if send_response:
            await conn.send_res(
                req_id,
                ok=True,
                payload={
                    "runId": run_id_holder.get("run_id") or "",
                    "acceptedAt": now_ms(),
                    "mode": "sync_direct",
                    "taskId": "",
                    "traceId": "",
                    "reply": user_facing_error,
                    "selectedSpecialist": str(p.get("specialist") or "generalist"),
                    "interactionMode": str(p.get("interaction_mode") or "comprehensive"),
                    "dispatchReason": "execution_failed",
                    "executionMode": execution_mode,
                    "managerSelectedSpecialist": str(p.get("specialist") or "generalist"),
                    "requestedSpecialist": str(p.get("specialist") or "generalist"),
                    "dynamicAgentUsed": False,
                    "dynamicAgentName": "",
                    "relayPointerCount": 0,
                    "relayEnvelopePresent": False,
                    "relayEnvelopePointerCount": 0,
                    "relayTtlTurnCount": int(marker_turn_count),
                    "relayTtlSessionCount": int(marker_session_count),
                    "relayTtlKeepCount": int(marker_keep_count),
                    "status": "failed",
                    "error": err_text,
                },
            )
        await conn.emit_agent_event(
            run_id=run_id_holder.get("run_id") or "",
            stream="lifecycle",
            # Always emit a terminal lifecycle event even on failure.
            data={"phase": "end", "status": "error", "error": str(exc or "agent_failed")},
        )
        await conn.emit_chat_event(
            run_id=run_id_holder.get("run_id") or "",
            state="final",
            reply=user_facing_error,
            message=fail_msg,
            session_key=str(session_id),
        )
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
        try:
            await conn.send_event("session.message", {"sessionKey": str(session_id), "message": fail_msg})
        except Exception:
            pass
        return
    finally:
        hb_stop.set()
        if hb_task is not None:
            try:
                await hb_task
            except Exception:
                pass
        _rid0 = str(run_id_holder.get("run_id") or "")
        if _rid0:
            with conn._abort_lock:
                conn._active_run_session.pop(_rid0, None)
                conn._aborted_run_ids.discard(_rid0)

    rid = str(getattr(result, "run_id", "") or run_id_holder.get("run_id") or "")
    run_status = "success"
    run_last_error_code = ""
    run_stop_reason = ""
    run_error_detail = ""
    try:
        rr = store.oclaw_run_get(run_id=rid, tenant_id=tenant_id or None) if rid else None
        if rr is not None:
            run_status = str(getattr(rr, "status", "") or "success").strip().lower() or "success"
            payload = getattr(rr, "payload", {}) or {}
            if isinstance(payload, dict):
                run_last_error_code = str(payload.get("last_error_code") or "").strip()
                run_stop_reason = str(payload.get("stop_reason") or "").strip()
        if rid and run_status == "failed":
            attempts = store.oclaw_attempt_list(run_id=rid, limit=30)
            if attempts:
                latest = attempts[-1] if isinstance(attempts[-1], dict) else {}
                run_error_detail = str((latest or {}).get("reason") or "").strip()
    except Exception:
        pass
    ttft_payload: dict[str, Any] | None = None
    try:
        ft = first_token_ms_holder.get("ms")
        tid = str(getattr(result, "trace_id", "") or "")
        if ft is not None and tid:
            store.add_trace_event(
                session_id=str(session_id),
                trace_id=tid,
                span_id=uuid.uuid4().hex,
                parent_span_id=None,
                event_type="ws_first_token",
                payload={"run_id": str(rid), "ws_first_token_ms": int(ft), "ws_accepted_ms": int(accepted_ms)},
            )
    except Exception:
        pass
    try:
        show_ttft = str(store.get_setting("AIA_CHAT_SHOW_TTFT_DEBUG") or "").strip().lower() in {"1", "true", "yes", "on"}
        tid = str(getattr(result, "trace_id", "") or "")
        if show_ttft and tid:
            rows = store.list_trace_events_for_trace(session_id=str(session_id), trace_id=tid, limit=400)
            ttft_payload = _compute_ttft(rows, accepted_ms=int(accepted_ms))
    except Exception:
        ttft_payload = None
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
                "executionMode": execution_mode,
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
                "ttft": ttft_payload if isinstance(ttft_payload, dict) else None,
                "status": run_status,
                "lastErrorCode": run_last_error_code,
                "stopReason": run_stop_reason,
                "errorDetail": run_error_detail,
            },
        )
    await conn.emit_agent_event(
        run_id=rid,
        stream="lifecycle",
        data={
            "phase": "end",
            "status": "error" if run_status == "failed" else "ok",
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
    stream_snapshot = str(final_text or "").strip()
    turn_for_persist = str(getattr(result, "turn_uuid", "") or "").strip()
    final_msg: dict[str, Any] = {"role": "assistant", "content": final_text, "timestamp": now_ms()}
    if run_status == "failed" and not stream_snapshot:
        err_code = run_last_error_code or "unknown_error"
        stop_reason = run_stop_reason or "failed"
        detail_line = f"\n详细原因：{run_error_detail}" if run_error_detail else ""
        final_text = (
            "本轮执行失败，已提前结束。"
            f"\n\n错误代码：{err_code}"
            f"\n停止原因：{stop_reason}"
            f"{detail_line}"
            "\n\n请重试，或减少输入复杂度后再试。"
        )
        final_msg = {"role": "assistant", "content": final_text, "timestamp": now_ms()}
        try:
            store.add_message(
                session_id=str(session_id),
                role="assistant",
                content=str(final_text),
                turn_uuid=turn_for_persist or None,
                event_type="assistant_text",
            )
        except Exception:
            _LOG.exception(
                "turn_runner_failed_final_reply_persist_failed session_id=%s run_id=%s",
                str(session_id),
                str(rid or ""),
            )
    elif run_status != "failed":
        try:
            def _event_payload_as_dict(raw: Any) -> dict[str, Any]:
                if raw is None or not str(raw).strip():
                    return {}
                if isinstance(raw, dict):
                    return dict(raw)
                try:
                    obj = json.loads(str(raw))
                except Exception:
                    return {}
                return dict(obj) if isinstance(obj, dict) else {}

            persisted = store.get_messages(session_id=session_id, limit=200)
            for m in reversed(list(persisted or [])):
                if str(getattr(m, "role", "") or "").lower() != "assistant":
                    continue
                if not _assistant_row_meaningful_for_terminal_snapshot(m):
                    continue
                content = str(getattr(m, "content", "") or "")
                atraw = getattr(m, "attachments", None)
                # Keep streamed / gateway reply_text when newest DB row is tool-only (empty body).
                final_text = str(content or "").strip() or str(final_text or "").strip()
                et = str(getattr(m, "event_type", "") or "").strip()
                ep = getattr(m, "event_payload", None)
                final_msg = {
                    "id": int(getattr(m, "id", 0) or 0),
                    "role": "assistant",
                    "content": content,
                    "timestamp": str(getattr(m, "timestamp", "") or ""),
                    "tool_calls": getattr(m, "tool_calls", None),
                    "attachments": atraw,
                }
                # Admin / WS clients build the reasoning fold from event_payload.reasoning_content (thinking mode)
                # or event_type=reasoning rows after reload; including these on ``final`` avoids "stream had
                # reasoning but terminal bubble only shows tools" when the UI hydrates from this snapshot.
                if et:
                    final_msg["event_type"] = et
                if ep is not None and str(ep).strip():
                    final_msg["event_payload"] = ep
                # Thinking-mode: reasoning_content is often stored on an earlier assistant row in the same turn
                # (e.g. first tool_call snapshot) while the newest row is post-tool prose only — merge it in.
                ep_d = _event_payload_as_dict(final_msg.get("event_payload"))
                rc0 = str(ep_d.get("reasoning_content") or "").strip()
                turn_key = str(getattr(m, "turn_uuid", "") or "").strip()
                if not rc0 and turn_key:
                    for m2 in reversed(list(persisted or [])):
                        if str(getattr(m2, "role", "") or "").lower() != "assistant":
                            continue
                        if str(getattr(m2, "turn_uuid", "") or "").strip() != turn_key:
                            continue
                        ep2 = _event_payload_as_dict(getattr(m2, "event_payload", None))
                        rc2 = str(ep2.get("reasoning_content") or "").strip()
                        if rc2:
                            merged = dict(ep_d)
                            merged["reasoning_content"] = rc2
                            final_msg["event_payload"] = json.dumps(merged, ensure_ascii=False)
                            break
                break
        except Exception:
            pass

    persist_assistant_text_if_turn_missing(
        store=store,
        session_id=str(session_id),
        turn_uuid=turn_for_persist,
        final_text=stream_snapshot,
        log_prefix="turn_runner_ws_text_fallback_persisted",
    )

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

