from __future__ import annotations

from ..api import PluginApi, PluginEntry, define_plugin_entry
from .index import register_webhook_routes


def build_webhooks_plugin_entry() -> PluginEntry:
    return define_plugin_entry(
        id="webhooks",
        name="Webhooks",
        description="Authenticated inbound webhooks that bind external automation to Oclaw TaskFlows.",
        register=lambda api: register_webhook_routes(api),
    )


__all__ = ["PluginApi", "PluginEntry", "build_webhooks_plugin_entry", "define_plugin_entry"]

