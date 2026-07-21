from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def test_whatsapp_ops_scripts_exist_and_use_openclaw() -> None:
    for rel in (
        "runtime/operations/scripts/whatsapp_install.ps1",
        "runtime/operations/scripts/whatsapp_login.ps1",
        "runtime/operations/scripts/whatsapp_start.ps1",
        "runtime/operations/scripts/whatsapp_status.ps1",
        "runtime/operations/scripts/whatsapp_stop.ps1",
    ):
        text = _read(rel)
        assert "openclaw" not in text.lower()
    start_text = _read("runtime/operations/scripts/whatsapp_start.ps1")
    assert "baileys_runner.ts" in start_text
    assert "AIA_GATEWAY_BASE_URL" in start_text


def test_runbook_mentions_whatsapp_scripts() -> None:
    text = _read("docs/RUNBOOK.md")
    assert "whatsapp_install.ps1" in text
    assert "whatsapp_login.ps1" in text
    assert "whatsapp_start.ps1" in text
    assert "/inbound/whatsapp" in text


def test_start_all_gracefully_skips_missing_channel_sidecars() -> None:
    text = _read("runtime/operations/scripts/start_all.ps1")
    assert 'Warn "weixin sidecar skipped:' in text
    assert 'Warn "whatsapp sidecar skipped:' in text


def test_whatsapp_runner_outbound_poll_uses_reply_attachments() -> None:
    text = _read("runtime/operations/whatsapp_bridge/baileys_runner.ts")
    assert "sendReplyWithAttachments" in text
    assert "hasMedia" in text
    assert "pollOutboundQueue" in text
    poll_start = text.index("async function pollOutboundQueue")
    poll_chunk = text[poll_start : poll_start + 2500]
    assert "sendReplyWithAttachments" in poll_chunk


def test_whatsapp_runner_supports_reply_attachments_base64() -> None:
    text = _read("runtime/operations/whatsapp_bridge/baileys_runner.ts")
    assert "sendReplyWithAttachments" in text
    assert "data_base64" in text
    assert "media_base64" in text
    assert "media_path" in text
    assert "media_url" in text


def test_whatsapp_runner_resolves_dm_remote_jid_alt() -> None:
    text = _read("runtime/operations/whatsapp_bridge/baileys_runner.ts")
    assert "resolveDmUserJid" in text
    assert "remoteJidAlt" in text


def test_whatsapp_runner_supports_inbound_media_download() -> None:
    text = _read("runtime/operations/whatsapp_bridge/baileys_runner.ts")
    assert "downloadMediaMessage" in text
    assert "downloadInboundAttachments" in text
    assert "local_path" in text
    assert "payload.attachments" in text
    assert "documentMessage?.caption" in text
    assert "buildOutboundMediaMessage" in text
    assert "video_base64" in text
    assert "audio_base64" in text


def test_whatsapp_runner_outbound_ack_passes_stanza_id() -> None:
    text = _read("runtime/operations/whatsapp_bridge/baileys_runner.ts")
    assert "stanza_id" in text
    assert "sent as any)?.key?.id" in text
