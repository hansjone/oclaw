from __future__ import annotations

import base64
import time
from typing import Any

from .shared_types import GatewayRequestHandlers
from .validation import error_shape


TALK_SECRETS_SCOPE = "talk.secrets"
ADMIN_SCOPE = "operator.admin"


def _ok(respond, payload: Any, meta: dict[str, Any] | None = None) -> None:
    if callable(respond):
        respond(True, payload, None, meta or None)


def _bad(respond, message: str) -> None:
    if callable(respond):
        respond(False, None, error_shape("INVALID_REQUEST", message), None)


def _unavailable(respond, message: str, *, details: dict[str, Any] | None = None) -> None:
    if callable(respond):
        respond(False, None, error_shape("UNAVAILABLE", message, {"details": details} if details else None), None)


def _norm_str(v: Any) -> str | None:
    if isinstance(v, str):
        s = v.strip()
        return s or None
    return None


def _caller_scopes(client: Any) -> list[str]:
    if not isinstance(client, dict):
        return []
    connect = client.get("connect")
    if not isinstance(connect, dict):
        return []
    scopes = connect.get("scopes")
    if isinstance(scopes, list):
        return [x for x in scopes if isinstance(x, str)]
    return []


def _can_read_talk_secrets(client: Any) -> bool:
    scopes = set(_caller_scopes(client))
    return (ADMIN_SCOPE in scopes) or (TALK_SECRETS_SCOPE in scopes)


def _resolve_speed(params: dict[str, Any]) -> float | None:
    speed = params.get("speed")
    if isinstance(speed, (int, float)):
        return float(speed)
    rate_wpm = params.get("rateWpm")
    if not isinstance(rate_wpm, (int, float)) or rate_wpm <= 0:
        return None
    resolved = float(rate_wpm) / 175.0
    if resolved <= 0.5 or resolved >= 2.0:
        return None
    return resolved


def _infer_mime_type(output_format: str | None, file_extension: str | None) -> str | None:
    of = (output_format or "").strip().lower()
    ext = (file_extension or "").strip().lower()
    if of == "mp3" or of.startswith("mp3_") or of.endswith("-mp3") or ext == ".mp3":
        return "audio/mpeg"
    if of == "opus" or of.startswith("opus_") or ext in {".opus", ".ogg"}:
        return "audio/ogg"
    if of.endswith("-wav") or ext == ".wav":
        return "audio/wav"
    if of.endswith("-webm") or ext == ".webm":
        return "audio/webm"
    return None


def _talk_config_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    client = opts.get("client")

    if not isinstance(params, dict):
        _bad(respond, "invalid talk.config params")
        return
    include_secrets = bool(params.get("includeSecrets"))
    if include_secrets and not _can_read_talk_secrets(client):
        _bad(respond, f"missing scope: {TALK_SECRETS_SCOPE}")
        return

    hook = context.get("read_talk_config") if isinstance(context, dict) else None
    if callable(hook):
        try:
            cfg = hook({"includeSecrets": include_secrets})
            _ok(respond, {"config": cfg if isinstance(cfg, dict) else {}})
            return
        except Exception as exc:
            _unavailable(respond, str(exc))
            return
    _ok(respond, {"config": {}})


def _talk_speak_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid talk.speak params")
        return
    text = _norm_str(params.get("text")) or ""
    if not text:
        _bad(respond, "talk.speak requires text")
        return

    if params.get("speed") is None and params.get("rateWpm") is not None and _resolve_speed(params) is None:
        _bad(respond, "invalid talk.speak params: rateWpm must resolve to speed between 0.5 and 2.0")
        return

    hook = context.get("talk_synthesize") if isinstance(context, dict) else None
    if callable(hook):
        try:
            out = hook(
                {
                    "text": text,
                    "voiceId": _norm_str(params.get("voiceId")),
                    "speed": _resolve_speed(params),
                }
            )
        except Exception as exc:
            _unavailable(respond, str(exc), details={"reason": "synthesis_failed", "fallbackEligible": False})
            return
        if not isinstance(out, dict):
            _unavailable(respond, "talk synthesis failed", details={"reason": "synthesis_failed", "fallbackEligible": False})
            return
        if not out.get("success") or not out.get("audio"):
            _unavailable(
                respond,
                str(out.get("error") or "talk synthesis failed"),
                details={"reason": "synthesis_failed", "fallbackEligible": False},
            )
            return
        audio = out.get("audio")
        if isinstance(audio, str):
            audio_b64 = audio
        elif isinstance(audio, (bytes, bytearray, memoryview)):
            audio_b64 = base64.b64encode(bytes(audio)).decode("ascii")
        else:
            _unavailable(respond, "talk synthesis returned invalid audio", details={"reason": "invalid_audio_result", "fallbackEligible": False})
            return
        provider = _norm_str(out.get("provider")) or "talk"
        if not provider:
            _unavailable(respond, "talk synthesis returned empty provider", details={"reason": "invalid_audio_result", "fallbackEligible": False})
            return
        output_format = _norm_str(out.get("outputFormat"))
        file_ext = _norm_str(out.get("fileExtension"))
        _ok(
            respond,
            {
                "audioBase64": audio_b64,
                "provider": provider,
                "outputFormat": output_format,
                "voiceCompatible": bool(out.get("voiceCompatible", True)),
                "mimeType": _infer_mime_type(output_format, file_ext),
                "fileExtension": file_ext,
            },
        )
        return

    # Fallback: return a tiny silent WAV header-ish payload (not real audio, but non-empty).
    audio_b64 = base64.b64encode(b"RIFF").decode("ascii")
    _ok(
        respond,
        {
            "audioBase64": audio_b64,
            "provider": "staging",
            "outputFormat": "wav",
            "voiceCompatible": True,
            "mimeType": "audio/wav",
            "fileExtension": ".wav",
        },
    )


def _talk_mode_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params") or {}
    respond = opts.get("respond")
    context = opts.get("context")
    client = opts.get("client")
    is_webchat_connect = opts.get("is_webchat_connect")

    if client and callable(is_webchat_connect) and is_webchat_connect((client or {}).get("connect")):
        has_mobile = context.get("hasConnectedMobileNode") if isinstance(context, dict) else None
        try:
            ok_mobile = bool(has_mobile()) if callable(has_mobile) else True
        except Exception:
            ok_mobile = True
        if not ok_mobile:
            _unavailable(respond, "talk disabled: no connected iOS/Android nodes")
            return

    if not isinstance(params, dict) or not isinstance(params.get("enabled"), bool):
        _bad(respond, "invalid talk.mode params")
        return
    payload = {
        "enabled": bool(params.get("enabled")),
        "phase": _norm_str(params.get("phase")),
        "ts": int(time.time() * 1000),
    }
    broadcast = context.get("broadcast") if isinstance(context, dict) else None
    if callable(broadcast):
        try:
            broadcast("talk.mode", payload, {"dropIfSlow": True})
        except Exception:
            pass
    _ok(respond, payload)


talk_handlers: GatewayRequestHandlers = {
    "talk.config": _talk_config_handler,
    "talk.speak": _talk_speak_handler,
    "talk.mode": _talk_mode_handler,
}

