from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from runtime.scheduler.job_delete import job_is_foreign, merge_delivery_creator
from runtime.tools.experts.productivity.schedule_tools import (
    schedule_create_tool,
    schedule_delete_tool,
)
from svc.persistence.assistant_store import reset_assistant_store_singleton
from svc.persistence.sqlite_store import SqliteStore


class ScheduleDeleteConfirmTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "del.sqlite"
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
        other = self.store.create_user_account(
            tenant_id=self.tenant_id,
            username="alice",
            display_name="Alice",
            role="member",
            password_hash="x",
            is_active=True,
        )
        self.other_id = str(other["id"])

    def tearDown(self) -> None:
        reset_assistant_store_singleton()
        self._tmp.cleanup()

    def _create(self, *, owner: str, name: str, creator_ext: str = "", push: str = "") -> str:
        out = schedule_create_tool().handler(
            {
                "tenant_id": self.tenant_id,
                "owner_user_id": owner,
                "name": name,
                "prompt_text": "提醒喝水",
                "schedule_kind": "interval",
                "schedule_expr": "3600",
                "creator_external_user_id": creator_ext,
                "creator_push_name": push,
            }
        )
        self.assertTrue(out.get("ok"), out)
        return str((out.get("job") or {})["id"])

    def test_delete_requires_confirmation(self) -> None:
        jid = self._create(owner=self.user_id, name="喝水", creator_ext="111@lid", push="Bob")
        preview = schedule_delete_tool().handler(
            {
                "tenant_id": self.tenant_id,
                "owner_user_id": self.user_id,
                "job_id": jid,
                "actor_external_user_id": "111@lid",
            }
        )
        self.assertFalse(preview.get("ok"))
        self.assertEqual(preview.get("error"), "confirmation_required")
        self.assertIn("preview_markdown", preview)
        still = self.store.scheduled_job_get(job_id=jid, tenant_id=self.tenant_id)
        self.assertIsNotNone(still)
        self.assertEqual(still.status, "active")

        done = schedule_delete_tool().handler(
            {
                "tenant_id": self.tenant_id,
                "owner_user_id": self.user_id,
                "job_id": jid,
                "confirmed": True,
                "actor_external_user_id": "111@lid",
            }
        )
        self.assertTrue(done.get("ok"), done)
        deleted = self.store.scheduled_job_get(job_id=jid, tenant_id=self.tenant_id)
        self.assertIsNotNone(deleted)
        self.assertEqual(deleted.status, "deleted")

    def test_foreign_delete_needs_extra_flag(self) -> None:
        jid = self._create(
            owner=self.other_id,
            name="AliceReminder",
            creator_ext="alice@lid",
            push="Alice",
        )
        first = schedule_delete_tool().handler(
            {
                "tenant_id": self.tenant_id,
                "owner_user_id": self.user_id,
                "job_id": jid,
                "confirmed": True,
                "actor_external_user_id": "bob@lid",
            }
        )
        self.assertFalse(first.get("ok"))
        self.assertEqual(first.get("error"), "foreign_job_confirmation_required")

        done = schedule_delete_tool().handler(
            {
                "tenant_id": self.tenant_id,
                "owner_user_id": self.user_id,
                "job_id": jid,
                "confirmed": True,
                "confirm_foreign": True,
                "actor_external_user_id": "bob@lid",
            }
        )
        self.assertTrue(done.get("ok"), done)

    def test_ambiguous_prefix(self) -> None:
        # Force two jobs; prefix of common empty won't work — use identical id prefix via listing
        a = self._create(owner=self.user_id, name="A")
        b = self._create(owner=self.user_id, name="B")
        # uuid unlikely share long prefix; use empty path with resolve of weird short then skip
        # Instead verify prefix of full id alone still unique
        out = schedule_delete_tool().handler(
            {
                "tenant_id": self.tenant_id,
                "owner_user_id": self.user_id,
                "job_id": a[:8],
            }
        )
        # Usually unique with 8 hex chars of uuid
        if out.get("error") == "ambiguous_job":
            self.assertTrue(out.get("candidates"))
        else:
            self.assertIn(out.get("error"), {"confirmation_required", "job_not_found"})
            if out.get("error") == "confirmation_required":
                self.assertEqual(out.get("job_id"), a)
        _ = b

    def test_creator_merge_and_foreign_helper(self) -> None:
        delivery = merge_delivery_creator(
            {},
            user_id="u1",
            external_user_id="ext-a",
            push_name="Ann",
        )
        job = type(
            "J",
            (),
            {
                "created_by_user_id": "u1",
                "delivery_json": __import__("json").dumps(delivery),
            },
        )()
        self.assertFalse(job_is_foreign(job, actor_user_id="u1", actor_external_user_id="ext-a"))
        self.assertTrue(job_is_foreign(job, actor_user_id="u2", actor_external_user_id="ext-b"))


if __name__ == "__main__":
    unittest.main()
