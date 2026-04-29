from __future__ import annotations

from dataclasses import dataclass

from oclaw.runtime.application.gateway.inbound_service import (
    _collect_reply_attachments_from_history,
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

