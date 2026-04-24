from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from oclaw.platform.config.paths import PROJECT_ROOT

_SCHEMA_DIR = Path(PROJECT_ROOT) / "oclaw" / "openclaw_protocol_schemas"


def _load_schema(name: str) -> dict[str, Any]:
    p = _SCHEMA_DIR / name
    return json.loads(p.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class WsSchemas:
    frame: Draft202012Validator
    connect_params: Draft202012Validator
    hello_ok: Draft202012Validator
    agent_params: Draft202012Validator
    agent_wait_params: Draft202012Validator
    sessions_schema: dict[str, Any]
    chat_schema: dict[str, Any]


_CACHED: WsSchemas | None = None


def get_ws_schemas() -> WsSchemas:
    global _CACHED
    if _CACHED is not None:
        return _CACHED

    frame_schema = _load_schema("frames.json")
    connect_schema = _load_schema("connect.json")
    hello_ok_schema = _load_schema("hello_ok.json")
    agent_schema = _load_schema("agent.json")
    agent_wait_schema = _load_schema("agent_wait.json")
    sessions_schema = _load_schema("sessions.json")
    chat_schema = _load_schema("chat.json")

    _CACHED = WsSchemas(
        frame=Draft202012Validator(frame_schema),
        connect_params=Draft202012Validator(connect_schema),
        hello_ok=Draft202012Validator(hello_ok_schema),
        agent_params=Draft202012Validator(agent_schema),
        agent_wait_params=Draft202012Validator(agent_wait_schema),
        sessions_schema=sessions_schema,
        chat_schema=chat_schema,
    )
    return _CACHED


def format_validation_errors(errors: list[Any]) -> str:
    out: list[str] = []
    for e in errors[:6]:
        try:
            path = "/".join(str(x) for x in list(e.path))
        except Exception:
            path = ""
        msg = str(getattr(e, "message", "") or "")
        if path:
            out.append(f"{path}: {msg}")
        else:
            out.append(msg)
    return "; ".join([x for x in out if x]) or "invalid_payload"


def validate_or_errors(validator: Draft202012Validator, obj: Any) -> list[Any]:
    return list(validator.iter_errors(obj))


__all__ = ["WsSchemas", "get_ws_schemas", "format_validation_errors", "validate_or_errors"]

