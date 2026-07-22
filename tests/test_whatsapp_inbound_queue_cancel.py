from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from runtime.application.gateway import inbound_service as inbound_mod
from runtime.application.gateway.channel_turn_gate import reset_channel_turn_gate_for_tests
from svc.persistence.sqlite_store import SqliteStore


class _FakeTurn:
    def __init__(self, text: str = "final answer") -> None:
        self.reply_text = text
        self.turn_uuid = "turn-1"


class WhatsappInboundSerialQueueTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "wa_inbound.sqlite"
        self.store = SqliteStore(str(self.db))
        tenant = self.store.create_tenant("Team")
        self.tenant_id = str(tenant["id"])
        user = self.store.create_user(tenant_id=self.tenant_id, display_name="ops", role="administrator")
        self.user_id = str(user["id"])
        self.store.upsert_user_channel_account(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            channel="whatsapp",
            account_id="wa-default",
            name="wa-default",
            config={},
            is_active=True,
        )
        self.store.upsert_channel_identity_v2(
            tenant_id=self.tenant_id,
            channel="whatsapp",
            account_id="wa-default",
            external_user_id="628100000@s.whatsapp.net",
            user_id=self.user_id,
        )
        reset_channel_turn_gate_for_tests()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _payload(self, text: str = "hello", stanza: str = "stanza1") -> dict:
        return {
            "channel": "whatsapp",
            "account_id": "wa-default",
            "user_id": "628100000@s.whatsapp.net",
            "chat_id": "120363011111111111@g.us",
            "text": f"@bot {text}",
            "is_group": True,
            "mentions": ["bot@s.whatsapp.net"],
            "metadata": {
                "bot_jid": "bot@s.whatsapp.net",
                "mentions_bot": True,
                "group_name": "AI nms",
                "raw": {
                    "id": stanza,
                    "participant": "628100000@s.whatsapp.net",
                    "pushName": "Egista",
                },
            },
        }

    def _patch_common(self):
        return mock.patch.multiple(
            inbound_mod,
            get_assistant_store=mock.MagicMock(return_value=self.store),
            _build_admin_gateway_executor=mock.MagicMock(return_value=object()),
            _resolve_channel_dispatch=mock.MagicMock(return_value=("expert", "ops", "en")),
        )

    def test_whatsapp_final_reply_goes_to_outbound_queue(self) -> None:
        with self._patch_common(), mock.patch("runtime.gateway.OclawGateway") as gw_cls, mock.patch(
            "runtime.orchestration.group_ingest.should_process_group_inbound", return_value=True
        ), mock.patch(
            "runtime.application.gateway.whatsapp_inbound_access.handle_whatsapp_access",
            return_value=None,
        ):
            gw = gw_cls.return_value
            gw.handle_turn.return_value = _FakeTurn("optical ok")
            out = inbound_mod.process_inbound_payload(self._payload("check optics"))

        self.assertTrue(out.get("ok"))
        self.assertEqual(out.get("delivery"), "queued")
        self.assertEqual(out.get("replies"), [])
        self.assertTrue(str(out.get("outbound_message_id") or "").strip())
        pending = self.store.list_pending_channel_outbound_messages(
            channel="whatsapp", account_id="wa-default", limit=5
        )
        self.assertEqual(len(pending), 1)
        self.assertIn("optical ok", pending[0].get("text") or "")
        source = json.loads(str(pending[0].get("source") or "{}"))
        self.assertEqual(source.get("kind"), "inbound_reply")
        self.assertEqual(source.get("quote_stanza_id"), "stanza1")

    def test_whatsapp_queue_delivery_does_not_double_enqueue(self) -> None:
        """Regression: agent-path enqueue must not fall through to bottom enqueue."""
        with self._patch_common(), mock.patch("runtime.gateway.OclawGateway") as gw_cls, mock.patch(
            "runtime.orchestration.group_ingest.should_process_group_inbound", return_value=True
        ), mock.patch(
            "runtime.application.gateway.whatsapp_inbound_access.handle_whatsapp_access",
            return_value=None,
        ):
            gw = gw_cls.return_value
            gw.handle_turn.return_value = _FakeTurn("only once")
            out = inbound_mod.process_inbound_payload(self._payload("ping"))

        self.assertEqual(out.get("delivery"), "queued")
        self.assertEqual(out.get("replies"), [])
        pending = self.store.list_pending_channel_outbound_messages(
            channel="whatsapp", account_id="wa-default", limit=10
        )
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].get("text"), "only once")

    def test_whatsapp_queue_includes_deliverable_tool_image(self) -> None:
        """Regression (session 8d2b…): image on tool row must still enqueue to WhatsApp.

        Final assistant_text often has no attachments; deliverable lives on
        ``save_deliverable_attachment`` tool_result. Queue path used to skip it.
        """
        reply_text = "done, here is a cute puppy"

        def _handle_turn(**kwargs):
            msg = kwargs.get("msg")
            sid = str(getattr(msg, "session_id", "") or "")
            self.store.add_message(sid, "user", "draw a puppy", event_type="user_text")
            self.store.add_message(
                sid,
                "tool",
                json.dumps({"ok": True, "attachment_id": "img-puppy", "deliverable": True}),
                attachments=[
                    {
                        "type": "image_ref",
                        "attachment_id": "img-puppy",
                        "name": "cute_puppy.png",
                        "mime": "image/png",
                        "deliverable": True,
                    }
                ],
                event_type="tool_result",
            )
            # Final assistant body intentionally has no attachments (real gateway behavior).
            self.store.add_message(sid, "assistant", reply_text, event_type="assistant_text")
            return _FakeTurn(reply_text)

        with self._patch_common(), mock.patch("runtime.gateway.OclawGateway") as gw_cls, mock.patch(
            "runtime.orchestration.group_ingest.should_process_group_inbound", return_value=True
        ), mock.patch(
            "runtime.application.gateway.whatsapp_inbound_access.handle_whatsapp_access",
            return_value=None,
        ), mock.patch.object(
            inbound_mod,
            "_maybe_expand_reply_attachments_for_channel",
            # Keep image_ref as-is so we can assert attachment_id without a real asset blob.
            side_effect=lambda reply: None,
        ):
            gw = gw_cls.return_value
            gw.handle_turn.side_effect = lambda **kw: _handle_turn(**kw)
            out = inbound_mod.process_inbound_payload(self._payload("draw a puppy", stanza="img1"))

        self.assertEqual(out.get("delivery"), "queued")
        pending = self.store.list_pending_channel_outbound_messages(
            channel="whatsapp", account_id="wa-default", limit=5
        )
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].get("text"), reply_text)
        atts = pending[0].get("attachments") or []
        self.assertTrue(atts, "outbound must include deliverable image attachment")
        self.assertEqual(atts[0].get("attachment_id"), "img-puppy")
        self.assertTrue(atts[0].get("deliverable") is True)

    def test_busy_inbound_is_accepted_queued_then_merged(self) -> None:
        release = threading.Event()
        seen_texts: list[str] = []

        def _handle_turn(**kwargs):
            msg = kwargs.get("msg")
            text = str(getattr(msg, "text", "") or "")
            seen_texts.append(text)
            if len(seen_texts) == 1:
                # While first turn runs, enqueue two follow-ups from other threads/requests.
                release.wait(timeout=2.0)
            return _FakeTurn(f"ans:{len(seen_texts)}")

        with self._patch_common(), mock.patch("runtime.gateway.OclawGateway") as gw_cls, mock.patch(
            "runtime.orchestration.group_ingest.should_process_group_inbound", return_value=True
        ), mock.patch(
            "runtime.application.gateway.whatsapp_inbound_access.handle_whatsapp_access",
            return_value=None,
        ):
            gw = gw_cls.return_value
            gw.handle_turn.side_effect = lambda **kw: _handle_turn(**kw)

            results: dict[str, dict] = {}

            def run_first() -> None:
                results["first"] = inbound_mod.process_inbound_payload(
                    self._payload("first question", stanza="s1")
                )

            t = threading.Thread(target=run_first, daemon=True)
            t.start()
            # Wait until first turn has started (gate busy).
            import time

            for _ in range(100):
                if seen_texts:
                    break
                time.sleep(0.02)

            self.assertTrue(seen_texts, "first turn did not start")
            out_b = inbound_mod.process_inbound_payload(self._payload("second question", stanza="s2"))
            out_c = inbound_mod.process_inbound_payload(self._payload("third question", stanza="s3"))
            self.assertEqual(out_b.get("delivery"), "accepted_queued")
            self.assertEqual(out_c.get("delivery"), "accepted_queued")

            release.set()
            t.join(timeout=5.0)
            self.assertFalse(t.is_alive())
            self.assertEqual(results["first"].get("delivery"), "queued")

        self.assertEqual(len(seen_texts), 2)
        self.assertIn("first question", seen_texts[0])
        self.assertIn("second question", seen_texts[1])
        self.assertIn("third question", seen_texts[1])
        pending = self.store.list_pending_channel_outbound_messages(
            channel="whatsapp", account_id="wa-default", limit=10
        )
        self.assertEqual(len(pending), 2)
        texts = " ".join(str(p.get("text") or "") for p in pending)
        self.assertIn("ans:1", texts)
        self.assertIn("ans:2", texts)


if __name__ == "__main__":
    unittest.main()
