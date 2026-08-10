from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from runtime.scheduler.recipe import (
    load_recipe_from_job,
    recipe_has_playbook,
    recipe_is_empty,
    resolve_effective_playbook_recipe,
)
from runtime.scheduler.session_resolver import resolve_scheduled_session, resolve_scheduled_viewer_username
from runtime.scheduler.turn_text import build_scheduled_turn_instruction, format_scheduled_skip_summary
from runtime.worker import ensure_worker_started

_LOCK = threading.Lock()
_THREAD: threading.Thread | None = None
_RUNNING = False

_OVERLAP_ACTIVE_STATUSES = frozenset({"queued", "running"})


def _tick_interval_seconds() -> float:
    import os

    raw = str(os.getenv("AIA_SCHEDULER_TICK_SECONDS") or "30").strip()
    try:
        return max(5.0, min(float(raw), 3600.0))
    except Exception:
        return 30.0


def _overlap_stale_seconds() -> float:
    import os

    raw = str(os.getenv("AIA_SCHEDULER_OVERLAP_STALE_SECONDS") or "10800").strip()
    try:
        return max(600.0, min(float(raw), 86400.0))
    except Exception:
        return 10800.0


def _parse_run_ts(raw: Any) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def _find_blocking_scheduled_run(
    store: Any,
    *,
    job_id: str,
    tenant_id: str,
    exclude_run_id: str = "",
) -> Any | None:
    """Return an active (queued/running) run that should block a new enqueue.

    Stale active runs (older than AIA_SCHEDULER_OVERLAP_STALE_SECONDS) are marked
    failed so a stuck worker cannot block the job forever.
    """
    lister = getattr(store, "scheduled_job_run_list", None)
    if not callable(lister):
        return None
    try:
        rows = lister(job_id=str(job_id), tenant_id=str(tenant_id), limit=12) or []
    except Exception:
        return None
    exclude = str(exclude_run_id or "").strip()
    stale_sec = _overlap_stale_seconds()
    now = datetime.now(timezone.utc)
    for row in rows:
        rid = str(getattr(row, "id", "") or "")
        if exclude and rid == exclude:
            continue
        status = str(getattr(row, "status", "") or "").strip().lower()
        if status not in _OVERLAP_ACTIVE_STATUSES:
            continue
        started = _parse_run_ts(getattr(row, "started_at", None)) or _parse_run_ts(
            getattr(row, "created_at", None)
        )
        age = (now - started).total_seconds() if started is not None else 0.0
        if started is not None and age > stale_sec:
            updater = getattr(store, "scheduled_job_run_update", None)
            if callable(updater):
                try:
                    updater(
                        run_id=rid,
                        tenant_id=str(tenant_id),
                        patch={
                            "status": "failed",
                            "finished_at": now.isoformat(),
                            "error": "stale_running_cleared",
                        },
                    )
                except Exception:
                    pass
            continue
        return row
    return None


def _notify_overlapping_skip(
    store: Any,
    *,
    job: Any,
    overlapping_run_id: str,
    reply_text: str,
) -> dict[str, Any]:
    from runtime.scheduler.channel_delivery import deliver_scheduled_reply

    delivery_json = str(getattr(job, "delivery_json", "") or "{}")
    try:
        return deliver_scheduled_reply(
            store,
            tenant_id=str(getattr(job, "tenant_id", "") or ""),
            reply_text=reply_text,
            delivery_json=delivery_json,
        )
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _skip_overlapping_job_run(
    store: Any,
    *,
    job: Any,
    blocking: Any,
    mode: str,
) -> dict[str, Any]:
    tenant_id = str(getattr(job, "tenant_id", "") or "")
    job_id = str(getattr(job, "id") or "")
    lang = str(getattr(job, "lang", "") or "en")
    overlapping_id = str(getattr(blocking, "id", "") or "")
    summary = format_scheduled_skip_summary(
        job_name=str(getattr(job, "name", "") or ""),
        job_id=job_id,
        overlapping_run_id=overlapping_id,
        lang=lang,
    )
    run = store.scheduled_job_run_create(
        job_id=job_id,
        tenant_id=tenant_id,
        scheduled_at=str(getattr(job, "next_run_at", "") or datetime.now(timezone.utc).isoformat()),
        status="skipped",
    )
    delivery_status = _notify_overlapping_skip(
        store,
        job=job,
        overlapping_run_id=overlapping_id,
        reply_text=summary,
    )
    store.scheduled_job_run_update(
        run_id=run.id,
        tenant_id=tenant_id,
        patch={
            "status": "skipped",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "reply_text": summary,
            "error": "overlapping_run",
            "delivery_status": delivery_status,
        },
    )
    # Advance the schedule so the tick does not re-fire every 30s while blocked.
    if str(mode or "") == "scheduled":
        try:
            store.scheduled_job_reserve_next_run(job_id=job_id, tenant_id=tenant_id)
        except Exception:
            pass
    store.scheduled_job_mark_run(
        job_id=job_id,
        tenant_id=tenant_id,
        last_run_status="skipped",
        pause_after=False,
    )
    return {
        "ok": True,
        "skipped": True,
        "reason": "overlapping_run",
        "run_id": run.id,
        "overlapping_run_id": overlapping_id,
        "reply_text": summary,
    }


