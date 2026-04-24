from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Callable

from .shared_types import GatewayRequestHandlers
from .validation import error_shape


def _ok(respond, payload: Any) -> None:
    if callable(respond):
        respond(True, payload, None, None)


def _bad(respond, message: str) -> None:
    if callable(respond):
        respond(False, None, error_shape("INVALID_REQUEST", message), None)


def _unavailable(respond, message: str) -> None:
    if callable(respond):
        respond(False, None, error_shape("UNAVAILABLE", message), None)


def _fail(respond, code: str, message: str) -> None:
    if callable(respond):
        respond(False, None, error_shape(code, message), None)


_generate_image_fn: Callable[..., Any] | None = None


def _load_generate_image_fn() -> Callable[..., Any]:
    global _generate_image_fn
    if _generate_image_fn is not None:
        return _generate_image_fn
    file_path = (Path(__file__).resolve().parents[2] / "extensions" / "image-generation-core" / "api.py").resolve()
    if not file_path.exists():
        # Backward compatibility for legacy layout.
        file_path = Path("extensions/image-generation-core/api.py").resolve()
    spec = importlib.util.spec_from_file_location("gateway_image_generation_core_api", str(file_path))
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load image-generation-core api module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fn = getattr(module, "generate_image", None)
    if not callable(fn):
        raise RuntimeError("image-generation-core.generate_image is not callable")
    _generate_image_fn = fn
    return fn


def _image_generate_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid image.generate params")
        return
    prompt = params.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        _bad(respond, "image.generate requires prompt")
        return
    provider = params.get("provider")
    if provider is not None and (not isinstance(provider, str) or not provider.strip()):
        _bad(respond, "image.generate provider must be a non-empty string when provided")
        return
    size = params.get("size")
    if size is not None and (not isinstance(size, str) or not size.strip()):
        _bad(respond, "image.generate size must be a non-empty string when provided")
        return
    quality = params.get("quality")
    if quality is not None and (not isinstance(quality, str) or not quality.strip()):
        _bad(respond, "image.generate quality must be a non-empty string when provided")
        return

    # Prefer explicit hook so app server can own the runtime.
    hook = context.get("image_generate") if isinstance(context, dict) else None
    if callable(hook):
        try:
            out = hook(params)
            _ok(respond, out if isinstance(out, dict) else {"ok": True, "result": out})
        except Exception as exc:
            _unavailable(respond, str(exc))
        return

    # Fallback: use image-generation-core with providers passed through context/runtime snapshot.
    providers: list[dict[str, Any]] = []
    if isinstance(context, dict):
        raw = context.get("image_generation_providers")
        if isinstance(raw, list):
            providers = [p for p in raw if isinstance(p, dict)]
        elif callable(context.get("get_runtime_snapshot")):
            try:
                snap = context["get_runtime_snapshot"]()
                if isinstance(snap, dict) and isinstance(snap.get("image_generation_providers"), list):
                    providers = [p for p in snap.get("image_generation_providers") if isinstance(p, dict)]
            except Exception:
                providers = []
    # Keep only image-capable providers when capability is declared.
    providers = [
        p
        for p in providers
        if not isinstance(p.get("capabilities"), dict) or bool((p.get("capabilities") or {}).get("image_generation", True))
    ]
    if provider and not any(str(p.get("id")) == provider.strip() for p in providers):
        _fail(respond, "NOT_FOUND", f'image provider "{provider.strip()}" is not registered')
        return
    cfg: dict[str, Any] = {}
    if isinstance(context, dict) and isinstance(context.get("config"), dict):
        cfg = dict(context.get("config") or {})
    image_cfg = cfg.get("image") if isinstance(cfg.get("image"), dict) else {}
    default_provider = str((image_cfg or {}).get("defaultProvider") or "").strip()
    priority = [str(x).strip() for x in ((image_cfg or {}).get("providerPriority") or []) if str(x).strip()]

    ordered = list(providers)
    if not provider:
        if default_provider and any(str(p.get("id") or "") == default_provider for p in ordered):
            ordered.sort(key=lambda p: 0 if str(p.get("id") or "") == default_provider else 1)
        elif priority:
            rank = {pid: idx for idx, pid in enumerate(priority)}
            ordered.sort(key=lambda p: rank.get(str(p.get("id") or ""), 10_000))
    runtime = {"image_generation_providers": ordered}
    try:
        generate_image = _load_generate_image_fn()
        out = generate_image(
            prompt=prompt.strip(),
            provider_id=(provider.strip() if isinstance(provider, str) else None),
            runtime=runtime,
            size=(size.strip() if isinstance(size, str) else None),
            quality=(quality.strip() if isinstance(quality, str) else None),
        )
        if isinstance(out, dict) and out.get("ok") is True:
            _ok(respond, out)
            return
        if isinstance(out, dict):
            err = str(out.get("error") or "image generation failed")
            if err == "no_image_generation_provider_registered":
                _fail(respond, "UNAVAILABLE", err)
                return
            if err == "provider_not_found":
                _fail(respond, "NOT_FOUND", err)
                return
            _fail(respond, "UNAVAILABLE", err)
            return
        _unavailable(respond, "image generation failed")
    except Exception as exc:
        _unavailable(respond, str(exc))


image_handlers: GatewayRequestHandlers = {
    "image.generate": _image_generate_handler,
}

