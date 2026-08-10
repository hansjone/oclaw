from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from runtime.application.gateway import inbound_service as inbound_mod
from runtime.application.gateway.channel_turn_gate import reset_channel_turn_gate_for_tests
from runtime.application.gateway.whatsapp_progress import (
    WhatsappTurnProgressPublisher,
    humanize_long_tool,
    humanize_progress_text,
    normalize_tool_key,
    should_forward_progress_text,
)
from svc.persistence.sqlite_store import SqliteStore


class WhatsappProgressHelpersTests(unittest.TestCase):
    def test_normalize_tool_key(self) -> None:
        self.assertEqual(normalize_tool_key("mcp__netx__execManagedNe"), "execmanagedne")
        self.assertEqual(normalize_tool_key("netx_exec_managed_ne"), "execmanagedne")
        self.assertEqual(normalize_tool_key("ume_alarm_xlsx_report"), "umealarmxlsxreport")

    def test_humanize_long_tool(self) -> None:
        zh = humanize_long_tool(tool_name="mcp__netx__execManagedNe", lang="zh")
        en = humanize_long_tool(tool_name="mcp__netx__execManagedNe", lang="en")
        self.assertIsNotNone(zh)
        self.assertIsNotNone(en)
        self.assertIn("设备", str(zh))
        self.assertIn("CLI", str(en))
        self.assertIsNone(humanize_long_tool(tool_name="read_file", lang="zh"))

    def test_should_forward_progress_text(self) -> None:
        self.assertFalse(should_forward_progress_text("oclaw: running…"))
        self.assertFalse(should_forward_progress_text("oclaw: think (1)…"))
        self.assertFalse(should_forward_progress_text("oclaw: tools done (120ms)"))
        self.assertTrue(should_forward_progress_text("oclaw: tools done (12000ms)"))
        self.assertTrue(should_forward_progress_text("oclaw: image specialist (legacy multimodal HTTP)…"))

    def test_humanize_progress_text(self) -> None:
        self.assertIn("整理", humanize_progress_text(text="oclaw: tools done (9000ms)", lang="zh"))
        self.assertIn("composing", humanize_progress_text(text="oclaw: tools done (9000ms)", lang="en").lower())


class WhatsappTurnProgressPublisherTests(unittest.TestCase):
    def test_tool_call_emits_and_throttles(self) -> None:
        sent: list[tuple[str, dict[str, Any] | None]] = []
        clock = {"t": 100.0}

        def enqueue(text: str, meta: dict[str, Any] | None) -> None:
            sent.append((text, meta))

        pub = WhatsappTurnProgressPublisher(
            enqueue=enqueue,
            lang="zh",
            is_group=False,
            min_interval_sec=10.0,
            enabled=True,
            clock=lambda: clock["t"],
        )
        pub.on_progress("oclaw: think (1)…")
        self.assertEqual(sent, [])

        pub.on_tool_ui("tool_use_call", {"tool_name": "mcp__netx__execManagedNe"})
        self.assertEqual(len(sent), 1)
        self.assertIn("设备", sent[0][0])

        clock["t"] = 105.0
        pub.on_tool_ui("tool_use_call", {"tool_name": "mcp__netx__queryUmeAlarms"})
        self.assertEqual(len(sent), 1)  # throttled

        clock["t"] = 111.0
        pub.on_tool_ui("tool_use_call", {"tool_name": "mcp__netx__queryUmeAlarms"})
        self.assertEqual(len(sent), 2)

        pub.on_progress("oclaw: tools done (15000ms)")
        self.assertEqual(len(sent), 2)
        clock["t"] = 122.0
        pub.on_progress("oclaw: tools done (15000ms)")
        self.assertEqual(len(sent), 3)
        self.assertIn("整理", sent[2][0])

    def test_group_metadata_mentions_without_quote(self) -> None:
        sent: list[tuple[str, dict[str, Any] | None]] = []

        class _Inbound:
            external_user_id = "628100000@s.whatsapp.net"
            external_chat_id = "120363011111111111@g.us"
            text = "@bot hello"
            metadata = {
                "raw": {
                    "id": "stanza1",
                    "participant": "628100000@s.whatsapp.net",
                    "pushName": "Ops",
                }
            }

        pub = WhatsappTurnProgressPublisher(
            enqueue=lambda t, m: sent.append((t, m)),
            lang="zh",
            is_group=True,
            inbound=_Inbound(),
            min_interval_sec=1.0,
            enabled=True,
        )
        pub.on_tool_ui("tool_use_call", {"tool_name": "ume_alarm_xlsx_report"})
        self.assertEqual(len(sent), 1)
        meta = sent[0][1] or {}
        self.assertTrue(meta.get("mention_jids"))
        self.assertNotIn("quote_stanza_id", meta)


