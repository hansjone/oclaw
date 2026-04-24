from __future__ import annotations

from .api import build_anthropic_provider
from oclaw.runtime.extensions.plugin_api import PluginEntry, define_plugin_entry


PLUGIN_ID = "anthropic"
PLUGIN_NAME = "Anthropic Provider"
PLUGIN_DESCRIPTION = "Bundled Anthropic provider plugin"


def register_anthropic_plugin(api) -> None:
    provider = build_anthropic_provider(api)
    if provider is not None and hasattr(api, "register_provider"):
        api.register_provider(provider)


def build_anthropic_plugin_entry() -> PluginEntry:
    return define_plugin_entry(
        id=PLUGIN_ID,
        name=PLUGIN_NAME,
        description=PLUGIN_DESCRIPTION,
        register=register_anthropic_plugin,
    )


plugin_entry = build_anthropic_plugin_entry()
