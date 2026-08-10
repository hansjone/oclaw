from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from runtime.extensions.whatsapp.formatting import markdown_to_whatsapp_text
from svc.persistence.sqlite_store import SqliteStore


class MarkdownToWhatsappTests(unittest.TestCase):
    def test_bold_heading_link_strike(self) -> None:
        src = (
            "## Bandwidth summary\n"
            "**Critical:** 3\n"
            "See [UME](https://example.com/ume) for detail.\n"
            "~~old~~ keep\n"
        )
        out = markdown_to_whatsapp_text(src)
        self.assertIn("*Bandwidth summary*", out)
        self.assertIn("*Critical:* 3", out)
        self.assertIn("UME: https://example.com/ume", out)
        self.assertIn("~old~", out)
        self.assertNotIn("**", out)
        self.assertNotIn("##", out)

    def test_table_to_bullets(self) -> None:
        src = (
            "| Hostname | Util |\n"
            "|---|---|\n"
            "| BTM-A | 92% |\n"
            "| ACH-B | 88% |\n"
        )
        out = markdown_to_whatsapp_text(src)
        self.assertIn("- Hostname: BTM-A · Util: 92%", out)
        self.assertIn("- Hostname: ACH-B · Util: 88%", out)
        self.assertNotIn("|---|", out)

    def test_preserves_code_and_list_markers(self) -> None:
        src = (
            "Run `show interface`:\n"
            "```\n"
            " GigabitEthernet0/1\n"
            "```\n"
            "- first\n"
            "* second\n"
            "Note: _careful_ word\n"
        )
        out = markdown_to_whatsapp_text(src)
        self.assertIn("`show interface`", out)
        self.assertIn("```", out)
        self.assertIn("GigabitEthernet0/1", out)
        self.assertIn("- first", out)
        self.assertIn("* second", out)
        self.assertIn("_careful_", out)

    def test_already_whatsapp_bold_stays(self) -> None:
        src = "*Critical:* 2 devices confirmed"
        out = markdown_to_whatsapp_text(src)
        self.assertEqual(out, src)

    def test_disable_env(self) -> None:
        prev = os.environ.get("AIA_WHATSAPP_MARKDOWN_CONVERT")
        os.environ["AIA_WHATSAPP_MARKDOWN_CONVERT"] = "0"
        try:
            src = "**bold** and ## Head"
            self.assertEqual(markdown_to_whatsapp_text(src), src)
        finally:
            if prev is None:
                os.environ.pop("AIA_WHATSAPP_MARKDOWN_CONVERT", None)
            else:
                os.environ["AIA_WHATSAPP_MARKDOWN_CONVERT"] = prev


class EnqueueConvertsWhatsappTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "wa.sqlite"
        os.environ["OPS_ASSISTANT_DB_PATH"] = str(self.db)
        self.store = SqliteStore(str(self.db))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_enqueue_whatsapp_converts_markdown(self) -> None:
        msg_id = self.store.enqueue_channel_outbound_message(
            channel="whatsapp",
            chat_id="x@g.us",
            text="## Done\n**ok**",
            account_id="wa-default",
        )
        rows = self.store.list_pending_channel_outbound_messages(
            channel="whatsapp", account_id="wa-default", limit=5
        )
        hit = next(r for r in rows if r["id"] == msg_id)
        self.assertIn("*Done*", hit["text"])
        self.assertIn("*ok*", hit["text"])
        self.assertNotIn("**", hit["text"])

    def test_enqueue_weixin_unchanged(self) -> None:
        msg_id = self.store.enqueue_channel_outbound_message(
            channel="weixin",
            chat_id="wx-1",
            text="**keep markdown**",
            account_id="wx-default",
        )
        # list_pending is channel-specific; read via SQL-ish helper path
        rows = self.store.list_pending_channel_outbound_messages(
            channel="weixin", account_id="wx-default", limit=5
        )
        hit = next(r for r in rows if r["id"] == msg_id)
        self.assertEqual(hit["text"], "**keep markdown**")


if __name__ == "__main__":
    unittest.main()
