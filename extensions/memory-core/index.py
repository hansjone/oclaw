from __future__ import annotations

from oclaw.extensions.plugin_api import PluginEntry, define_plugin_entry

PLUGIN_ID = "memory-core"
PLUGIN_NAME = "Memory (Core)"


def register_memory_core_plugin(api) -> None:
    if hasattr(api, "register_tool"):
        api.register_tool({"name": "memory_search"})
        api.register_tool({"name": "memory_get"})


def build_memory_core_plugin_entry() -> PluginEntry:
    return define_plugin_entry(
        id=PLUGIN_ID,
        name=PLUGIN_NAME,
        description="File-backed memory search tools and CLI",
        register=register_memory_core_plugin,
    )


plugin_entry = build_memory_core_plugin_entry()
