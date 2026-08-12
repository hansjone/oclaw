# -*- coding: utf-8 -*-
"""Tests for scheduled job failure classification + summary."""

from __future__ import annotations

from pathlib import Path

from runtime.scheduler.failure_class import classify_scheduled_job_error, enrich_scheduled_job_run_dict
from svc.persistence.sqlite_store import SqliteStore


def test_classify_scheduled_job_error_classes() -> None:
    assert classify_scheduled_job_error("overlapping_run", status="skipped") == "overlap"
    assert classify_scheduled_job_error("read_timeout after 60s", status="failed") == "timeout"
    assert classify_scheduled_job_error("WhatsApp Connection Closed", status="failed") == "delivery"
    assert classify_scheduled_job_error("insufficient_scope:sql:query", status="failed") == "auth"
    assert classify_scheduled_job_error("Unregistered tool: mcp__netx__x", status="failed") == "mcp"
    assert classify_scheduled_job_error("stale_running_cleared", status="failed") == "stale"
    assert classify_scheduled_job_error("boom", status="failed") == "runtime"
    assert classify_scheduled_job_error("", status="success") == ""


def test_enrich_run_dict_adds_failure_class() -> None:
    out = enrich_scheduled_job_run_dict({"status": "failed", "error": "tool timeout"})
    assert out["failure_class"] == "timeout"


def test_scheduled_job_failure_summary(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "jobs.sqlite"))
    # Ensure tenant user exists if required by store create paths.
    job = store.scheduled_job_create(
        tenant_id="default",
        name="fail-board",
        description="",
        schedule_kind="interval",
        schedule_expr="3600",
        timezone_name="UTC",
        prompt_text="ping",
        specialist="ops",
        lang="en",
        created_by_user_id="u1",
        source="test",
    )
    run_ok = store.scheduled_job_run_create(
        job_id=job.id, tenant_id="default", scheduled_at="2026-08-01T00:00:00+00:00", status="queued"
    )
    store.scheduled_job_run_update(
        run_id=run_ok.id,
        tenant_id="default",
        patch={"status": "success", "finished_at": "2026-08-01T00:01:00+00:00", "error": ""},
    )
    run_fail = store.scheduled_job_run_create(
        job_id=job.id, tenant_id="default", scheduled_at="2026-08-01T01:00:00+00:00", status="queued"
    )
    store.scheduled_job_run_update(
        run_id=run_fail.id,
        tenant_id="default",
        patch={
            "status": "failed",
            "finished_at": "2026-08-01T01:01:00+00:00",
            "error": "read_timeout after 90s",
        },
    )
    store.scheduled_job_mark_run(
        job_id=job.id, tenant_id="default", last_run_status="failed", pause_after=False
    )
    summary = store.scheduled_job_failure_summary(tenant_id="default", recent_limit=50)
    assert summary["recent_failed"] >= 1
    assert summary["recent_success"] >= 1
    assert "timeout" in (summary.get("recent_fail_classes") or {})
    assert any(x.get("id") == job.id for x in summary.get("jobs_last_failed") or [])
    d = store.scheduled_job_run_to_dict(store.scheduled_job_run_get(run_id=run_fail.id, tenant_id="default"))
    assert d.get("failure_class") == "timeout"
