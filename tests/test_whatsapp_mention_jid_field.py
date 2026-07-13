from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from runtime.scheduler.whatsapp_mentions import format_whatsapp_mention_text, merge_whatsapp_mention_jids, normalize_whatsapp_mention_jids
from svc.persistence.assistant_store import reset_assistant_store_singleton
from svc.persistence.sqlite_store import SqliteStore


class WhatsappMentionJidFieldTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "wa_names.sqlite"
        os.environ["OPS_ASSISTANT_DB_PATH"] = str(self.db)
        os.environ["AIA_ASSISTANT_DB_BACKEND"] = "sqlite"
        reset_assistant_store_singleton()
        self.store = SqliteStore(str(self.db))
        tenant = self.store.create_tenant("Team")
        self.tenant_id = str(tenant["id"])

    def tearDown(self) -> None:
        reset_assistant_store_singleton()
        self._tmp.cleanup()
    def test_normalize_whatsapp_mention_jids(self) -> None:
        out = normalize_whatsapp_mention_jids(
            ["6281@s.whatsapp.net", "6282@s.whatsapp.net, 6283@s.whatsapp.net"]
        )
        self.assertEqual(
            out,
            ["6281@s.whatsapp.net", "6282@s.whatsapp.net", "6283@s.whatsapp.net"],
        )

    def test_merge_whatsapp_mention_jids_into_delivery(self) -> None:
        delivery = merge_whatsapp_mention_jids(
            {"whatsapp": {"enabled": True, "chat_id": "120@g.us"}},
            ["6281@s.whatsapp.net"],
        )
        self.assertEqual(delivery["whatsapp"]["mention_jids"], ["6281@s.whatsapp.net"])

    def test_format_whatsapp_mention_text_uses_push_name(self) -> None:
        out = format_whatsapp_mention_text(
            "💧 @+1 33346537541839 该喝水啦",
            ["333465375410398@lid"],
            store=self.store,
            tenant_id=self.tenant_id,
            account_id="wa-default",
            mention_names=["Egista Hadi Putranto"],
        )
        self.assertEqual(out, "@Egista Hadi Putranto 💧 该喝水啦")

    def test_format_whatsapp_mention_text_looks_up_push_name_by_jid(self) -> None:
        self.store.upsert_whatsapp_contact(
            tenant_id=self.tenant_id,
            account_id="wa-default",
            external_user_id="333465375410398@lid",
            push_name="Egista Hadi Putranto",
            phone="33346537541839",
            list_type="whitelist",
        )
        out = format_whatsapp_mention_text(
            "该喝水啦",
            ["333465375410398@lid"],
            store=self.store,
            tenant_id=self.tenant_id,
            account_id="wa-default",
        )
        self.assertEqual(out, "@Egista Hadi Putranto 该喝水啦")


if __name__ == "__main__":
    unittest.main()
