from __future__ import annotations

from oclaw.extensions.plugin_api import PluginEntry, define_plugin_entry
from .api import build_plugin_config_schema, build_wiki_tool_specs


def register_memory_wiki_plugin(api) -> None:
    if hasattr(api, "register_tool"):
        for tool in build_wiki_tool_specs(api):
            api.register_tool(tool)


def build_memory_wiki_plugin_entry() -> PluginEntry:
    entry = define_plugin_entry(
        id="memory-wiki",
        name="Memory Wiki",
        description="Persistent wiki compiler and Obsidian-friendly knowledge vault for OpenClaw.",
        register=register_memory_wiki_plugin,
    )
    # Best-effort compatibility for loaders that read config schema from entry object.
    try:
        object.__setattr__(entry, "config_schema", build_plugin_config_schema())
    except Exception:
        pass
    return entry


plugin_entry = build_memory_wiki_plugin_entry()
