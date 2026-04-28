from __future__ import annotations

from fastapi.testclient import TestClient

from oclaw.interfaces.http.fastapi_app import create_app
from oclaw.interfaces.http import fastapi_app


def test_inbound_whatsapp_accepts_basic_payload_and_returns_replies() -> None:
    client = TestClient(create_app())
    old_usecase = fastapi_app.process_inbound_payload_usecase

    def _fake_usecase(payload: dict[str, object]) -> dict[str, object]:
        assert str(payload.get("channel") or "") == "whatsapp"
        assert str(payload.get("account_id") or "") == "wa-default"
        assert str(payload.get("user_id") or "") == "111@s.whatsapp.net"
        assert str(payload.get("chat_id") or "") == "111@s.whatsapp.net"
        return {"ok": True, "replies": [{"chat_id": payload.get("chat_id"), "text": "ok"}]}

    try:
        fastapi_app.process_inbound_payload_usecase = _fake_usecase  # type: ignore[assignment]
        r = client.post(
            "/inbound/whatsapp",
            json={
                "account_id": "wa-default",
                "user_id": "111@s.whatsapp.net",
                "chat_id": "111@s.whatsapp.net",
                "text": "hello",
                "metadata": {"source": "test"},
            },
        )
        assert r.status_code == 200, r.text
        data = r.json() or {}
        assert data.get("ok") is True
        replies = data.get("replies") if isinstance(data.get("replies"), list) else []
        assert replies and isinstance(replies[0], dict)
        assert str(replies[0].get("text") or "") == "ok"
    finally:
        fastapi_app.process_inbound_payload_usecase = old_usecase  # type: ignore[assignment]

