from __future__ import annotations

import importlib.util
from pathlib import Path

from oclaw.gateway.server_plugins import load_gateway_plugins


def _load_image_core_generate_image():
    file_path = (Path(__file__).resolve().parents[1] / "extensions" / "image-generation-core" / "api.py").resolve()
    spec = importlib.util.spec_from_file_location("test_image_generation_core_api", str(file_path))
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load image-generation-core api module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "generate_image")


def test_openai_registers_image_generation_provider_in_gateway_registry() -> None:
    out = load_gateway_plugins(
        cfg={"plugins": {"enabled": ["openai"]}},
        workspace_dir=".",
        log={},
        core_gateway_handlers={},
        base_methods=["ping"],
    )
    providers = out.plugin_registry.get("image_generation_providers") or []
    assert isinstance(providers, list)
    assert any(isinstance(p, dict) and p.get("id") == "openai" for p in providers)


def test_image_generation_core_uses_registered_openai_provider() -> None:
    out = load_gateway_plugins(
        cfg={"plugins": {"enabled": ["openai"]}},
        workspace_dir=".",
        log={},
        core_gateway_handlers={},
        base_methods=["ping"],
    )
    runtime = {"image_generation_providers": out.plugin_registry.get("image_generation_providers") or []}
    generate_image = _load_image_core_generate_image()
    result = generate_image(prompt="sunset over city", provider_id="openai", runtime=runtime, size="1024x1024")
    assert result.get("ok") is True
    assert result.get("provider") == "openai"
    assert result.get("model") == "gpt-image-1"
    assert result.get("prompt") == "sunset over city"
    assert result.get("size") == "1024x1024"

