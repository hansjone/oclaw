from __future__ import annotations

from .api import QWEN_BASE_URL, build_qwen_provider
from oclaw.runtime.extensions.plugin_api import PluginEntry, define_plugin_entry

PROVIDER_ID = "qwen"


def register_qwen_plugin(api) -> None:
    if hasattr(api, "register_provider"):
        api.register_provider(build_qwen_provider(base_url=QWEN_BASE_URL))


def build_qwen_plugin_entry() -> PluginEntry:
    return define_plugin_entry(
        id=PROVIDER_ID,
        name="Qwen Provider",
        description="Bundled Qwen Cloud provider plugin",
        register=register_qwen_plugin,
    )


plugin_entry = build_qwen_plugin_entry()
