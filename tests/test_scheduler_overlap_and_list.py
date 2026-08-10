from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from runtime.scheduler.service import enqueue_scheduled_job_run
from runtime.scheduler.turn_text import format_scheduled_skip_summary
from runtime.tools.experts.productivity.schedule_tools import schedule_list_tool
from svc.persistence.assistant_store import reset_assistant_store_singleton
from svc.persistence.sqlite_store import SqliteStore


class OverlapSkipTextTests(unittest.TestCase):
    def test_skip_summary_english(self) -> None:
        text = format_scheduled_skip_summary(
            job_name="Hourly congestion",
            overlapping_run_id="abcdef12-3456",
            lang="en",
        )
        self.assertIn("[Scheduled job skipped]", text)
        self.assertIn("overlapping", text)
        self.assertIn("abcdef12-345", text)


class ScheduledOverlapAndListTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "overlap.sqlite"
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

    def _make_job(self, *, recipe: dict | None = None, prompt: str = "remind drink"):
        return self.store.scheduled_job_create(
            tenant_id=self.tenant_id,
            name="job-a",
            prompt_text=prompt,
            schedule_kind="interval",
            schedule_expr="3600",
            timezone_name="UTC",
            lang="en",
            delivery={"whatsapp": {"enabled": True, "target_type": "group", "chat_id": "x@g.us"}},
            recipe=recipe or {},
            created_by_user_id=self.user_id,
        )

    def test_enqueue_skips_when_prior_run_active(self) -> None:
        job = self._make_job()
        active = self.store.scheduled_job_run_create(
            job_id=job.id,
            tenant_id=self.tenant_id,
            status="running",
        )
        self.store.scheduled_job_run_update(
            run_id=active.id,
            tenant_id=self.tenant_id,
            patch={"status": "running", "started_at": "2026-08-10T23:00:00+00:00"},
        )

        with patch(
            "runtime.scheduler.service.deliver_scheduled_reply",
            create=True,
        ):
            # Patch via channel_delivery import path used inside helper.
            with patch(
                "runtime.scheduler.channel_delivery.deliver_scheduled_reply",
                return_value={"ok": True, "channel": "whatsapp"},
            ) as deliver:
                out = enqueue_scheduled_job_run(self.store, job=job, mode="scheduled")

        self.assertTrue(out.get("ok"), out)
        self.assertTrue(out.get("skipped"), out)
        self.assertEqual(out.get("reason"), "overlapping_run")
        self.assertEqual(out.get("overlapping_run_id"), active.id)
        deliver.assert_called_once()
        skipped = self.store.scheduled_job_run_get(run_id=str(out["run_id"]), tenant_id=self.tenant_id)
        assert skipped is not None
        self.assertEqual(skipped.status, "skipped")
        self.assertIn("overlapping", skipped.reply_text.lower())
        refreshed = self.store.scheduled_job_get(job_id=job.id, tenant_id=self.tenant_id)
        assert refreshed is not None
        self.assertEqual(refreshed.last_run_status, "skipped")

    def test_force_overlap_bypasses_skip(self) -> None:
        job = self._make_job()
        active = self.store.scheduled_job_run_create(
            job_id=job.id,
            tenant_id=self.tenant_id,
            status="running",
        )
        self.store.scheduled_job_run_update(
            run_id=active.id,
            tenant_id=self.tenant_id,
            patch={"status": "running", "started_at": "2026-08-10T23:00:00+00:00"},
        )

        from runtime.scheduler import service as sched_service
        from runtime.scheduler.session_resolver import ResolvedSession

        resolved = ResolvedSession(
            session_id="sess-1",
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            channel="admin_chat",
            account_id="",
            external_chat_id="",
            external_user_id="",
            is_group=False,
        )
        self.store.oclaw_task_create = MagicMock(return_value=MagicMock(id="task-1"))  # type: ignore[method-assign]
        original_resolve = sched_service.resolve_scheduled_session
        original_worker = sched_service.ensure_worker_started
        try:
            sched_service.resolve_scheduled_session = MagicMock(return_value=resolved)
            sched_service.ensure_worker_started = MagicMock(return_value="worker-1")
            out = enqueue_scheduled_job_run(self.store, job=job, mode="manual", force_overlap=True)
        finally:
            sched_service.resolve_scheduled_session = original_resolve
            sched_service.ensure_worker_started = original_worker

        self.assertTrue(out.get("ok"), out)
        self.assertFalse(bool(out.get("skipped")))
        self.assertIn("task_id", out)

    def test_schedule_list_exposes_playbook_signals(self) -> None:
        recipe = {
            "goal": "Hourly bandwidth check",
            "steps": ["Query alarms", "Filter areas", "Deliver xlsx"],
            "success_criteria": ["Report sent"],
        }
        self._make_job(recipe=recipe, prompt="Hourly bandwidth check")
        self._make_job(prompt="提醒喝水")

        out = schedule_list_tool().handler(
            {"tenant_id": self.tenant_id, "owner_user_id": self.user_id, "limit": 20}
        )
        self.assertTrue(out.get("ok"), out)
        items = out.get("items") or []
        self.assertGreaterEqual(len(items), 2)
        playbook_items = [i for i in items if i.get("playbook")]
        self.assertTrue(playbook_items)
        hit = playbook_items[0]
        self.assertEqual(hit.get("steps_n"), 3)
        self.assertIn("Hourly bandwidth", str(hit.get("recipe_goal") or ""))
        self.assertNotIn("recipe", hit)

        reminder = next(i for i in items if not i.get("playbook") and not i.get("has_recipe"))
        self.assertEqual(int(reminder.get("steps_n") or 0), 0)

    def test_job_to_dict_includes_summary(self) -> None:
        job = self._make_job(
            recipe={
                "goal": "License report",
                "steps": ["Query", "Attach"],
                "success_criteria": ["Done"],
            },
            prompt="License report",
        )
        d = self.store.scheduled_job_to_dict(job)
        self.assertTrue(d.get("playbook"))
        self.assertEqual(d.get("steps_n"), 2)
        self.assertTrue(d.get("has_recipe"))
        self.assertIn("License", str(d.get("recipe_goal") or ""))


if __name__ == "__main__":
    unittest.main()
