"""Regression: admin REST and WS share attachment normalization (typed refs must survive parsing)."""

from __future__ import annotations

from interfaces.admin.chat_api import _parse_attachments_payload


def test_parse_attachments_payload_preserves_image_ref() -> None:
    att: dict = {"type": "image_ref", "attachment_id": "a" * 64, "mime": "image/png"}
    out = _parse_attachments_payload([att])
    assert out == [att]


def test_parse_attachments_payload_preserves_relay_pointer_image() -> None:
    att: dict = {
        "type": "relay_pointer",
        "mime": "image/jpeg",
        "attachment_id": "b" * 64,
        "pointer_uri": "relay://attachments/x/" + "b" * 64,
    }
    out = _parse_attachments_payload([att])
    assert out == [att]


def test_parse_attachments_payload_empty() -> None:
    assert _parse_attachments_payload(None) is None
    assert _parse_attachments_payload([]) is None
