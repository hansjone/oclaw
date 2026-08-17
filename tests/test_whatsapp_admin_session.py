from __future__ import annotations

import json
from pathlib import Path

from runtime.operations import whatsapp_sidecar as wa


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_whatsapp_bridge_writes_status_module() -> None:
    text = (REPO_ROOT / "runtime/operations/whatsapp_bridge/baileys_runner.ts").read_text(encoding="utf-8")
    assert "writeBridgeStatus" in text
    assert 'from "./status"' in text
    assert "writeQrImage" in text
    status = (REPO_ROOT / "runtime/operations/whatsapp_bridge/status.ts").read_text(encoding="utf-8")
    assert "bridge_status.json" in status


def test_whatsapp_install_copies_status_and_qrcode_pkg() -> None:
    text = (REPO_ROOT / "runtime/operations/scripts/whatsapp_install.ps1").read_text(encoding="utf-8")
    assert "status.ts" in text
    assert "qrcode@$qrcodeVersion" in text
    start = (REPO_ROOT / "runtime/operations/scripts/whatsapp_start.ps1").read_text(encoding="utf-8")
    assert "status.ts" in start


def test_whatsapp_session_status_unbound(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(wa, "PROJECT_ROOT", tmp_path)
    root = tmp_path / "data" / "channel_sidecar" / "whatsapp"
    root.mkdir(parents=True)
    (root / "baileys_runner.ts").write_text("// stub\n", encoding="utf-8")
    st = wa.session_status(channel_id="whatsapp")
    assert st["ok"] is True
    assert st["installed"] is True
    assert st["bound"] is False
    assert st["lifecycle"] == "unbound"
    assert st["sidecar_running"] is False


def test_whatsapp_session_status_bound_offline(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(wa, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(wa, "is_pid_running", lambda pid: True)
    root = tmp_path / "data" / "channel_sidecar" / "whatsapp"
    state = root / "state"
    auth = state / "auth"
    auth.mkdir(parents=True)
    (root / "baileys_runner.ts").write_text("// stub\n", encoding="utf-8")
    (root / "pid.txt").write_text("4242\n", encoding="utf-8")
    (auth / "creds.json").write_text(
        json.dumps({"me": {"id": "8615601877957:4@s.whatsapp.net", "name": "oclaw"}}),
        encoding="utf-8",
    )
    (state / "bridge_status.json").write_text(
        json.dumps(
            {
                "connection": "close",
                "me": "8615601877957:4@s.whatsapp.net",
                "phone": "8615601877957",
                "reconnect_attempt": 12,
                "last_error": "Connection was lost",
                "updated_at": "2026-08-13T09:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    st = wa.session_status(channel_id="whatsapp")
    assert st["bound"] is True
    assert st["sidecar_running"] is True
    assert st["lifecycle"] == "bound_offline"
    assert st["phone"] == "8615601877957"
    assert st["reconnect_attempt"] == 12


def test_whatsapp_unbind_removes_auth(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(wa, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(wa, "stop_sidecar", lambda channel_id="whatsapp", force=True: {"ok": True, "action": "stop"})
    root = tmp_path / "data" / "channel_sidecar" / "whatsapp"
    auth = root / "state" / "auth"
    auth.mkdir(parents=True)
    (auth / "creds.json").write_text("{}", encoding="utf-8")
    (root / "state" / "qr.png").write_bytes(b"png")
    out = wa.unbind_session(channel_id="whatsapp")
    assert out["ok"] is True
    assert out["removed_auth"] is True
    assert not auth.exists()
    assert out["status"]["lifecycle"] == "unbound"


def test_whatsapp_session_status_needs_rebind_on_405(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(wa, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(wa, "is_pid_running", lambda pid: True)
    root = tmp_path / "data" / "channel_sidecar" / "whatsapp"
    state = root / "state"
    auth = state / "auth"
    auth.mkdir(parents=True)
    (root / "baileys_runner.ts").write_text("// stub\n", encoding="utf-8")
    (root / "pid.txt").write_text("4242\n", encoding="utf-8")
    (auth / "creds.json").write_text(
        json.dumps({"me": {"id": "8615601877957:4@s.whatsapp.net", "name": "oclaw"}}),
        encoding="utf-8",
    )
    (state / "bridge_status.json").write_text(
        json.dumps(
            {
                "connection": "close",
                "me": "8615601877957@s.whatsapp.net",
                "phone": "8615601877957",
                "last_disconnect_status": 405,
                "last_error": "Error: Connection Failure",
                "updated_at": "2026-08-17T13:50:57.152Z",
            }
        ),
        encoding="utf-8",
    )
    st = wa.session_status(channel_id="whatsapp")
    assert st["lifecycle"] == "needs_rebind"
    assert st["status_hint"] == "session_invalid_need_rebind"


def test_qr_to_data_url_generates_png() -> None:
    url = wa._qr_to_data_url("2@testqr")
    assert url.startswith("data:image/png;base64,")


def test_admin_routes_expose_whatsapp_session_apis() -> None:
    text = (REPO_ROOT / "interfaces/admin/routes.py").read_text(encoding="utf-8")
    assert '/admin/api/whatsapp/session"' in text
    assert "/admin/api/whatsapp/session/start" in text
    assert "/admin/api/whatsapp/session/stop" in text
    assert "/admin/api/whatsapp/session/unbind" in text
    assert "/admin/api/whatsapp/session/bind" in text
    stack = (REPO_ROOT / "interfaces/admin/static/js/pages/stack.js").read_text(encoding="utf-8")
    assert "/admin/api/whatsapp/session" in stack
    assert "whatsappSessionCard" in stack
    assert "pollWaSession" in stack
    runner = (REPO_ROOT / "runtime/operations/whatsapp_bridge/baileys_runner.ts").read_text(encoding="utf-8")
    assert "needs_rebind" in runner
