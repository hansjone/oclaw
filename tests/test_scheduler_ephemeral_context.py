from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from runtime.scheduler.worker_turn import resolve_scheduled_outbound_text
from svc.persistence.sqlite_store import SqliteStore


class EphemeralUserContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "ctx.sqlite"
        os.environ["OPS_ASSISTANT_DB_PATH"] = str(self.db)
        self.store = SqliteStore(str(self.db))
        sess = self.store.create_session("test")
        self.session_id = str(sess.id)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_build_model_context_injects_ephemeral_user_text(self) -> None:
        from runtime.direct_loop import _build_model_context
        from svc.llm.chat_models import RuleBasedChatModel

        msgs = _build_model_context(
            store=self.store,
            session_id=self.session_id,
            max_messages=20,
            system_prompt="sys",
            model=RuleBasedChatModel(),
            lang="zh",
            memory_context=None,
            trace_id=None,
            parent_span_id=None,
            user_text="【定时主动提醒】站起来",
            active_turn_uuid="turn-sched-1",
        )
        roles = [str(m.get("role") or "") for m in msgs]
        self.assertIn("user", roles)
        self.assertEqual(str(msgs[-1].get("content") or ""), "【定时主动提醒】站起来")
        rows = self.store.get_messages(session_id=self.session_id, limit=10)
        self.assertEqual(len(rows), 0)


class ScheduledOutboundFallbackTests(unittest.TestCase):
    def test_uses_prompt_when_model_reply_empty(self) -> None:
        text = resolve_scheduled_outbound_text(
            payload={"prompt_text": "站起来活动一下"},
            reply_text="",
        )
        self.assertIn("站起来活动一下", text)
        self.assertTrue(text.startswith("⏰"))

    def test_keeps_model_reply_when_present(self) -> None:
        text = resolve_scheduled_outbound_text(
            payload={"prompt_text": "站起来活动一下"},
            reply_text="该起来啦！",
        )
        self.assertEqual(text, "该起来啦！")


class ScheduledAssistantPersistTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "persist.sqlite"
        os.environ["OPS_ASSISTANT_DB_PATH"] = str(self.db)
        self.store = SqliteStore(str(self.db))
        sess = self.store.create_session("sched")
        self.session_id = str(sess.id)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_finalize_persists_assistant_when_missing(self) -> None:
        from runtime.scheduler.worker_turn import finalize_scheduled_turn_success

        task = MagicMock()
        task.task_type = "scheduled_turn"
        payload = {
            "tenant_id": "t1",
            "job_id": "",
            "run_id_scheduled": "",
            "session_id": self.session_id,
            "prompt_text": "休息",
            "delivery": {"weixin": {"enabled": False}},
            "resolved_channel": "admin_chat",
        }
        with unittest.mock.patch(
            "runtime.scheduler.channel_delivery.deliver_scheduled_reply",
            return_value={"ok": True, "skipped": True},
        ):
            finalize_scheduled_turn_success(
                store=self.store,
                task=task,
                payload={
                    **payload,
                    "session_id": self.session_id,
                },
                base_result={"reply_text": "", "turn_uuid": "tu-1"},
            )
        rows = self.store.get_messages(session_id=self.session_id, limit=10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(str(rows[0].role), "assistant")
        self.assertEqual(str(getattr(rows[0], "event_type", "") or ""), "assistant_text")
        self.assertIn("休息", str(rows[0].content or ""))

    def test_updates_empty_assistant_for_same_turn(self) -> None:
        from runtime.scheduler.worker_turn import _persist_scheduled_assistant_reply

        self.store.add_message(
            session_id=self.session_id,
            role="assistant",
            content="",
            turn_uuid="tu-empty",
            event_type="assistant_text",
        )
        _persist_scheduled_assistant_reply(
            self.store,
            session_id=self.session_id,
            turn_uuid="tu-empty",
            reply_text="⏰ 提醒：站起来",
        )
        rows = self.store.get_messages(session_id=self.session_id, limit=10)
        self.assertEqual(len(rows), 1)
        self.assertIn("站起来", str(rows[0].content or ""))


if __name__ == "__main__":
    unittest.main()
