from __future__ import annotations

from interfaces.gateway.server_methods.telegram_send_normalize import normalize_transport_target_for_channel


def test_normalize_transport_target_for_channel_non_telegram_passthrough() -> None:
    to, extra = normalize_transport_target_for_channel(
        channel="discord",
        to="room-1",
        params={},
    )
    assert to == "room-1"
    assert extra == {}


def test_normalize_transport_target_for_channel_handles_topic_target() -> None:
    to, extra = normalize_transport_target_for_channel(
        channel="telegram",
        to="telegram:group:-100123:topic:88",
        params={"replyToId": "9"},
    )
    assert to == "telegram:group:-100123:topic:88"
    target = extra.get("target") or {}
    assert target.get("chatId") == "-100123"
    assert target.get("chatType") == "group"
    assert target.get("messageThreadId") == 88
    assert extra.get("threadId") == 88
    assert extra.get("replyToMessageId") == 9


def test_normalize_transport_target_for_channel_supports_username_lookup_targets() -> None:
    to, extra = normalize_transport_target_for_channel(
        channel="telegram",
        to="@MyUser_01",
        params={},
    )
    assert to == "telegram:@myuser_01"
    target = extra.get("target") or {}
    assert target.get("chatId") == "@myuser_01"
    assert target.get("chatType") == "unknown"
    assert "threadId" not in extra


def test_normalize_transport_target_for_channel_uses_explicit_thread_id_override() -> None:
    to, extra = normalize_transport_target_for_channel(
        channel="telegram",
        to="telegram:-100500:topic:2",
        params={"threadId": "99"},
    )
    assert to == "telegram:-100500:topic:2"
    assert extra.get("threadId") == 99
    target = extra.get("target") or {}
    # parsed target remains the source target
    assert target.get("messageThreadId") == 2

