from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from runtime.chat.tool_runtime import ToolExecutionContext, ToolExecutor
from runtime.tools.experts.productivity.schedule_tools import schedule_create_tool
from runtime.tools.base import ToolRegistry
from svc.llm.transports.base import LLMToolCall
from svc.persistence.assistant_store import reset_assistant_store_singleton
from svc.persistence.sqlite_store import SqliteStore


class ToolRuntimeScheduleValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "rt.sqlite"
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

    def test_execute_schedule_create_with_hallucinated_user_id(self) -> None:
        reg = ToolRegistry([schedule_create_tool()])
        ex = ToolExecutor()
        ctx = ToolExecutionContext(
            store=self.store,
            tools=reg,
            session_id=self.session_id,
            path_policy_tenant_id=self.tenant_id,
            path_policy_user_id=self.user_id,
        )
        tc = LLMToolCall(
            id="call1",
            name="schedule_create",
            arguments={
                "user_id": "wechat_external_123",
                "name": "Break",
                "prompt_text": "Stand up",
                "schedule_kind": "interval",
                "schedule_expr": "300",
            },
        )
        result, _dur = ex._execute_tool(ctx, tc)
        self.assertTrue(result.get("ok"), result)


if __name__ == "__main__":
    unittest.main()
