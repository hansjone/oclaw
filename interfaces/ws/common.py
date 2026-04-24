from __future__ import annotations

import base64
import time
from typing import Any

from oclaw.platform.files.file_attachments import process_file_data

PROTOCOL_VERSION = 3
MAX_PAYLOAD_BYTES = 26_214_400
MAX_BUFFERED_BYTES = 52_428_800
TICK_INTERVAL_MS = 15_000
PREAUTH_HANDSHAKE_TIMEOUT_MS = 15_000


def now_ms() -> int:
    return int(time.time() * 1000)


def error_shape(code: str, message: str, *, details: Any | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"code": str(code or "INVALID_REQUEST"), "message": str(message or "invalid_request")}
    if details is not None:
        out["details"] = details
    return out


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
    "now_ms",
    "error_shape",
    "decode_base64_payload_ws",
    "normalize_ws_attachments",
]