class _FakeTurn:
    def __init__(self, text: str = "final answer") -> None:
        self.reply_text = text
        self.turn_uuid = "turn-1"


class WhatsappInboundProgressWiringTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self._tmp.name) / "wa_progress.sqlite"
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

    def _payload(self) -> dict:
        return {
            "channel": "whatsapp",
            "account_id": "wa-default",
            "user_id": "628100000@s.whatsapp.net",
            "chat_id": "120363011111111111@g.us",
            "text": "@bot run cli",
            "is_group": True,
            "mentions": ["bot@s.whatsapp.net"],
            "metadata": {
                "bot_jid": "bot@s.whatsapp.net",
                "mentions_bot": True,
                "group_name": "AI nms",
                "raw": {
                    "id": "stanza-progress",
                    "participant": "628100000@s.whatsapp.net",
                    "pushName": "Egista",
                },
            },
        }

    def test_handle_turn_progress_enqueues_inbound_progress(self) -> None:
        captured: dict[str, Any] = {}

        def _handle_turn(**kwargs: Any) -> _FakeTurn:
            captured.update(kwargs)
            on_tool_ui = kwargs.get("on_tool_ui")
            if callable(on_tool_ui):
                on_tool_ui("tool_use_call", {"tool_name": "mcp__netx__execManagedNe"})
            return _FakeTurn("cli done")

        with mock.patch.multiple(
            inbound_mod,
            get_assistant_store=mock.MagicMock(return_value=self.store),
            _build_admin_gateway_executor=mock.MagicMock(return_value=object()),
            _resolve_channel_dispatch=mock.MagicMock(return_value=("expert", "ops", "zh")),
        ), mock.patch("runtime.gateway.OclawGateway") as gw_cls, mock.patch(
            "runtime.orchestration.group_ingest.should_process_group_inbound",
            return_value=True,
        ), mock.patch(
            "runtime.application.gateway.whatsapp_inbound_access.handle_whatsapp_access",
            return_value=None,
        ), mock.patch.dict(
            "os.environ",
            {"OCLAW_WHATSAPP_TURN_PROGRESS": "1", "OCLAW_WHATSAPP_INBOUND_QUEUE_DELIVERY": "1"},
            clear=False,
        ):
            gw = gw_cls.return_value
            gw.handle_turn.side_effect = lambda **kw: _handle_turn(**kw)
            out = inbound_mod.process_inbound_payload(self._payload())

        self.assertEqual(out.get("delivery"), "queued")
        self.assertTrue(callable(captured.get("on_progress")))
        self.assertTrue(callable(captured.get("on_tool_ui")))
        pending = self.store.list_pending_channel_outbound_messages(
            channel="whatsapp", account_id="wa-default", limit=10
        )
        kinds = [json.loads(str(p.get("source") or "{}")).get("kind") for p in pending]
        self.assertIn("inbound_progress", kinds)
        self.assertIn("inbound_reply", kinds)
        progress_rows = [p for p, k in zip(pending, kinds) if k == "inbound_progress"]
        self.assertTrue(progress_rows)
        self.assertIn("设备", str(progress_rows[0].get("text") or ""))
        progress_src = json.loads(str(progress_rows[0].get("source") or "{}"))
        self.assertTrue(progress_src.get("mention_jids"))
        self.assertFalse(progress_src.get("quote_stanza_id"))


if __name__ == "__main__":
    unittest.main()
