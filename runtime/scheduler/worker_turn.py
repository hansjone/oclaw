from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


from runtime.orchestration.group_ingest import is_nonsend_channel_reply_text
from runtime.scheduler.turn_text import format_scheduled_user_reminder


def resolve_scheduled_outbound_text(*, payload: dict[str, Any], reply_text: str) -> str:
    text = str(reply_text or "").strip()
    if text and not is_nonsend_channel_reply_text(text):
        return text
    prompt = str(payload.get("prompt_text") or "").strip()
    if prompt:
        return format_scheduled_user_reminder(prompt)
    return ""


def _persist_scheduled_assistant_reply(
    store: Any,
    *,
    session_id: str,
    turn_uuid: str,
    reply_text: str,
) -> None:
    sid = str(session_id or "").strip()
    body = str(reply_text or "").strip()
    if not sid or not body:
        return
    tu = str(turn_uuid or "").strip()
    payload = {"scheduled_proactive": True}
    try:
        rows = store.get_messages(session_id=sid, limit=80)
    except Exception:
        rows = []
    if tu:
        for m in rows or []:
            if str(getattr(m, "role", "") or "").lower() != "assistant":
                continue
            if str(getattr(m, "turn_uuid", "") or "").strip() != tu:
                continue
            existing = str(getattr(m, "content", "") or "").strip()
            mid = int(getattr(m, "id", 0) or 0)
            updater = getattr(store, "update_message_content", None)
            if existing == body:
                if mid > 0 and callable(updater):
                    merged = dict(payload)
                    raw_ep = getattr(m, "event_payload", None)
                    if isinstance(raw_ep, dict):
                        merged = {**raw_ep, **merged}
                    elif isinstance(raw_ep, str) and raw_ep.strip():
                        try:
                            parsed = json.loads(raw_ep)
                            if isinstance(parsed, dict):
                                merged = {**parsed, **merged}
                        except Exception:
                            pass
                    updater(
                        session_id=sid,
                        message_id=mid,
                        content=body,
                        event_payload=merged,
                    )
                return
            if not existing:
                if mid > 0 and callable(updater):
                    updater(
                        session_id=sid,
                        message_id=mid,
                        content=body,
                        event_payload=payload,
                    )
                    return
            break
    for m in rows or []:
        if str(getattr(m, "role", "") or "").lower() != "assistant":
            continue
        if str(getattr(m, "content", "") or "").strip() == body:
            return
    try:
        store.add_message(
            session_id=sid,
            role="assistant",
            content=body,
            turn_uuid=tu or None,
            event_type="assistant_text",
            event_payload=payload,
        )
    except Exception:
        pass


def finalize_scheduled_turn_success(
    store: Any,
    *,
    task: Any,
    payload: dict[str, Any],
    base_result: dict[str, Any],
) -> None:
    from runtime.scheduler.channel_delivery import deliver_scheduled_reply

    tenant_id = str(payload.get("tenant_id") or "")
    job_id = str(payload.get("job_id") or "")
    scheduled_run_id = str(payload.get("run_id_scheduled") or "")
    reply_text = resolve_scheduled_outbound_text(payload=payload, reply_text=str(base_result.get("reply_text") or ""))
    delivery = payload.get("delivery") if isinstance(payload.get("delivery"), dict) else {}
    delivery_json = json.dumps(delivery, ensure_ascii=False)

    job = store.scheduled_job_get(job_id=job_id, tenant_id=tenant_id) if job_id else None
    if job:
        delivery_json = str(getattr(job, "delivery_json", "") or delivery_json)

    _persist_scheduled_assistant_reply(
        store,
        session_id=str(payload.get("session_id") or ""),
        turn_uuid=str(base_result.get("turn_uuid") or payload.get("run_id") or ""),
        reply_text=reply_text,
    )
    delivery_status = deliver_scheduled_reply(
        store,
        tenant_id=tenant_id,
        reply_text=reply_text,
        delivery_json=delivery_json,
        resolved_channel=str(payload.get("resolved_channel") or ""),
        resolved_chat_id=str(payload.get("resolved_chat_id") or ""),
        resolved_account_id=str(payload.get("resolved_account_id") or ""),
        session_id=str(payload.get("session_id") or ""),
    )
    if scheduled_run_id:
        store.scheduled_job_run_update(
            run_id=scheduled_run_id,
            tenant_id=tenant_id,
            patch={
                "status": "success" if delivery_status.get("ok") else "failed",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "reply_text": reply_text,
                "delivery_status": delivery_status,
                "session_id": str(payload.get("session_id") or ""),
            },
        )
    if job_id and job:
        pause_after = str(getattr(job, "schedule_kind", "") or "") == "once"
        store.scheduled_job_mark_run(
            job_id=job_id,
            tenant_id=tenant_id,
            last_run_status="success" if delivery_status.get("ok") else "failed",
            pause_after=pause_after,
        )


def finalize_scheduled_turn_failure(
    store: Any,
    *,
    payload: dict[str, Any],
    error: str,
) -> None:
    tenant_id = str(payload.get("tenant_id") or "")
    job_id = str(payload.get("job_id") or "")
    scheduled_run_id = str(payload.get("run_id_scheduled") or "")
    if scheduled_run_id:
        store.scheduled_job_run_update(
            run_id=scheduled_run_id,
            tenant_id=tenant_id,
            patch={
                "status": "failed",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "error": str(error or "")[:500],
            },
        )
    if job_id:
        job = store.scheduled_job_get(job_id=job_id, tenant_id=tenant_id)
        pause_after = bool(job and str(getattr(job, "schedule_kind", "") or "") == "once")
        store.scheduled_job_mark_run(
            job_id=job_id,
            tenant_id=tenant_id,
            last_run_status="failed",
            pause_after=pause_after,
        )


__all__ = ["finalize_scheduled_turn_failure", "finalize_scheduled_turn_success"]
