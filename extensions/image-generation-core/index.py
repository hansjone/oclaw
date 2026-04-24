from __future__ import annotations

from oclaw.extensions.plugin_api import PluginEntry, define_plugin_entry

from .api import list_runtime_image_generation_providers


def register_image_generation_core_plugin(api) -> None:
    providers = list_runtime_image_generation_providers(getattr(api, "runtime", None))
    if not providers and hasattr(api, "register_tool"):
        api.register_tool({"name": "generate_image"})


def build_image_generation_core_plugin_entry() -> PluginEntry:
    return define_plugin_entry(
        id="image-generation-core",
        name="Image Generation Core",
        description="Runtime image generation helper APIs",
        register=register_image_generation_core_plugin,
    )


plugin_entry = build_image_generation_core_plugin_entry()
