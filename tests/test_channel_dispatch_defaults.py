from __future__ import annotations

from runtime.application.gateway.inbound_service import (
    _resolve_channel_dispatch,
)


class _DummyStore:
    def __init__(self, data: dict[str, str] | None = None) -> None:
        self._data = dict(data or {})

    def get_setting(self, key: str) -> str:
        return str(self._data.get(key) or "")


def test_channel_dispatch_defaults_to_expert_and_generalist() -> None:
    store = _DummyStore()
    interaction_mode, specialist, lang = _resolve_channel_dispatch(store, channel="weixin", account=None)
    assert interaction_mode == "expert"
    assert specialist == "generalist"
    assert lang == "auto"


def test_channel_dispatch_uses_global_settings() -> None:
    store = _DummyStore(
        {
            "channel.dispatch.interaction_mode.whatsapp": "comprehensive",
            "channel.dispatch.specialist.whatsapp": "ops",
            "channel.dispatch.lang.whatsapp": "en",
        }
    )
    interaction_mode, specialist, lang = _resolve_channel_dispatch(store, channel="whatsapp", account=None)
    assert interaction_mode == "comprehensive"
    assert specialist == "ops"
    assert lang == "en"


def test_channel_dispatch_account_config_overrides_global() -> None:
    store = _DummyStore(
        {
            "channel.dispatch.interaction_mode.weixin": "comprehensive",
            "channel.dispatch.specialist.weixin": "ops",
            "channel.dispatch.lang.weixin": "zh",
        }
    )
    account = {
        "config": {
            "interaction_mode": "expert",
            "specialist": "generalist",
            "lang": "en",
        }
    }
    interaction_mode, specialist, lang = _resolve_channel_dispatch(store, channel="weixin", account=account)
    assert interaction_mode == "expert"
    assert specialist == "generalist"
    assert lang == "en"

