from __future__ import annotations

from .api import (
    build_openai_codex_provider,
    build_openai_image_generation_provider,
    build_openai_provider,
)
from oclaw.extensions.plugin_api import PluginEntry, define_plugin_entry


def register_openai_plugin(api) -> None:
    if hasattr(api, "register_provider"):
        api.register_provider(build_openai_provider())
        api.register_provider(build_openai_codex_provider())
    if hasattr(api, "register_image_generation_provider"):
        api.register_image_generation_provider(build_openai_image_generation_provider())


def build_openai_plugin_entry() -> PluginEntry:
    return define_plugin_entry(
        id="openai",
        name="OpenAI Provider",
        description="Bundled OpenAI provider plugins",
        register=register_openai_plugin,
    )


plugin_entry = build_openai_plugin_entry()
