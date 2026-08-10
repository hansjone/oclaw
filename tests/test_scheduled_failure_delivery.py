from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime.extensions.whatsapp.access_control import denied_reply_text
from runtime.scheduler.turn_text import (
    format_scheduled_failure_summary,
    format_scheduled_success_summary,
    format_scheduled_user_reminder,
)
from runtime.scheduler.worker_turn import finalize_scheduled_turn_failure, finalize_scheduled_turn_success
from svc.persistence.sqlite_store import SqliteStore


class ScheduledFailureTextTests(unittest.TestCase):
    def test_failure_summary_english_default(self) -> None:
        text = format_scheduled_failure_summary(
            job_name="License daily",
            error='TimeoutError: CLI timed out after 60s',
            lang="en",
        )
        self.assertIn("[Scheduled job failed]", text)
        self.assertIn("License daily", text)
        self.assertIn("TimeoutError", text)
        self.assertNotIn("定时", text)

    def test_success_summary_wraps_body_and_attachments(self) -> None:
        text = format_scheduled_success_summary(
            job_name="Bandwidth watch",
            reply_text="Critical: 3\nMajor: 1",
            attachment_count=1,
            lang="en",
        )
        self.assertIn("[Scheduled job done]", text)
        self.assertIn("Bandwidth watch", text)
        self.assertIn("Attachments: 1", text)
        self.assertIn("Critical: 3", text)

    def test_reminder_fallback_english(self) -> None:
        self.assertIn("Reminder", format_scheduled_user_reminder("stretch", lang="en"))
        self.assertIn("提醒", format_scheduled_user_reminder("活动一下", lang="zh"))


class DeniedPendingTextTests(unittest.TestCase):
    def test_denied_includes_pending_id_english(self) -> None:
        text = denied_reply_text(lang="en", pending_id="pend-1")
        self.assertIn("Access pending", text)
        self.assertIn("pend-1", text)
        self.assertIn("YES", text)


class ScheduledFailureDeliveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "fail.sqlite"
        self.store = SqliteStore(str(self.db))
        tenant = self.store.create_tenant("Team")
        self.tenant_id = str(tenant["id"])
        user = self.store.create_user(tenant_id=self.tenant_id, display_name="ops", role="administrator")
        self.user_id = str(user["id"])

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_finalize_failure_enqueues_whatsapp_summary(self) -> None:
        job = self.store.scheduled_job_create(
            tenant_id=self.tenant_id,
            created_by_user_id=self.user_id,
            name="Bandwidth watch",
            prompt_text="check congestion",
            schedule_kind="cron",
            schedule_expr="0 * * * *",
            lang="en",
            delivery={
                "whatsapp": {
                    "enabled": True,
                    "target_type": "group",
                    "chat_id": "120363011111111111@g.us",
                    "account_id": "wa-default",
                }
            },
            timezone_name="UTC",
            status="active",
        )
        run = self.store.scheduled_job_run_create(
            job_id=str(job.id),
            tenant_id=self.tenant_id,
            scheduled_at="2026-08-10T00:00:00+00:00",
        )
        payload = {
            "tenant_id": self.tenant_id,
            "job_id": str(job.id),
            "run_id_scheduled": str(run.id),
            "lang": "en",
            "resolved_channel": "whatsapp",
            "resolved_chat_id": "120363011111111111@g.us",
            "resolved_account_id": "wa-default",
            "session_id": "",
        }
        finalize_scheduled_turn_failure(
            self.store,
            payload=payload,
            error="RuntimeError: tool boom",
        )
        pending = self.store.list_pending_channel_outbound_messages(
            channel="whatsapp", account_id="wa-default", limit=5
        )
        self.assertEqual(len(pending), 1)
        body = str(pending[0].get("text") or "")
        self.assertIn("[Scheduled job failed]", body)
        self.assertIn("Bandwidth watch", body)
        self.assertIn("tool boom", body)
        updated = self.store.scheduled_job_run_get(run_id=str(run.id), tenant_id=self.tenant_id)
        self.assertEqual(str(getattr(updated, "status", "") or ""), "failed")

    def test_finalize_success_enqueues_wrapped_summary(self) -> None:
        job = self.store.scheduled_job_create(
            tenant_id=self.tenant_id,
            created_by_user_id=self.user_id,
            name="License daily",
            prompt_text="license report",
            schedule_kind="cron",
            schedule_expr="0 11 * * *",
            lang="en",
            delivery={
                "whatsapp": {
                    "enabled": True,
                    "target_type": "group",
                    "chat_id": "120363011111111111@g.us",
                    "account_id": "wa-default",
                }
            },
            timezone_name="UTC",
            status="active",
        )
        run = self.store.scheduled_job_run_create(
            job_id=str(job.id),
            tenant_id=self.tenant_id,
            scheduled_at="2026-08-10T00:00:00+00:00",
        )
        payload = {
            "tenant_id": self.tenant_id,
            "job_id": str(job.id),
            "run_id_scheduled": str(run.id),
            "lang": "en",
            "resolved_channel": "whatsapp",
            "resolved_chat_id": "120363011111111111@g.us",
            "resolved_account_id": "wa-default",
            "session_id": "",
        }
        finalize_scheduled_turn_success(
            self.store,
            task=None,
            payload=payload,
            base_result={"reply_text": "Found 2 license alarms.", "turn_uuid": "tu1"},
        )
        pending = self.store.list_pending_channel_outbound_messages(
            channel="whatsapp", account_id="wa-default", limit=5
        )
        self.assertEqual(len(pending), 1)
        body = str(pending[0].get("text") or "")
        self.assertIn("[Scheduled job done]", body)
        self.assertIn("License daily", body)
        self.assertIn("Found 2 license alarms.", body)


if __name__ == "__main__":
    unittest.main()
