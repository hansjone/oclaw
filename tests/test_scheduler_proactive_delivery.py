from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from runtime.scheduler.channel_delivery import deliver_scheduled_reply
from runtime.scheduler.cron_service import build_delivery_for_session
from runtime.scheduler.session_resolver import resolve_scheduled_session
from runtime.scheduler.turn_text import build_scheduled_turn_instruction
from svc.persistence.sqlite_store import SqliteStore


class ScheduledTurnTextTests(unittest.TestCase):
    def test_instruction_is_internal_not_user_facing(self) -> None:
        text = build_scheduled_turn_instruction(
            prompt_text="站起来活动一下",
            mode="scheduled",
            lang="zh",
        )
        self.assertIn("提醒意图", text)
        self.assertNotIn("[scheduled:", text)


class ScheduledSessionResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "sched.sqlite"
        os.environ["OPS_ASSISTANT_DB_PATH"] = str(self.db)
        self.store = SqliteStore(str(self.db))
        t = self.store.create_tenant("Team")
        self.tenant_id = str(t["id"])
        admin = self.store.create_user_account(
            tenant_id=self.tenant_id,
            username="administrator",
            display_name="Admin",
            role="owner",
            password_hash="x",
            is_active=True,
        )
        self.admin_id = str(admin["id"])
        sess = self.store.create_session("WeChat session")
        self.session_id = str(sess.id)
        self.store.ensure_ui_session_owner(
            session_id=self.session_id,
            tenant_id=self.tenant_id,
            user_id=self.admin_id,
        )
        with self.store._connect() as conn:
            conn.execute(
                """
                INSERT INTO channel_session_v2
                    (tenant_id, channel, account_id, external_chat_id, external_user_id, session_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (self.tenant_id, "weixin", "weixin-default", "wx-user-123", "wx-user-123", self.session_id),
            )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_source_session_preserves_weixin_delivery_target(self) -> None:
        job = MagicMock()
        job.tenant_id = self.tenant_id
        job.delivery_json = '{"weixin":{"enabled":true}}'
        job.source_session_id = self.session_id
        job.name = "rest"
        resolved = resolve_scheduled_session(store=self.store, job=job, created_by_user_id=self.admin_id)
        self.assertEqual(resolved.channel, "weixin")
        self.assertEqual(resolved.external_chat_id, "wx-user-123")


class ScheduledDeliveryChannelTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "sched.sqlite"
        os.environ["OPS_ASSISTANT_DB_PATH"] = str(self.db)
        self.store = SqliteStore(str(self.db))
        t = self.store.create_tenant("Team")
        self.tenant_id = str(t["id"])

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_whatsapp_session_disables_weixin_delivery(self) -> None:
        sess = self.store.create_session("WA session")
        session_id = str(sess.id)
        with self.store._connect() as conn:
            conn.execute(
                """
                INSERT INTO channel_session_v2
                    (tenant_id, channel, account_id, external_chat_id, external_user_id, session_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (self.tenant_id, "whatsapp", "wa-default", "15551234567@s.whatsapp.net", "15551234567", session_id),
            )
        delivery = build_delivery_for_session(
            self.store,
            tenant_id=self.tenant_id,
            session_id=session_id,
        )
        self.assertTrue(delivery["whatsapp"]["enabled"])
        self.assertEqual(delivery["whatsapp"]["chat_id"], "15551234567@s.whatsapp.net")
        self.assertFalse(delivery["weixin"]["enabled"])

    def test_weixin_session_disables_whatsapp_delivery(self) -> None:
        sess = self.store.create_session("WX session")
        session_id = str(sess.id)
        with self.store._connect() as conn:
            conn.execute(
                """
                INSERT INTO channel_session_v2
                    (tenant_id, channel, account_id, external_chat_id, external_user_id, session_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (self.tenant_id, "weixin", "weixin-default", "wx-user-9", "wx-user-9", session_id),
            )
        delivery = build_delivery_for_session(
            self.store,
            tenant_id=self.tenant_id,
            session_id=session_id,
        )
        self.assertTrue(delivery["weixin"]["enabled"])
        self.assertFalse(delivery["whatsapp"]["enabled"])


class ScheduledDeliveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "sched.sqlite"
        os.environ["OPS_ASSISTANT_DB_PATH"] = str(self.db)
        self.store = SqliteStore(str(self.db))
        t = self.store.create_tenant("Team")
        self.tenant_id = str(t["id"])

    def tearDown(self) -> None:
        self._tmp.cleanup()

    @patch("runtime.scheduler.channel_delivery.enqueue_weixin_reply")
    def test_deliver_uses_stored_context_token(self, mock_enqueue: MagicMock) -> None:
        mock_enqueue.return_value = {"ok": True, "channel": "wechat", "queued": True}
        self.store.set_channel_context_token(
            tenant_id=self.tenant_id,
            channel="wechat",
            account_id="real-acct",
            external_chat_id="wx-user-123",
            context_token="ctx-abc",
        )
        sess = self.store.create_session("wx-deliver")
        session_id = str(sess.id)
        with self.store._connect() as conn:
            conn.execute(
                """
                INSERT INTO channel_session_v2
                    (tenant_id, channel, account_id, external_chat_id, external_user_id, session_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (self.tenant_id, "wechat", "real-acct", "wx-user-123", "wx-user-123", session_id),
            )
        out = deliver_scheduled_reply(
            self.store,
            tenant_id=self.tenant_id,
            reply_text="该起来活动啦",
            delivery_json='{"weixin":{"enabled":true}}',
            resolved_channel="wechat",
            resolved_chat_id="wx-user-123",
            resolved_account_id="weixin-default",
            session_id=session_id,
        )
        self.assertTrue(out.get("ok"))
        mock_enqueue.assert_called_once()
        kwargs = mock_enqueue.call_args.kwargs
        self.assertEqual(kwargs.get("context_token"), "ctx-abc")
        self.assertEqual(kwargs.get("chat_id"), "wx-user-123")


if __name__ == "__main__":
    unittest.main()
