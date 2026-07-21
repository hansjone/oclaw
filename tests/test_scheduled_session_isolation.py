from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime.scheduler.channel_delivery import deliver_scheduled_reply
from runtime.scheduler.session_resolver import resolve_scheduled_session
from runtime.scheduler.whatsapp_mentions import (
    finalize_whatsapp_scheduled_delivery,
    resolve_scheduled_whatsapp_mention_targets,
)
from svc.persistence.sqlite_store import SqliteStore


class ScheduledSessionIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "sched_iso.sqlite"
        os.environ["OPS_ASSISTANT_DB_PATH"] = str(self.db)
        self.store = SqliteStore(str(self.db))
        self.tenant_id = str(self.store.create_tenant("Team")["id"])
        admin = self.store.create_user_account(
            tenant_id=self.tenant_id,
            username="administrator",
            display_name="Admin",
            role="owner",
            password_hash="x",
            is_active=True,
        )
        self.admin_id = str(admin["id"])
        interactive = self.store.create_session("WA interactive")
        self.interactive_session_id = str(interactive.id)
        self.store.ensure_ui_session_owner(
            session_id=self.interactive_session_id,
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
                (
                    self.tenant_id,
                    "whatsapp",
                    "wa-default",
                    "120363012345678@g.us",
                    "333465375410398@lid",
                    self.interactive_session_id,
                ),
            )
        self.store.add_message(
            session_id=self.interactive_session_id,
            role="user",
            content="帮我设个喝水提醒",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_resolve_scheduled_session_uses_fresh_execution_session(self) -> None:
        job = mock.MagicMock()
        job.tenant_id = self.tenant_id
        job.source_session_id = self.interactive_session_id
        job.delivery_json = json.dumps(
            {
                "whatsapp": {
                    "enabled": True,
                    "target_type": "group",
                    "chat_id": "120363012345678@g.us",
                    "account_id": "wa-default",
                },
                "weixin": {"enabled": False},
            }
        )
        job.name = "喝水提醒"

        resolved = resolve_scheduled_session(
            self.store,
            job=job,
            created_by_user_id=self.admin_id,
            run_id="run-abc12345",
        )
        self.assertNotEqual(resolved.session_id, self.interactive_session_id)
        self.assertEqual(resolved.source_session_id, self.interactive_session_id)
        self.assertEqual(resolved.external_chat_id, "120363012345678@g.us")
        rows = self.store.get_messages(session_id=resolved.session_id, limit=10)
        self.assertEqual(len(rows), 0)


class ScheduledMentionCreatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "sched_mention.sqlite"
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
        self.store.upsert_whatsapp_contact(
            tenant_id=self.tenant_id,
            account_id="wa-default",
            external_user_id="999999999999@lid",
            push_name="Oliver",
            phone="",
            list_type="whitelist",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_finalize_defaults_mention_to_creator_and_filters_bot(self) -> None:
        delivery = finalize_whatsapp_scheduled_delivery(
            {
                "whatsapp": {
                    "enabled": True,
                    "target_type": "group",
                    "chat_id": "120363012345678@g.us",
                    "mention_jids": ["999999999999@lid"],
                },
                "creator": {
                    "external_user_id": "333465375410398@lid",
                    "push_name": "Egista Hadi Putranto",
                },
            },
            creator_external_user_id="333465375410398@lid",
            creator_push_name="Egista Hadi Putranto",
            bot_jid="",
            bot_lid="999999999999@lid",
        )
        wa = delivery["whatsapp"]
        self.assertEqual(wa["mention_jids"], ["333465375410398@lid"])
        self.assertEqual(wa["mention_names"], ["Egista Hadi Putranto"])

    def test_resolve_scheduled_mention_targets_prefers_creator_when_only_bot_configured(self) -> None:
        delivery = {
            "whatsapp": {
                "enabled": True,
                "mention_jids": ["999999999999@lid"],
                "bot_lid": "999999999999@lid",
            },
            "creator": {
                "external_user_id": "333465375410398@lid",
                "push_name": "Egista Hadi Putranto",
            },
        }
        jids, names = resolve_scheduled_whatsapp_mention_targets(
            delivery=delivery,
            reply_text="该喝水啦",
            store=self.store,
            tenant_id=self.tenant_id,
            account_id="wa-default",
        )
        self.assertEqual(jids, ["333465375410398@lid"])
        self.assertEqual(names, ["Egista Hadi Putranto"])

    def test_deliver_scheduled_reply_mentions_creator_not_bot(self) -> None:
        delivery = finalize_whatsapp_scheduled_delivery(
            {
                "whatsapp": {
                    "enabled": True,
                    "target_type": "group",
                    "chat_id": "120363012345678@g.us",
                    "account_id": "wa-default",
                    "mention_jids": ["999999999999@lid"],
                },
            },
            creator_external_user_id="333465375410398@lid",
            creator_push_name="Egista Hadi Putranto",
            bot_lid="999999999999@lid",
        )
        delivery = {
            **delivery,
            "weixin": {"enabled": False},
            "creator": {
                "external_user_id": "333465375410398@lid",
                "push_name": "Egista Hadi Putranto",
            },
        }
        result = deliver_scheduled_reply(
            self.store,
            tenant_id=self.tenant_id,
            reply_text="💧 该喝水啦！",
            delivery_json=json.dumps(delivery, ensure_ascii=False),
        )
        self.assertTrue(result.get("ok"), result)
        pending = self.store.list_pending_channel_outbound_messages(
            channel="whatsapp",
            account_id="wa-default",
            limit=5,
        )
        self.assertEqual(len(pending), 1)
        out_text = str(pending[0].get("text") or "")
        self.assertTrue(out_text.startswith("@Egista Hadi Putranto"))
        source = json.loads(str(pending[0].get("source") or "{}"))
        self.assertEqual(source.get("mention_jids"), ["333465375410398@lid"])


if __name__ == "__main__":
    unittest.main()
