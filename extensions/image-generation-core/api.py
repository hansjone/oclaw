from __future__ import annotations

from typing import Any

def _runtime_get(runtime: Any, key: str):
    if isinstance(runtime, dict):
        return runtime.get(key)
    return getattr(runtime, key, None)


def list_runtime_image_generation_providers(runtime: Any = None) -> list[dict]:
    providers = _runtime_get(runtime, "image_generation_providers")
    if isinstance(providers, list):
        return [p for p in providers if isinstance(p, dict)]
    return []

def generate_image(*, prompt: str, provider_id: str | None = None, runtime: Any = None, **kwargs) -> dict:
    providers = list_runtime_image_generation_providers(runtime)
    if not providers:
        return {"ok": False, "error": "no_image_generation_provider_registered"}

    chosen = None
    if provider_id:
        chosen = next((p for p in providers if str(p.get("id")) == provider_id), None)
    if chosen is None:
        chosen = providers[0]

    generator = chosen.get("generate")
    if callable(generator):
        result = generator(prompt=prompt, **kwargs)
        if isinstance(result, dict):
            return {"ok": True, "provider": chosen.get("id"), **result}
        return {"ok": True, "provider": chosen.get("id"), "result": result}

    return {
        "ok": True,
        "provider": chosen.get("id"),
        "prompt": prompt,
        "note": "provider_has_no_generate_callable",
    }
