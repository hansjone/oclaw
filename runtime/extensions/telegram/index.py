from __future__ import annotations

from runtime.extensions.plugin_api import PluginEntry


def register_telegram_channel(api) -> None:
    """Telegram channel removed from product surface; keep normalize helpers only."""
    del api


def build_telegram_plugin_entry() -> PluginEntry:
    return PluginEntry(
        id="telegram",
        name="Telegram (disabled)",
        description="Removed from product surface; outbound normalize helpers remain.",
        register=register_telegram_channel,
    )


plugin_entry = build_telegram_plugin_entry()
