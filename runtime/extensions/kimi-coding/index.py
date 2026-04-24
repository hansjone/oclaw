from __future__ import annotations

from .api import build_kimi_coding_provider
from oclaw.runtime.extensions.plugin_api import PluginEntry, define_plugin_entry

PLUGIN_ID = "kimi"


def register_kimi_plugin(api) -> None:
    if hasattr(api, "register_provider"):
        api.register_provider(build_kimi_coding_provider())


def build_kimi_plugin_entry() -> PluginEntry:
    return define_plugin_entry(
        id=PLUGIN_ID,
        name="Kimi Provider",
        description="Bundled Kimi provider plugin",
        register=register_kimi_plugin,
    )


plugin_entry = build_kimi_plugin_entry()
