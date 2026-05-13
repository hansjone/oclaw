from __future__ import annotations

from .api import build_deepseek_provider
from runtime.extensions.plugin_api import PluginEntry, define_plugin_entry

PROVIDER_ID = "deepseek"


def register_deepseek_plugin(api) -> None:
    if hasattr(api, "register_provider"):
        api.register_provider(
            {
                "id": PROVIDER_ID,
                "label": "DeepSeek",
                "provider": build_deepseek_provider(),
            }
        )


def build_deepseek_plugin_entry() -> PluginEntry:
    return define_plugin_entry(
        id=PROVIDER_ID,
        name="DeepSeek Provider",
        description="Bundled DeepSeek provider plugin",
        register=register_deepseek_plugin,
    )


plugin_entry = build_deepseek_plugin_entry()
