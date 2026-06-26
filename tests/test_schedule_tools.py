from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from runtime.tools.experts.productivity.schedule_tools import schedule_create_tool, schedule_list_tool
from svc.persistence.assistant_store import reset_assistant_store_singleton
from svc.persistence.sqlite_store import SqliteStore


class ScheduleToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "tools.sqlite"
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

    def test_schedule_create_and_list(self) -> None:
        create = schedule_create_tool()
        out = create.handler(
            {
                "tenant_id": self.tenant_id,
                "owner_user_id": self.user_id,
                "name": "Reminder",
                "prompt_text": "Check inbox",
                "schedule_kind": "interval",
                "schedule_expr": "900",
                "specialist": "ops",
                "interaction_mode": "expert",
            }
        )
        self.assertTrue(out.get("ok"), out)
        lst = schedule_list_tool()
        listed = lst.handler({"tenant_id": self.tenant_id})
        self.assertTrue(listed.get("ok"))
        self.assertEqual(len(listed.get("items") or []), 1)


if __name__ == "__main__":
    unittest.main()
