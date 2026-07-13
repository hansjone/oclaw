from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from runtime.scheduler.channel_delivery import deliver_scheduled_reply
from svc.persistence.assistant_store import reset_assistant_store_singleton
from svc.persistence.sqlite_store import SqliteStore


class WhatsappScheduledMentionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "wa_mentions.sqlite"
        os.environ["OPS_ASSISTANT_DB_PATH"] = str(self.db)
        os.environ["AIA_ASSISTANT_DB_BACKEND"] = "sqlite"
        reset_assistant_store_singleton()
        self.store = SqliteStore(str(self.db))
        tenant = self.store.create_tenant("Team")
        self.tenant_id = str(tenant["id"])
        self.store.upsert_whatsapp_contact(
            tenant_id=self.tenant_id,
            account_id="wa-default",
            external_user_id="333465375410398@lid",
            push_name="Egista Hadi Putranto",
            phone="33346537541839",
            list_type="whitelist",
        )

    def tearDown(self) -> None:
        reset_assistant_store_singleton()
        self._tmp.cleanup()

    def test_deliver_scheduled_reply_encodes_explicit_mention_jids(self) -> None:
        delivery = {
            "whatsapp": {
                "enabled": True,
                "target_type": "group",
                "chat_id": "120363012345678@g.us",
                "account_id": "wa-default",
                "mention_jids": ["333465375410398@lid"],
            },
            "weixin": {"enabled": False},
        }
        reply_text = "💧 @+1 33346537541839 该喝水啦！记得保持水分哦~"
        result = deliver_scheduled_reply(
            self.store,
            tenant_id=self.tenant_id,
            reply_text=reply_text,
            delivery_json=__import__("json").dumps(delivery),
        )
        self.assertTrue(result.get("ok"), result)
        pending = self.store.list_pending_channel_outbound_messages(
            channel="whatsapp",
            account_id="wa-default",
            limit=5,
        )
        self.assertEqual(len(pending), 1)
        source = __import__("json").loads(str(pending[0].get("source") or "{}"))
        self.assertEqual(source.get("mention_jids"), ["333465375410398@lid"])
        out_text = str(pending[0].get("text") or "")
        self.assertTrue(out_text.startswith("@Egista Hadi Putranto"))
        self.assertIn("该喝水啦", out_text)
        self.assertNotIn("@+1", out_text)
        self.assertTrue(source.get("mention_text_ready"))
        self.assertEqual(source.get("mention_names"), ["Egista Hadi Putranto"])

    def test_deliver_scheduled_reply_infers_mentions_from_phoneish_text(self) -> None:
        self.store.upsert_whatsapp_contact(
            tenant_id=self.tenant_id,
            account_id="wa-default",
            external_user_id="200846277140511@lid",
            push_name="吴华",
            phone="0846277140511",
            list_type="whitelist",
        )
        delivery = {
            "whatsapp": {
                "enabled": True,
                "target_type": "group",
                "chat_id": "120363012345678@g.us",
                "account_id": "wa-default",
            },
            "weixin": {"enabled": False},
        }
        reply_text = "💧 @+20 0846277140511 该喝水啦！快去补充一下水分吧～ 💧"
        result = deliver_scheduled_reply(
            self.store,
            tenant_id=self.tenant_id,
            reply_text=reply_text,
            delivery_json=__import__("json").dumps(delivery),
        )
        self.assertTrue(result.get("ok"), result)
        pending = self.store.list_pending_channel_outbound_messages(
            channel="whatsapp",
            account_id="wa-default",
            limit=5,
        )
        self.assertEqual(len(pending), 1)
        source = __import__("json").loads(str(pending[0].get("source") or "{}"))
        self.assertEqual(source.get("mention_jids"), ["200846277140511@lid"])
        out_text = str(pending[0].get("text") or "")
        self.assertTrue(out_text.startswith("@吴华"))
        self.assertIn("该喝水啦", out_text)
        self.assertNotIn("@+20", out_text)

    def test_normalize_bare_digits_to_lid(self) -> None:
        from runtime.scheduler.whatsapp_mentions import normalize_whatsapp_mention_jids

        self.assertEqual(normalize_whatsapp_mention_jids(["200846277140511"]), ["200846277140511@lid"])


if __name__ == "__main__":
    unittest.main()
