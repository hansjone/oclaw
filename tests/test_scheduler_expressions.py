from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from runtime.scheduler.expressions import compute_next_run_at, normalize_schedule_kind
from svc.persistence.sqlite_store import SqliteStore


class SchedulerExpressionsTests(unittest.TestCase):
    def test_normalize_schedule_kind(self) -> None:
        self.assertEqual(normalize_schedule_kind("CRON"), "cron")
        self.assertEqual(normalize_schedule_kind("bad"), "cron")

    def test_interval_next_run(self) -> None:
        base = datetime(2026, 6, 26, 10, 0, 0, tzinfo=timezone.utc)
        nxt = compute_next_run_at(
            schedule_kind="interval",
            schedule_expr="120",
            timezone_name="Asia/Shanghai",
            from_dt=base,
        )
        self.assertEqual(nxt, (base + timedelta(seconds=120)).isoformat())

    def test_once_future(self) -> None:
        future = datetime.now(timezone.utc) + timedelta(hours=2)
        nxt = compute_next_run_at(
            schedule_kind="once",
            schedule_expr=future.isoformat(),
            timezone_name="Asia/Shanghai",
        )
        self.assertIsNotNone(nxt)


class ScheduledJobStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "sched.sqlite"
        os.environ["OPS_ASSISTANT_DB_PATH"] = str(self.db)
        self.store = SqliteStore(str(self.db))
        t = self.store.create_tenant("Team")
        self.tenant_id = str(t["id"])
        user = self.store.create_user_account(
            tenant_id=self.tenant_id,
            username="administrator",
            display_name="Admin",
            role="owner",
            password_hash="x",
            is_active=True,
        )
        self.user_id = str(user["id"])

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_row_to_job_dict_row(self) -> None:
        from svc.persistence.scheduled_job_store import _row_to_job

        row = {
            "id": "j1",
            "tenant_id": self.tenant_id,
            "name": "Test",
            "description": "",
            "status": "active",
            "schedule_kind": "interval",
            "schedule_expr": "300",
            "timezone": "Asia/Shanghai",
            "prompt_text": "ping",
            "interaction_mode": "expert",
            "specialist": "generalist",
            "lang": "zh",
            "delivery_json": "{}",
            "source_session_id": None,
            "created_by_user_id": self.user_id,
            "source": "chat",
            "next_run_at": "2026-06-26T10:00:00+00:00",
            "last_run_at": None,
            "last_run_status": "",
            "created_at": "2026-06-26T09:00:00+00:00",
            "updated_at": "2026-06-26T09:00:00+00:00",
        }
        job = _row_to_job(row)
        self.assertEqual(job.id, "j1")
        self.assertEqual(job.name, "Test")
        job = self.store.scheduled_job_create(
            tenant_id=self.tenant_id,
            name="Daily report",
            prompt_text="Summarize alarms",
            schedule_kind="interval",
            schedule_expr="3600",
            created_by_user_id=self.user_id,
        )
        self.assertEqual(job.status, "active")
        self.assertTrue(job.next_run_at)
        rows = self.store.scheduled_job_list(tenant_id=self.tenant_id)
        self.assertEqual(len(rows), 1)
        ok = self.store.scheduled_job_set_status(
            tenant_id=self.tenant_id,
            job_id=job.id,
            status="paused",
        )
        self.assertTrue(ok)
        due = self.store.scheduled_job_list_due(limit=10)
        self.assertEqual(due, [])

    def test_run_record(self) -> None:
        job = self.store.scheduled_job_create(
            tenant_id=self.tenant_id,
            name="Once",
            prompt_text="Ping",
            schedule_kind="once",
            schedule_expr=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
            created_by_user_id=self.user_id,
        )
        run = self.store.scheduled_job_run_create(job_id=job.id, tenant_id=self.tenant_id)
        self.assertEqual(run.status, "queued")
        updated = self.store.scheduled_job_run_update(
            run_id=run.id,
            tenant_id=self.tenant_id,
            patch={"status": "success", "reply_text": "ok"},
        )
        self.assertIsNotNone(updated)
        self.assertEqual(str(updated.reply_text), "ok")


if __name__ == "__main__":
    unittest.main()
