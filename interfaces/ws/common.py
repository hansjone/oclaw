from __future__ import annotations

import base64
import os
import time
from typing import Any

from oclaw.platform.files.file_attachments import process_file_data

PROTOCOL_VERSION = 3
MAX_PAYLOAD_BYTES = 26_214_400
MAX_BUFFERED_BYTES = 52_428_800
TICK_INTERVAL_MS = 15_000
PREAUTH_HANDSHAKE_TIMEOUT_MS = 15_000
WS_REQUIRE_AUTH = str(os.getenv("OCLAW_WS_REQUIRE_AUTH") or "1").strip().lower() not in ("0", "false", "no", "off")
WS_ALLOWED_ORIGINS = [s.strip() for s in str(os.getenv("OCLAW_WS_ALLOWED_ORIGINS") or "").split(",") if s.strip()]
WS_RATE_LIMIT_WINDOW_MS = int(os.getenv("OCLAW_WS_RATE_LIMIT_WINDOW_MS") or "60000")
WS_RATE_LIMIT_CONN_PER_WINDOW = int(os.getenv("OCLAW_WS_RATE_LIMIT_CONN_PER_WINDOW") or "120")
WS_RATE_LIMIT_IP_PER_WINDOW = int(os.getenv("OCLAW_WS_RATE_LIMIT_IP_PER_WINDOW") or "240")
WS_RATE_LIMIT_USER_PER_WINDOW = int(os.getenv("OCLAW_WS_RATE_LIMIT_USER_PER_WINDOW") or "360")
WS_SEND_QUEUE_MAX_MESSAGES = int(os.getenv("OCLAW_WS_SEND_QUEUE_MAX_MESSAGES") or "256")
WS_SEND_QUEUE_MAX_BYTES = int(os.getenv("OCLAW_WS_SEND_QUEUE_MAX_BYTES") or str(MAX_BUFFERED_BYTES))
WS_EVENT_REPLAY_MAX = int(os.getenv("OCLAW_WS_EVENT_REPLAY_MAX") or "256")


def now_ms() -> int:
    return int(time.time() * 1000)


def error_shape(code: str, message: str, *, details: Any | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"code": str(code or "INVALID_REQUEST"), "message": str(message or "invalid_request")}
    if details is not None:
        out["details"] = details
    return out


def origin_is_allowed(origin: str | None, host: str | None) -> bool:
    value = str(origin or "").strip()
    if not value:
        return True
    allowlist = list(WS_ALLOWED_ORIGINS)
    if allowlist:
        return value in allowlist
    host_value = str(host or "").strip()
    if not host_value:
        return False
    lower = value.lower()
    return lower.startswith(f"https://{host_value.lower()}") or lower.startswith(f"http://{host_value.lower()}")


def decode_base64_payload_ws(s: str | None) -> bytes | None:
    raw = str(s or "").strip()
    if not raw:
        return None
    if raw.startswith("data:") and "," in raw:
        raw = raw.split(",", 1)[1].strip()
    raw = raw.replace("-", "+").replace("_", "/")
    pad = (-len(raw)) % 4
    if pad:
        raw += "=" * pad
    try:
        return base64.b64decode(raw, validate=False)
    except Exception:
        try:
            return base64.standard_b64decode(raw)
        except Exception:
            return None


def normalize_ws_attachments(raw: Any) -> list[dict[str, Any]]:
    if not raw:
        return []
    items = raw if isinstance(raw, list) else []
    out: list[dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        if "type" in it:
            out.append(it)
            continue
        name = str(it.get("name") or "file").strip() or "file"
        b64 = it.get("data_base64") if "data_base64" in it else it.get("data")
        if not isinstance(b64, str) or not b64.strip():
            continue
        data = decode_base64_payload_ws(b64)
        if not data:
            continue
        got = process_file_data(name, data)
        if got:
            out.extend(got)
    return out


__all__ = [
    "PROTOCOL_VERSION",
    "MAX_PAYLOAD_BYTES",
    "MAX_BUFFERED_BYTES",
    "TICK_INTERVAL_MS",
    "PREAUTH_HANDSHAKE_TIMEOUT_MS",
    "WS_REQUIRE_AUTH",
    "WS_ALLOWED_ORIGINS",
    "WS_RATE_LIMIT_WINDOW_MS",
    "WS_RATE_LIMIT_CONN_PER_WINDOW",
    "WS_RATE_LIMIT_IP_PER_WINDOW",
    "WS_RATE_LIMIT_USER_PER_WINDOW",
    "WS_SEND_QUEUE_MAX_MESSAGES",
    "WS_SEND_QUEUE_MAX_BYTES",
    "WS_EVENT_REPLAY_MAX",
    "now_ms",
    "error_shape",
    "origin_is_allowed",
    "decode_base64_payload_ws",
    "normalize_ws_attachments",
]

