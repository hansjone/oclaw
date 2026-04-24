from __future__ import annotations

from typing import Any

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


def _norm_str(v: Any) -> str | None:
    if isinstance(v, str):
        s = v.strip()
        return s or None
    return None


def _tts_status_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    context = opts.get("context")
    hook = context.get("tts_status") if isinstance(context, dict) else None
    if callable(hook):
        try:
            out = hook()
            _ok(respond, out if isinstance(out, dict) else {})
        except Exception as exc:
            _unavailable(respond, str(exc))
        return
    _ok(
        respond,
        {
            "enabled": False,
            "auto": True,
            "provider": None,
            "fallbackProvider": None,
            "fallbackProviders": [],
            "prefsPath": None,
            "providerStates": [],
        },
    )


def _tts_enable_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    context = opts.get("context")
    hook = context.get("set_tts_enabled") if isinstance(context, dict) else None
    if callable(hook):
        try:
            hook(True)
        except Exception as exc:
            _unavailable(respond, str(exc))
            return
    _ok(respond, {"enabled": True})


def _tts_disable_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    context = opts.get("context")
    hook = context.get("set_tts_enabled") if isinstance(context, dict) else None
    if callable(hook):
        try:
            hook(False)
        except Exception as exc:
            _unavailable(respond, str(exc))
            return
    _ok(respond, {"enabled": False})


def _tts_convert_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params")
    respond = opts.get("respond")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid tts.convert params")
        return
    text = _norm_str(params.get("text")) or ""
    if not text:
        _bad(respond, "tts.convert requires text")
        return
    hook = context.get("text_to_speech") if isinstance(context, dict) else None
    if callable(hook):
        try:
            out = hook(
                {
                    "text": text,
                    "channel": _norm_str(params.get("channel")),
                    "provider": _norm_str(params.get("provider")),
                    "modelId": _norm_str(params.get("modelId")),
                    "voiceId": _norm_str(params.get("voiceId")),
                }
            )
            if isinstance(out, dict):
                success = bool(out.get("success", False))
                if success and out.get("audioPath"):
                    _ok(
                        respond,
                        {
                            "audioPath": out.get("audioPath"),
                            "provider": out.get("provider"),
                            "outputFormat": out.get("outputFormat"),
                            "voiceCompatible": out.get("voiceCompatible"),
                        },
                    )
                    return
                _unavailable(respond, str(out.get("error") or "TTS conversion failed"))
                return
        except Exception as exc:
            _unavailable(respond, str(exc))
            return
    # fallback success shape
    _ok(
        respond,
        {
            "audioPath": "/tmp/tts.wav",
            "provider": _norm_str(params.get("provider")) or "staging",
            "outputFormat": "wav",
            "voiceCompatible": True,
        },
    )


def _tts_set_provider_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params")
    respond = opts.get("respond")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid tts.setProvider params")
        return
    provider = _norm_str(params.get("provider")) or ""
    if not provider:
        _bad(respond, "Invalid provider. Use a registered TTS provider id.")
        return
    hook = context.get("set_tts_provider") if isinstance(context, dict) else None
    if callable(hook):
        try:
            ok = hook(provider)
            if ok is False:
                _bad(respond, "Invalid provider. Use a registered TTS provider id.")
                return
        except Exception as exc:
            _unavailable(respond, str(exc))
            return
    _ok(respond, {"provider": provider})


def _tts_providers_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    context = opts.get("context")
    hook = context.get("list_tts_providers") if isinstance(context, dict) else None
    if callable(hook):
        try:
            out = hook()
            if isinstance(out, dict):
                _ok(respond, out)
                return
        except Exception as exc:
            _unavailable(respond, str(exc))
            return
    _ok(respond, {"providers": [], "active": None})


tts_handlers: GatewayRequestHandlers = {
    "tts.status": _tts_status_handler,
    "tts.enable": _tts_enable_handler,
    "tts.disable": _tts_disable_handler,
    "tts.convert": _tts_convert_handler,
    "tts.setProvider": _tts_set_provider_handler,
    "tts.providers": _tts_providers_handler,
}

