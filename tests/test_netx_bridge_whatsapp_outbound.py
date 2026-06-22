from __future__ import annotations

import asyncio
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from interfaces.http.fastapi_app import create_app
from svc.persistence.assistant_store import reset_assistant_store_singleton


class NetxBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["OCLAW_NETX_BRIDGE_TOKEN"] = "test-bridge-token"
        os.environ.pop("OCLAW_OPS_AI_SHARED_TOKEN", None)
        os.environ["AIA_WHATSAPP_ACCOUNT_ID"] = "wa-default"
        reset_assistant_store_singleton()
        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        reset_assistant_store_singleton()

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
