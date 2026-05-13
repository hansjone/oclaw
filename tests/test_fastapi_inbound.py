from __future__ import annotations

from fastapi.testclient import TestClient

from interfaces.http.fastapi_app import create_app


def test_inbound_route_uses_given_channel() -> None:
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    r = client.post("/inbound", json={"channel": "bad", "text": "x"})
    assert r.status_code == 500
    assert "Internal Server Error" in r.text


def test_wecom_inbound_overrides_channel() -> None:
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    r = client.post("/wecom/inbound", json={"channel": "bad", "text": "x", "user_id": "u1"})
    assert r.status_code == 500
    assert "Internal Server Error" in r.text
