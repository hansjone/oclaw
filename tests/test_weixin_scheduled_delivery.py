from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from runtime.scheduler.channel_delivery import enqueue_weixin_reply
from runtime.scheduler.weixin_delivery import resolve_weixin_delivery_target
from svc.persistence.sqlite_store import SqliteStore


class WeixinBridgePollTests(unittest.TestCase):
    def test_poll_accepts_wechat_channel_alias(self) -> None:
        from interfaces.http.weixin_ilink_api import _BRIDGE

        _BRIDGE._events.clear()
        _BRIDGE._seq = 0
        _BRIDGE.enqueue_reply(
            token="",
            channel="weixin",
            account_id="acct-1",
            chat_id="user-1",
            text="hello",
            context_token="ctx-1",
        )
        msgs, _ = _BRIDGE.poll(token="sidecar-token", cursor=0, channel="wechat", account_id="acct-1")
        self.assertEqual(len(msgs), 1)
        self.assertEqual(str(msgs[0].get("text") or ""), "hello")

    def test_poll_accepts_legacy_default_account_id(self) -> None:
        from interfaces.http.weixin_ilink_api import _BRIDGE

        _BRIDGE._events.clear()
        _BRIDGE._seq = 0
        _BRIDGE.enqueue_reply(
            token="",
            channel="wechat",
            account_id="weixin-default",
            chat_id="user-1",
            text="hello",
            context_token="ctx-1",
        )
        msgs, _ = _BRIDGE.poll(token="sidecar-token", cursor=0, channel="wechat", account_id="real-acct")
        self.assertEqual(len(msgs), 1)


class WeixinDeliveryTargetTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "wx.sqlite"
        os.environ["OPS_ASSISTANT_DB_PATH"] = str(self.db)
        self.store = SqliteStore(str(self.db))
        t = self.store.create_tenant("Team")
        self.tenant_id = str(t["id"])
        sess = self.store.create_session("wx")
        self.session_id = str(sess.id)
        with self.store._connect() as conn:
            conn.execute(
                """
                INSERT INTO channel_session_v2
                    (tenant_id, channel, account_id, external_chat_id, external_user_id, session_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (self.tenant_id, "wechat", "real-acct-9", "wx-user-9", "wx-user-9", self.session_id),
            )
        self.store.set_channel_context_token(
            tenant_id=self.tenant_id,
            channel="wechat",
            account_id="real-acct-9",
            external_chat_id="wx-user-9",
            context_token="ctx-xyz",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_resolve_account_and_token_from_session(self) -> None:
        target = resolve_weixin_delivery_target(
            self.store,
            tenant_id=self.tenant_id,
            session_id=self.session_id,
            delivery={"weixin": {"enabled": True}},
            resolved_channel="wechat",
            resolved_chat_id="",
            resolved_account_id="weixin-default",
        )
        self.assertEqual(target["account_id"], "real-acct-9")
        self.assertEqual(target["chat_id"], "wx-user-9")
        self.assertEqual(target["context_token"], "ctx-xyz")


class EnqueueWeixinReplyTests(unittest.TestCase):
    @patch("interfaces.http.weixin_ilink_api.enqueue_weixin_outbound_reply", return_value="7")
    def test_requires_context_token(self, _mock_enqueue: MagicMock) -> None:
        out = enqueue_weixin_reply(
            channel="wechat",
            account_id="acct",
            chat_id="user",
            text="hi",
            context_token="",
        )
        self.assertFalse(out.get("ok"))
        self.assertEqual(out.get("error"), "context_token_missing")
        _mock_enqueue.assert_not_called()

    @patch("interfaces.http.weixin_ilink_api.enqueue_weixin_outbound_reply", return_value="8")
    def test_queues_with_context_token(self, mock_enqueue: MagicMock) -> None:
        out = enqueue_weixin_reply(
            channel="wechat",
            account_id="acct",
            chat_id="user",
            text="hi",
            context_token="ctx-1",
        )
        self.assertTrue(out.get("ok"))
        self.assertTrue(out.get("queued"))
        mock_enqueue.assert_called_once()

    @patch("interfaces.http.weixin_ilink_api.enqueue_weixin_outbound_reply", return_value="9")
    def test_persists_durable_outbound_when_store_available(self, mock_enqueue: MagicMock) -> None:
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db = Path(tmp.name) / "wx.sqlite"
        os.environ["OPS_ASSISTANT_DB_PATH"] = str(db)
        store = SqliteStore(str(db))
        try:
            out = enqueue_weixin_reply(
                channel="wechat",
                account_id="acct",
                chat_id="user",
                text="hi",
                context_token="ctx-1",
                store=store,
                tenant_id="t1",
            )
            self.assertTrue(out.get("ok"))
            self.assertTrue(out.get("durable"))
            pending = store.list_pending_weixin_outbound_messages(account_id="acct", limit=10)
            self.assertEqual(len(pending), 1)
            self.assertEqual(str(pending[0].get("context_token") or ""), "ctx-1")
            mock_enqueue.assert_called_once()
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
