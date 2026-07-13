from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from runtime.scheduler.channel_delivery import _encode_weixin_outbound_source, _decode_weixin_outbound_source
from svc.persistence.sqlite_store import SqliteStore


class WeixinAttachmentDeliveryTests(unittest.TestCase):
    def test_encode_decode_weixin_outbound_source_with_attachments(self) -> None:
        atts = [{"name": "report.xlsx", "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "data_base64": "abc"}]
        raw = _encode_weixin_outbound_source(context_token="ctx-1", attachments=atts, media_path="")
        data = _decode_weixin_outbound_source(raw)
        self.assertEqual(data.get("context_token"), "ctx-1")
        self.assertEqual(data.get("attachments"), atts)

    def test_list_pending_weixin_outbound_includes_attachments_from_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.db"
            store = SqliteStore(str(db))
            source = json.dumps(
                {
                    "kind": "scheduled_job",
                    "context_token": "ctx-9",
                    "attachments": [{"name": "a.txt", "data_base64": "dGVzdA=="}],
                    "media_path": "D:/tmp/a.txt",
                },
                ensure_ascii=False,
            )
            store.enqueue_channel_outbound_message(
                channel="weixin",
                chat_id="wx-user-1",
                text="file attached",
                tenant_id="tenant-a",
                account_id="acct-1",
                source=source,
            )
            items = store.list_pending_weixin_outbound_messages(account_id="acct-1", limit=5)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].get("context_token"), "ctx-9")
            self.assertEqual(len(items[0].get("attachments") or []), 1)
            self.assertEqual(items[0].get("media_path"), "D:/tmp/a.txt")


if __name__ == "__main__":
    unittest.main()
