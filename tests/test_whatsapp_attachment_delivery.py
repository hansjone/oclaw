from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime.scheduler.channel_delivery import deliver_scheduled_reply
from runtime.scheduler.whatsapp_mentions import encode_whatsapp_outbound_source
from svc.persistence.sqlite_store import SqliteStore


class WhatsappAttachmentDeliveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "wa_attach.sqlite"
        self.store = SqliteStore(str(self.db))
        tenant = self.store.create_tenant("Team")
        self.tenant_id = str(tenant["id"])
        sess = self.store.create_session("WA scheduled")
        self.session_id = str(sess.id)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_encode_whatsapp_outbound_source_with_attachments(self) -> None:
        atts = [{"name": "report.xlsx", "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "data_base64": "abc"}]
        raw = encode_whatsapp_outbound_source(
            mention_jids=["111@lid"],
            attachments=atts,
            media_path="/tmp/report.xlsx",
        )
        data = json.loads(raw)
        self.assertEqual(data.get("mention_jids"), ["111@lid"])
        self.assertEqual(data.get("attachments"), atts)
        self.assertEqual(data.get("media_path"), "/tmp/report.xlsx")

    def test_list_pending_whatsapp_outbound_includes_attachments_from_source(self) -> None:
        source = encode_whatsapp_outbound_source(
            attachments=[{"name": "a.txt", "data_base64": "dGVzdA=="}],
            media_path="D:/tmp/a.txt",
        )
        self.store.enqueue_channel_outbound_message(
            channel="whatsapp",
            chat_id="120363012345678@g.us",
            text="file attached",
            tenant_id=self.tenant_id,
            account_id="wa-default",
            source=source,
        )
        items = self.store.list_pending_channel_outbound_messages(channel="whatsapp", account_id="wa-default", limit=5)
        self.assertEqual(len(items), 1)
        self.assertEqual(len(items[0].get("attachments") or []), 1)
        self.assertEqual(items[0].get("media_path"), "D:/tmp/a.txt")

    def test_deliver_scheduled_reply_encodes_tool_attachments_for_turn(self) -> None:
        turn_uuid = "turn-wa-attach-1"
        self.store.add_message(
            session_id=self.session_id,
            role="tool",
            content='{"ok": true}',
            turn_uuid=turn_uuid,
            event_type="tool_result",
            attachments=json.dumps(
                [
                    {
                        "type": "binary_ref",
                        "attachment_id": "att-1",
                        "name": "daily.xlsx",
                        "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        "deliverable": True,
                    }
                ],
                ensure_ascii=False,
            ),
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
        with mock.patch(
            "runtime.scheduler.channel_delivery._prepare_channel_outbound_attachments",
            return_value=(
                [{"name": "daily.xlsx", "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "data_base64": "ZGF0YQ=="}],
                "",
            ),
        ):
            result = deliver_scheduled_reply(
                self.store,
                tenant_id=self.tenant_id,
                reply_text="今日报表已生成",
                delivery_json=json.dumps(delivery, ensure_ascii=False),
                session_id=self.session_id,
                turn_uuid=turn_uuid,
            )
        self.assertTrue(result.get("ok"), result)
        pending = self.store.list_pending_channel_outbound_messages(
            channel="whatsapp",
            account_id="wa-default",
            limit=5,
        )
        self.assertEqual(len(pending), 1)
        source = json.loads(str(pending[0].get("source") or "{}"))
        self.assertEqual(len(source.get("attachments") or []), 1)
        self.assertEqual(source["attachments"][0].get("name"), "daily.xlsx")
        self.assertEqual((result.get("channels") or {}).get("whatsapp", {}).get("attachments"), 1)


if __name__ == "__main__":
    unittest.main()
