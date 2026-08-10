from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from runtime.scheduler.service import enqueue_scheduled_job_run
from svc.persistence.assistant_store import reset_assistant_store_singleton
from svc.persistence.sqlite_store import SqliteStore


class EnqueuePlaybookBackfillTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "enqueue.sqlite"
        os.environ["OPS_ASSISTANT_DB_PATH"] = str(self.db)
        os.environ["AIA_ASSISTANT_DB_BACKEND"] = "sqlite"
        reset_assistant_store_singleton()
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
        reset_assistant_store_singleton()
        self._tmp.cleanup()

    def test_enqueue_synthesizes_recipe_and_injects_previous_run(self) -> None:
        prompt = (
            "Hourly dying-gasp check.\n\n"
            "Step 1 — Query BN EMS failures.\n"
            "Step 2 — Query remote dying gasp.\n"
            "Step 3 — Correlate and report.\n"
        )
        job = self.store.scheduled_job_create(
            tenant_id=self.tenant_id,
            name="dying-gasp",
            prompt_text=prompt,
            schedule_kind="interval",
            schedule_expr="3600",
            timezone_name="UTC",
            lang="en",
            delivery={"channel": "admin_chat"},
            recipe={},
            created_by_user_id=self.user_id,
        )
        prev = self.store.scheduled_job_run_create(
            job_id=job.id,
            tenant_id=self.tenant_id,
            status="queued",
        )
        self.store.scheduled_job_run_update(
            run_id=prev.id,
            tenant_id=self.tenant_id,
            patch={
                "status": "success",
                "reply_text": "Prior: 4 unmanaged NEs.",
                "finished_at": "2026-08-10T06:00:00+00:00",
            },
        )

        captured: dict[str, object] = {}

        def _capture_create(**kwargs: object) -> MagicMock:
            captured.update(kwargs)
            return MagicMock(id="task-1")

        self.store.oclaw_task_create = _capture_create  # type: ignore[method-assign]

        from runtime.scheduler import service as sched_service
        from runtime.scheduler.session_resolver import ResolvedSession

        resolved = ResolvedSession(
            session_id="sess-sched-1",
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            channel="admin_chat",
            account_id="",
            external_chat_id="",
            external_user_id="",
            is_group=False,
        )
        original_resolve = sched_service.resolve_scheduled_session
        original_worker = sched_service.ensure_worker_started
        try:
            sched_service.resolve_scheduled_session = MagicMock(return_value=resolved)
            sched_service.ensure_worker_started = MagicMock(return_value="worker-1")
            out = enqueue_scheduled_job_run(self.store, job=job, mode="scheduled")
        finally:
            sched_service.resolve_scheduled_session = original_resolve
            sched_service.ensure_worker_started = original_worker

        self.assertTrue(out.get("ok"), out)
        payload = captured.get("payload")
        self.assertIsInstance(payload, dict)
        assert isinstance(payload, dict)
        self.assertTrue((payload.get("metadata") or {}).get("scheduled_playbook"))
        text = str(payload.get("text") or "")
        self.assertIn("Scheduled playbook", text)
        self.assertIn("Previous run context", text)
        self.assertIn("4 unmanaged", text)

        refreshed = self.store.scheduled_job_get(job_id=job.id, tenant_id=self.tenant_id)
        assert refreshed is not None
        self.assertIn("Query BN EMS", refreshed.recipe_json)
        self.assertIn("compiled_from", refreshed.recipe_json)


if __name__ == "__main__":
    unittest.main()
