from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from runtime.scheduler.session_resolver import resolve_scheduled_session, resolve_scheduled_viewer_username
from runtime.scheduler.turn_text import build_scheduled_turn_instruction
from runtime.worker import ensure_worker_started

_LOCK = threading.Lock()
_THREAD: threading.Thread | None = None
_RUNNING = False


def _tick_interval_seconds() -> float:
    import os

    raw = str(os.getenv("AIA_SCHEDULER_TICK_SECONDS") or "30").strip()
    try:
        return max(5.0, min(float(raw), 3600.0))
    except Exception:
        return 30.0


def enqueue_scheduled_job_run(
    store: Any,
    *,
    job: Any,
    mode: str = "scheduled",
) -> dict[str, Any]:
    tenant_id = str(getattr(job, "tenant_id", "") or "")
    job_id = str(getattr(job, "id") or "")
    run = store.scheduled_job_run_create(
        job_id=job_id,
        tenant_id=tenant_id,
        scheduled_at=str(getattr(job, "next_run_at", "") or datetime.now(timezone.utc).isoformat()),
        status="queued",
    )
    try:
        resolved = resolve_scheduled_session(
            store,
            job=job,
            created_by_user_id=str(getattr(job, "created_by_user_id", "") or ""),
        )
    except Exception as exc:
        store.scheduled_job_run_update(
            run_id=run.id,
            tenant_id=tenant_id,
            patch={
                "status": "failed",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "error": str(exc),
            },
        )
        store.scheduled_job_mark_run(
            job_id=job_id,
            tenant_id=tenant_id,
            last_run_status="failed",
            pause_after=False,
        )
        return {"ok": False, "error": str(exc), "run_id": run.id}

    delivery: dict[str, Any] = {}
    try:
        raw = json.loads(str(getattr(job, "delivery_json", "") or "{}"))
        if isinstance(raw, dict):
            delivery = raw
    except Exception:
        delivery = {}

    trace_id = uuid.uuid4().hex
    agent_run_id = uuid.uuid4().hex
    prompt_text = str(getattr(job, "prompt_text", "") or "").strip()
    lang = str(getattr(job, "lang", "") or "zh")
    user_text = build_scheduled_turn_instruction(prompt_text=prompt_text, mode=mode, lang=lang)
    viewer_username = resolve_scheduled_viewer_username(
        store,
        tenant_id=tenant_id,
        user_id=resolved.user_id,
        channel=resolved.channel,
    )
    payload = {
        "trace_id": trace_id,
        "run_id": agent_run_id,
        "session_id": resolved.session_id,
        "tenant_id": tenant_id,
        "user_id": resolved.user_id,
        "viewer_username": viewer_username,
        "role": "member",
        "channel": resolved.channel if resolved.channel != "admin_chat" else "admin_chat",
        "lang": lang,
        "text": user_text,
        "prompt_text": prompt_text,
        "attachments": [],
        "metadata": {
            "scheduled_job_id": job_id,
            "scheduled_run_id": run.id,
            "interaction_mode": str(getattr(job, "interaction_mode", "") or "expert"),
            "selected_specialist": str(getattr(job, "specialist", "") or "generalist"),
            "scheduled_mode": mode,
            "scheduled_proactive": True,
        },
        "interaction_mode": str(getattr(job, "interaction_mode", "") or "expert"),
        "requested_specialist": str(getattr(job, "specialist", "") or "generalist"),
        "selected_specialist": str(getattr(job, "specialist", "") or "generalist"),
        "job_id": job_id,
        "run_id_scheduled": run.id,
        "delivery": delivery,
        "resolved_channel": resolved.channel,
        "resolved_chat_id": resolved.external_chat_id,
        "resolved_account_id": resolved.account_id,
    }
    worker_id = ensure_worker_started(store=store)
    task = store.oclaw_task_create(
        tenant_id=tenant_id,
        session_id=resolved.session_id,
        task_type="scheduled_turn",
        payload=payload,
    )
    store.scheduled_job_run_update(
        run_id=run.id,
        tenant_id=tenant_id,
        patch={
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "session_id": resolved.session_id,
            "oclaw_task_id": task.id,
            "run_id": agent_run_id,
        },
    )
    store.scheduled_job_reserve_next_run(job_id=job_id, tenant_id=tenant_id)
    pause_after = str(getattr(job, "schedule_kind", "") or "") == "once"
    return {
        "ok": True,
        "run_id": run.id,
        "task_id": task.id,
        "worker_id": worker_id,
        "pause_after": pause_after,
    }


def scheduler_tick(store: Any) -> dict[str, Any]:
    due = store.scheduled_job_list_due(limit=20)
    triggered = 0
    errors: list[str] = []
    for job in due:
        try:
            out = enqueue_scheduled_job_run(store, job=job, mode="scheduled")
            if out.get("ok"):
                triggered += 1
            else:
                errors.append(str(out.get("error") or "enqueue_failed"))
        except Exception as exc:
            errors.append(f"{getattr(job, 'id', '')}: {type(exc).__name__}: {exc}")
    return {"ok": True, "due": len(due), "triggered": triggered, "errors": errors}


def run_scheduled_job_now(store: Any, *, tenant_id: str, job_id: str) -> dict[str, Any]:
    job = store.scheduled_job_get(job_id=job_id, tenant_id=tenant_id)
    if not job:
        return {"ok": False, "error": "job_not_found"}
    if str(job.status or "") != "active":
        return {"ok": False, "error": "job_not_active"}
    return enqueue_scheduled_job_run(store, job=job, mode="manual")


def _scheduler_loop(*, store: Any) -> None:
    global _RUNNING
    interval = _tick_interval_seconds()
    while _RUNNING:
        try:
            scheduler_tick(store)
        except Exception:
            pass
        time.sleep(interval)


def ensure_scheduler_started(*, store: Any) -> str:
    global _THREAD, _RUNNING
    with _LOCK:
        if _THREAD and _THREAD.is_alive():
            return _THREAD.name
        _RUNNING = True
        tid = f"oclaw-scheduler-{uuid.uuid4().hex[:8]}"
        t = threading.Thread(target=_scheduler_loop, kwargs={"store": store}, name=tid, daemon=True)
        t.start()
        _THREAD = t
        return tid


__all__ = [
    "ensure_scheduler_started",
    "enqueue_scheduled_job_run",
    "run_scheduled_job_now",
    "scheduler_tick",
]
