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


def _normalize_triggers(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for x in raw:
        if not isinstance(x, str):
            continue
        s = x.strip()
        if not s:
            continue
        k = s.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(s)
    return out


def _voicewake_get_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    context = opts.get("context")
    load_cfg = context.get("load_voicewake_config") if isinstance(context, dict) else None
    if callable(load_cfg):
        try:
            cfg = load_cfg()
            triggers = cfg.get("triggers") if isinstance(cfg, dict) else None
            _ok(respond, {"triggers": triggers if isinstance(triggers, list) else []})
            return
        except Exception as exc:
            _unavailable(respond, str(exc))
            return
    _ok(respond, {"triggers": []})


def _voicewake_set_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params")
    context = opts.get("context")
    if not isinstance(params, dict) or not isinstance(params.get("triggers"), list):
        _bad(respond, "voicewake.set requires triggers: string[]")
        return
    triggers = _normalize_triggers(params.get("triggers"))
    set_cfg = context.get("set_voicewake_triggers") if isinstance(context, dict) else None
    if callable(set_cfg):
        try:
            cfg = set_cfg(triggers)
            value = cfg.get("triggers") if isinstance(cfg, dict) else triggers
            if callable(context.get("broadcastVoiceWakeChanged")):
                context["broadcastVoiceWakeChanged"](value)
            _ok(respond, {"triggers": value if isinstance(value, list) else triggers})
            return
        except Exception as exc:
            _unavailable(respond, str(exc))
            return
    if callable(context.get("broadcastVoiceWakeChanged")):
        context["broadcastVoiceWakeChanged"](triggers)
    _ok(respond, {"triggers": triggers})


voicewake_handlers: GatewayRequestHandlers = {
    "voicewake.get": _voicewake_get_handler,
    "voicewake.set": _voicewake_set_handler,
}

