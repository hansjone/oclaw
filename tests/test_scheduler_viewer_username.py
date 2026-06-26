from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from runtime.scheduler.session_resolver import resolve_scheduled_viewer_username
from runtime.scheduler.service import enqueue_scheduled_job_run
from svc.persistence.sqlite_store import SqliteStore


class ResolveScheduledViewerUsernameTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "sched.sqlite"
        os.environ["OPS_ASSISTANT_DB_PATH"] = str(self.db)
        self.store = SqliteStore(str(self.db))
        t = self.store.create_tenant("Team")
        self.tenant_id = str(t["id"])
        self.admin = self.store.create_user_account(
            tenant_id=self.tenant_id,
            username="administrator",
            display_name="Admin",
            role="owner",
            password_hash="x",
            is_active=True,
        )
        self.member = self.store.create_user_account(
            tenant_id=self.tenant_id,
            username="alice",
            display_name="Alice",
            role="member",
            password_hash="x",
            is_active=True,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_weixin_uses_administrator_pool(self) -> None:
        uname = resolve_scheduled_viewer_username(
            self.store,
            tenant_id=self.tenant_id,
            user_id=str(self.member["id"]),
            channel="weixin",
        )
        self.assertEqual(uname, "administrator")

    def test_admin_chat_uses_job_owner_username(self) -> None:
        uname = resolve_scheduled_viewer_username(
            self.store,
            tenant_id=self.tenant_id,
            user_id=str(self.member["id"]),
            channel="admin_chat",
        )
        self.assertEqual(uname, "alice")

    def test_enqueue_payload_includes_viewer_username_for_weixin(self) -> None:
        job = MagicMock()
        job.tenant_id = self.tenant_id
        job.id = "job-weixin"
        job.next_run_at = "2026-06-26T10:00:00+00:00"
        job.delivery_json = '{"weixin":{"enabled":true}}'
        job.prompt_text = "stretch"
        job.lang = "zh"
        job.interaction_mode = "expert"
        job.specialist = "generalist"
        job.created_by_user_id = str(self.member["id"])
        job.schedule_kind = "interval"

        run = MagicMock()
        run.id = "run-1"
        self.store.scheduled_job_run_create = MagicMock(return_value=run)  # type: ignore[method-assign]
        self.store.scheduled_job_run_update = MagicMock()  # type: ignore[method-assign]
        self.store.scheduled_job_reserve_next_run = MagicMock()  # type: ignore[method-assign]
        captured: dict[str, object] = {}

        def _capture_create(**kwargs: object) -> MagicMock:
            captured.update(kwargs)
            return MagicMock(id="task-1")

        self.store.oclaw_task_create = _capture_create  # type: ignore[method-assign]

        from runtime.scheduler import service as sched_service
        from runtime.scheduler.session_resolver import ResolvedSession

        resolved = ResolvedSession(
            session_id="sess-1",
            tenant_id=self.tenant_id,
            user_id=str(self.admin["id"]),
            channel="weixin",
            account_id="weixin-default",
            external_chat_id="wx-user-1",
            external_user_id="wx-user-1",
            is_group=False,
        )
        original_resolve = sched_service.resolve_scheduled_session
        original_worker = sched_service.ensure_worker_started
        try:
            sched_service.resolve_scheduled_session = MagicMock(return_value=resolved)
            sched_service.ensure_worker_started = MagicMock(return_value="worker-1")
            enqueue_scheduled_job_run(self.store, job=job, mode="scheduled")
        finally:
            sched_service.resolve_scheduled_session = original_resolve
            sched_service.ensure_worker_started = original_worker

        payload = captured.get("payload")
        self.assertIsInstance(payload, dict)
        assert isinstance(payload, dict)
        self.assertEqual(payload.get("viewer_username"), "administrator")


if __name__ == "__main__":
    unittest.main()
