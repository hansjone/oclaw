from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from runtime.tools.context_inject import enrich_tool_arguments
from runtime.tools.experts.productivity.schedule_tools import schedule_create_tool
from svc.persistence.assistant_store import reset_assistant_store_singleton
from svc.persistence.sqlite_store import SqliteStore


class ToolContextInjectTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "ctx.sqlite"
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
        sess = self.store.create_session_for_user(
            title="wx",
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )
        self.session_id = str(sess.id)
        self.store.ensure_ui_session_owner(
            session_id=self.session_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )

    def tearDown(self) -> None:
        reset_assistant_store_singleton()
        self._tmp.cleanup()

    def test_enrich_from_session_owner(self) -> None:
        out = enrich_tool_arguments(
            store=self.store,
            session_id=self.session_id,
            tool_name="schedule_create",
            arguments={"name": "x"},
        )
        self.assertEqual(out.get("tenant_id"), self.tenant_id)
        self.assertEqual(out.get("owner_user_id"), self.user_id)
        self.assertEqual(out.get("session_id"), self.session_id)

    def test_schedule_create_strips_llm_user_id(self) -> None:
        tool = schedule_create_tool()
        res = tool.handler(
            {
                "session_id": self.session_id,
                "user_id": "wx_fake_external_id",
                "name": "Rest",
                "prompt_text": "提醒休息",
                "schedule_kind": "interval",
                "schedule_expr": "300",
            }
        )
        self.assertTrue(res.get("ok"), res)

    def test_tool_runtime_filters_user_id_for_schedule_schema(self) -> None:
        from runtime.tools.tool_validation import filter_arguments_to_schema

        tool = schedule_create_tool()
        filtered = filter_arguments_to_schema(
            tool.parameters,
            {
                "user_id": "bad",
                "name": "x",
                "prompt_text": "y",
                "schedule_kind": "interval",
                "schedule_expr": "60",
            },
        )
        self.assertNotIn("user_id", filtered)
        self.assertIn("name", filtered)


if __name__ == "__main__":
    unittest.main()
