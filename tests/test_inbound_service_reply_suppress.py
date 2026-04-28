from __future__ import annotations

from oclaw.runtime.application.gateway.inbound_service import _should_suppress_channel_reply


def test_should_suppress_weixin_openai_missing_api_key_message() -> None:
    text = '⚠️ Missing API key for provider "openai". Configure the gateway auth for that provider, then try again.'
    assert _should_suppress_channel_reply(channel="wechat", text=text) is True
    assert _should_suppress_channel_reply(channel="weixin", text=text) is True


def test_should_not_suppress_non_weixin_channel() -> None:
    text = '⚠️ Missing API key for provider "openai". Configure the gateway auth for that provider, then try again.'
    assert _should_suppress_channel_reply(channel="admin_chat", text=text) is False

