from __future__ import annotations

from dataclasses import dataclass

from oclaw.runtime.application.gateway.inbound_service import (
    _collect_reply_attachments_from_history,
    _collect_recent_tool_attachments,
    _maybe_add_media_path_for_wechat_reply,
    _maybe_expand_reply_attachments_for_channel,
    _parse_message_attachments,
    _should_suppress_channel_reply,
)


def test_should_suppress_weixin_openai_missing_api_key_message() -> None:
    text = '⚠️ Missing API key for provider "openai". Configure the gateway auth for that provider, then try again.'
    assert _should_suppress_channel_reply(channel="wechat", text=text) is True
    assert _should_suppress_channel_reply(channel="weixin", text=text) is True


def test_should_not_suppress_non_weixin_channel() -> None:
    text = '⚠️ Missing API key for provider "openai". Configure the gateway auth for that provider, then try again.'
    assert _should_suppress_channel_reply(channel="admin_chat", text=text) is False


def test_parse_message_attachments_accepts_json_string() -> None:
    out = _parse_message_attachments('[{"type":"image_ref","attachment_id":"a1"}]')
    assert len(out) == 1
    assert out[0].get("attachment_id") == "a1"


@dataclass
class _Row:
    role: str
    content: str
    attachments: object


class _FakeStore:
    def __init__(self, rows: list[_Row]) -> None:
        self._rows = rows

    def get_messages(self, *, session_id: str, limit: int = 120) -> list[_Row]:
        _ = (session_id, limit)
        return list(self._rows)


def test_collect_reply_attachments_prefers_matching_assistant_text() -> None:
    rows = [
        _Row(role="assistant", content="old", attachments='[{"attachment_id":"old"}]'),
        _Row(role="assistant", content="target", attachments='[{"attachment_id":"new"}]'),
    ]
    out = _collect_reply_attachments_from_history(store=_FakeStore(rows), session_id="s1", reply_text="target")
    assert len(out) == 1
    assert out[0].get("attachment_id") == "new"


def test_collect_recent_tool_attachments_falls_back_to_tool_media() -> None:
    rows = [
        _Row(role="assistant", content="x", attachments=None),
        _Row(role="tool", content="{}", attachments='[{"type":"image_ref","attachment_id":"a1"}]'),
    ]
    out = _collect_recent_tool_attachments(store=_FakeStore(rows), session_id="s1")
    assert len(out) == 1
    assert out[0].get("attachment_id") == "a1"


def test_maybe_add_media_path_for_wechat_reply_sets_media_path(monkeypatch) -> None:
    # Avoid touching disk: stub AttachmentAssetStore.get_local_path.
    from pathlib import Path

    def _fake_get_local_path(self, attachment_id: str):  # noqa: ANN001
        assert attachment_id == "a1"
        return Path("D:/tmp/fake.png")

    monkeypatch.setattr(
        "oclaw.platform.files.attachment_assets.AttachmentAssetStore.get_local_path",
        _fake_get_local_path,
    )
    r = {"channel": "wechat", "text": "hi", "attachments": [{"type": "image_ref", "attachment_id": "a1"}]}
    _maybe_add_media_path_for_wechat_reply(r)
    assert r.get("media_path") in {"D:/tmp/fake.png", "D:\\tmp\\fake.png"}


def test_maybe_expand_reply_attachments_for_channel_converts_ref_to_base64(monkeypatch) -> None:
    import base64

    class _Meta:
        mime = "image/png"
        name = "x.png"

    def _fake_load_bytes(self, attachment_id: str):  # noqa: ANN001
        assert attachment_id == "a1"
        return b"abc", _Meta()

    monkeypatch.setattr(
        "oclaw.platform.files.attachment_assets.AttachmentAssetStore.load_bytes",
        _fake_load_bytes,
    )
    r = {"channel": "wechat", "attachments": [{"type": "image_ref", "attachment_id": "a1"}]}
    _maybe_expand_reply_attachments_for_channel(r)
    out = r.get("attachments")
    assert isinstance(out, list) and len(out) == 1
    assert out[0].get("data_base64") == base64.b64encode(b"abc").decode("ascii")
    assert out[0].get("mime") == "image/png"


def test_maybe_expand_reply_attachments_for_channel_works_for_whatsapp(monkeypatch) -> None:
    import base64

    class _Meta:
        mime = "image/png"
        name = "wa.png"

    def _fake_load_bytes(self, attachment_id: str):  # noqa: ANN001
        assert attachment_id == "wa1"
        return b"wa", _Meta()

    monkeypatch.setattr(
        "oclaw.platform.files.attachment_assets.AttachmentAssetStore.load_bytes",
        _fake_load_bytes,
    )
    r = {"channel": "whatsapp", "attachments": [{"type": "image_ref", "attachment_id": "wa1"}]}
    _maybe_expand_reply_attachments_for_channel(r)
    out = r.get("attachments")
    assert isinstance(out, list) and len(out) == 1
    assert out[0].get("data_base64") == base64.b64encode(b"wa").decode("ascii")

