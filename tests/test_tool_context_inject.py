from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from runtime.tools.context_inject import enrich_tool_arguments
from runtime.tools.experts.productivity.schedule_tools import schedule_create_tool
from runtime.chat.tool_runtime import ToolExecutionContext, ToolExecutor
from runtime.tools.base import ToolRegistry, ToolSpec
from svc.llm.transports.base import LLMToolCall
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

    def test_schedule_create_inherits_executor_specialist_when_missing(self) -> None:
        # Tool args from the model commonly omit "specialist". In that case, schedule_create should
        # receive selected_specialist inherited from executor context (ops/generalist/...).
        seen: dict[str, object] = {}

        def _capture(args: dict[str, object]) -> dict[str, object]:
            seen.update(args)
            return {"ok": True}

        fake_schedule_create = ToolSpec(
            name="schedule_create",
            description="capture args",
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "prompt_text": {"type": "string"},
                    "schedule_kind": {"type": "string"},
                    "schedule_expr": {"type": "string"},
                    "selected_specialist": {"type": "string"},
                },
                "required": ["name", "prompt_text", "schedule_kind", "schedule_expr"],
                "additionalProperties": True,
            },
            handler=_capture,
        )

        self.store.add_message(
            session_id=self.session_id,
            role="assistant",
            content="hi",
            event_type="assistant_text",
            turn_uuid="t0",
        )
        assistant_msg_id = int(self.store.get_messages(session_id=self.session_id, limit=1)[0].id)

        ctx = ToolExecutionContext(
            store=self.store,
            tools=ToolRegistry([fake_schedule_create]),
            session_id=self.session_id,
            lang="en",
            specialist="ops",
            turn_uuid="turn-1",
        )
        tc = LLMToolCall(
            id="tc1",
            name="schedule_create",
            arguments={
                "name": "drink water",
                "prompt_text": "drink water",
                "schedule_kind": "interval",
                "schedule_expr": "300",
            },
        )

        tool_msgs, _ = ToolExecutor().execute_tool_uses(ctx=ctx, assistant_msg_id=assistant_msg_id, tool_uses=[tc])
        self.assertEqual(len(tool_msgs), 1)
        self.assertEqual(str(seen.get("selected_specialist") or ""), "ops")

    def test_schedule_create_inherits_workspace_lane_role_when_specialist_internal(self) -> None:
        seen: dict[str, object] = {}

        def _capture(args: dict[str, object]) -> dict[str, object]:
            seen.update(args)
            return {"ok": True}

        fake_schedule_create = ToolSpec(
            name="schedule_create",
            description="capture args",
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "prompt_text": {"type": "string"},
                    "schedule_kind": {"type": "string"},
                    "schedule_expr": {"type": "string"},
                    "selected_specialist": {"type": "string"},
                },
                "required": ["name", "prompt_text", "schedule_kind", "schedule_expr"],
                "additionalProperties": True,
            },
            handler=_capture,
        )

        self.store.add_message(
            session_id=self.session_id,
            role="assistant",
            content="hi",
            event_type="assistant_text",
            turn_uuid="t0",
        )
        assistant_msg_id = int(self.store.get_messages(session_id=self.session_id, limit=1)[0].id)

        ctx = ToolExecutionContext(
            store=self.store,
            tools=ToolRegistry([fake_schedule_create]),
            session_id=self.session_id,
            lang="en",
            specialist="oclaw",
            workspace_lane_role="ops",
            turn_uuid="turn-1",
        )
        tc = LLMToolCall(
            id="tc2",
            name="schedule_create",
            arguments={
                "name": "daily report",
                "prompt_text": "send report",
                "schedule_kind": "cron",
                "schedule_expr": "0 9 * * *",
            },
        )

        tool_msgs, _ = ToolExecutor().execute_tool_uses(ctx=ctx, assistant_msg_id=assistant_msg_id, tool_uses=[tc])
        self.assertEqual(len(tool_msgs), 1)
        self.assertEqual(str(seen.get("selected_specialist") or ""), "ops")


if __name__ == "__main__":
    unittest.main()
