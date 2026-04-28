from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from oclaw.interfaces.http.fastapi_app import create_app
from oclaw.interfaces.http import weixin_ilink_api


class WeixinIlinkApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_app())
        self.headers = {
            "AuthorizationType": "ilink_bot_token",
            "Authorization": "Bearer test-ilink-token",
        }

    def test_sendmessage_requires_account_id(self) -> None:
        r = self.client.post(
            "/ilink/bot/sendmessage",
            headers=self.headers,
            json={
                "channel": "wechat",
                "user_id": "wxid_u1",
                "text": "hello",
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual((r.json() or {}).get("ret"), 400)

    def test_sendmessage_enqueues_reply_for_getupdates(self) -> None:
        old_usecase = weixin_ilink_api.process_inbound_payload_usecase

        def _fake_usecase(payload: dict[str, object]) -> dict[str, object]:
            text = str(payload.get("text") or "")
            return {
                "ok": True,
                "replies": [
                    {
                        "chat_id": str(payload.get("chat_id") or ""),
                        "text": f"echo:{text}",
                    }
                ],
            }

        try:
            weixin_ilink_api.process_inbound_payload_usecase = _fake_usecase  # type: ignore[assignment]
            s = self.client.post(
                "/ilink/bot/sendmessage",
                headers=self.headers,
                json={
                    "channel": "wechat",
                    "account_id": "bot-1",
                    "user_id": "wxid_u2",
                    "chat_id": "room_1",
                    "text": "ping",
                },
            )
            self.assertEqual(s.status_code, 200, s.text)
            self.assertEqual((s.json() or {}).get("ret"), 0)

            g = self.client.post(
                "/ilink/bot/getupdates",
                headers=self.headers,
                json={
                    "channel": "wechat",
                    "account_id": "bot-1",
                    "get_updates_buf": "0",
                    "longpolling_timeout_ms": 1000,
                },
            )
            self.assertEqual(g.status_code, 200, g.text)
            data = g.json() or {}
            self.assertEqual(data.get("ret"), 0)
            msgs = data.get("msgs") if isinstance(data.get("msgs"), list) else []
            self.assertTrue(msgs, data)
            self.assertEqual(str((msgs[0] or {}).get("text") or ""), "echo:ping")
        finally:
            weixin_ilink_api.process_inbound_payload_usecase = old_usecase  # type: ignore[assignment]


if __name__ == "__main__":
    unittest.main()