def _load_previous_run_context(
    store: Any,
    *,
    job_id: str,
    tenant_id: str,
    current_run_id: str = "",
) -> dict[str, Any] | None:
    """Latest finished run for this job (excluding the run currently being queued)."""
    lister = getattr(store, "scheduled_job_run_list", None)
    if not callable(lister):
        return None
    try:
        rows = lister(job_id=str(job_id), tenant_id=str(tenant_id), limit=8) or []
    except Exception:
        return None
    cur = str(current_run_id or "").strip()
    for row in rows:
        rid = str(getattr(row, "id", "") or "")
        if cur and rid == cur:
            continue
        status = str(getattr(row, "status", "") or "").strip().lower()
        if status in {"queued", "running", ""}:
            continue
        return {
            "id": rid,
            "status": status,
            "finished_at": str(getattr(row, "finished_at", "") or "") or None,
            "created_at": str(getattr(row, "created_at", "") or "") or None,
            "reply_text": str(getattr(row, "reply_text", "") or ""),
            "error": str(getattr(row, "error", "") or ""),
        }
    return None


def _maybe_backfill_job_recipe(
    store: Any,
    *,
    job: Any,
    recipe: dict[str, Any],
) -> None:
    """Persist synthesized recipe onto jobs that only stored a long prompt_text."""
    if not recipe_has_playbook(recipe):
        return
    if not recipe_is_empty(load_recipe_from_job(job)):
        return
    updater = getattr(store, "scheduled_job_update", None)
    if not callable(updater):
        return
    try:
        stamped = dict(recipe)
        src = dict(stamped.get("source") or {})
        if not str(src.get("compiled_at") or "").strip():
            src["compiled_at"] = datetime.now(timezone.utc).isoformat()
        src["compiled_from"] = str(src.get("compiled_from") or "prompt_text")
        stamped["source"] = src
        updater(
            job_id=str(getattr(job, "id") or ""),
            tenant_id=str(getattr(job, "tenant_id") or ""),
            patch={"recipe": stamped},
        )
    except Exception:
        pass


def enqueue_scheduled_job_run(
    store: Any,
    *,
    job: Any,
    mode: str = "scheduled",
    force_overlap: bool = False,
) -> dict[str, Any]:
    tenant_id = str(getattr(job, "tenant_id", "") or "")
    job_id = str(getattr(job, "id") or "")
    if not force_overlap:
        blocking = _find_blocking_scheduled_run(store, job_id=job_id, tenant_id=tenant_id)
        if blocking is not None:
            return _skip_overlapping_job_run(
                store,
                job=job,
                blocking=blocking,
                mode=mode,
            )
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
    lang = str(getattr(job, "lang", "") or "en")
    stored_recipe = load_recipe_from_job(job)
    recipe = resolve_effective_playbook_recipe(
        recipe=stored_recipe,
        prompt_text=prompt_text,
        session_id=str(getattr(job, "source_session_id", "") or ""),
    )
    playbook = recipe_has_playbook(recipe)
    if playbook and recipe is not None:
        _maybe_backfill_job_recipe(store, job=job, recipe=recipe)
    previous_run = _load_previous_run_context(
        store,
        job_id=job_id,
        tenant_id=tenant_id,
        current_run_id=str(getattr(run, "id", "") or ""),
    )
    user_text = build_scheduled_turn_instruction(
        prompt_text=prompt_text,
        mode=mode,
        lang=lang,
        recipe=recipe if playbook else None,
        previous_run=previous_run,
    )
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
        "source_session_id": str(resolved.source_session_id or getattr(job, "source_session_id", "") or ""),
        "tenant_id": tenant_id,
        "user_id": resolved.user_id,
        "viewer_username": viewer_username,
        "role": "member",
        "channel": resolved.channel if resolved.channel != "admin_chat" else "admin_chat",
        "lang": lang,
        "text": user_text,
        "prompt_text": prompt_text,
        "recipe": recipe if playbook else {},
        "previous_run": previous_run or {},
        "attachments": [],
        "metadata": {
            "scheduled_job_id": job_id,
            "scheduled_run_id": run.id,
            "interaction_mode": str(getattr(job, "interaction_mode", "") or "expert"),
            "selected_specialist": str(getattr(job, "specialist", "") or "generalist"),
            "scheduled_mode": mode,
            "scheduled_proactive": True,
            "scheduled_playbook": playbook,
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
    skipped = 0
    errors: list[str] = []
    for job in due:
        try:
            out = enqueue_scheduled_job_run(store, job=job, mode="scheduled")
            if out.get("skipped"):
                skipped += 1
            elif out.get("ok"):
                triggered += 1
            else:
                errors.append(str(out.get("error") or "enqueue_failed"))
        except Exception as exc:
            errors.append(f"{getattr(job, 'id', '')}: {type(exc).__name__}: {exc}")
    return {
        "ok": True,
        "due": len(due),
        "triggered": triggered,
        "skipped": skipped,
        "errors": errors,
    }


def run_scheduled_job_now(
    store: Any,
    *,
    tenant_id: str,
    job_id: str,
    force_overlap: bool = False,
) -> dict[str, Any]:
    job = store.scheduled_job_get(job_id=job_id, tenant_id=tenant_id)
    if not job:
        return {"ok": False, "error": "job_not_found"}
    if str(job.status or "") != "active":
        return {"ok": False, "error": "job_not_active"}
    return enqueue_scheduled_job_run(
        store,
        job=job,
        mode="manual",
        force_overlap=force_overlap,
    )


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
