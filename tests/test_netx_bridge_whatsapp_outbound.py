from __future__ import annotations

import asyncio
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from interfaces.http.fastapi_app import create_app
from interfaces.ws.netx_bridge import _format_alarm_text
from svc.persistence.assistant_store import reset_assistant_store_singleton


class NetxBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["OCLAW_OPS_AI_SHARED_TOKEN"] = "test-bridge-token"
        os.environ.pop("OCLAW_NETX_BRIDGE_TOKEN", None)
        os.environ["AIA_WHATSAPP_ACCOUNT_ID"] = "wa-default"
        reset_assistant_store_singleton()
        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        reset_assistant_store_singleton()

    def test_format_alarm_text_english(self) -> None:
        text = _format_alarm_text(
            {
                "action": "inserted",
                "rule_label": "Fan",
                "object_name": "ME{abc},FAN={/module=0}",
                "perceived_severity": "major",
                "native_probable_cause": "Fan The fan speed level is abnormally high",
                "time_created": "2026-06-22T19:29:41.086+07:00",
                "notification_id": "1680996323029",
                "ne": {"host_name": "LPG-BKM-AN1-ZM3SP", "ip_address": "114.0.24.178"},
            }
        )
        self.assertIn("[UME Alarm Raised] Fan", text)
        self.assertIn("Device: LPG-BKM-AN1-ZM3SP (114.0.24.178)", text)
        self.assertIn("Severity: major", text)
        self.assertNotIn("设备", text)
        self.assertNotIn("NetX", text)

    def test_netx_bridge_auth_and_alarm_ack(self) -> None:
        with self.client.websocket_connect("/ws/netx-bridge") as ws:
            ws.send_json({"type": "auth", "token": "bad"})
            msg = ws.receive_json()
            self.assertEqual(msg.get("type"), "auth-fail")

        with self.client.websocket_connect("/ws/netx-bridge") as ws:
            ws.send_json({"type": "auth", "token": "test-bridge-token"})
            msg = ws.receive_json()
            self.assertEqual(msg.get("type"), "auth-ok")
            ws.send_json(
                {
                    "type": "event",
                    "event": "netx.alarm",
                    "payload": {
                        "action": "inserted",
                        "alarm_key": "AK-1",
                        "notification_id": "NID-1",
                        "native_probable_cause": "link down",
                        "perceived_severity": "critical",
                        "ne": {"host_name": "host-a", "ip_address": "10.0.0.1"},
                    },
                }
            )
            ack = ws.receive_json()
            self.assertEqual(ack.get("type"), "ack")
            self.assertEqual(ack.get("alarm_key"), "AK-1")
            self.assertFalse(ack.get("ok"))

    def test_whatsapp_outbound_pending_empty(self) -> None:
        resp = self.client.get("/whatsapp/outbound/pending?account_id=wa-default")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body.get("ok"))
        self.assertEqual(body.get("items"), [])


if __name__ == "__main__":
    unittest.main()
