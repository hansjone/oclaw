from __future__ import annotations

from .api import telegram_plugin
from runtime.extensions.plugin_api import PluginEntry, define_plugin_entry


def register_telegram_channel(api) -> None:
    if hasattr(api, "register_channel"):
        api.register_channel({"id": "telegram", "plugin": telegram_plugin})


def build_telegram_plugin_entry() -> PluginEntry:
    return define_plugin_entry(
        id="telegram",
        name="Telegram",
        description="Telegram channel plugin",
        register=register_telegram_channel,
    )


plugin_entry = build_telegram_plugin_entry()
