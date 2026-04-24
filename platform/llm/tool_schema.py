from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_MIN_TOOL_PARAMETERS: dict[str, Any] = {"type": "object", "additionalProperties": True}


def openai_tools_json_byte_length(tools: list[dict[str, Any]]) -> int:
    try:
        return len(json.dumps(tools, ensure_ascii=False, default=str))
    except Exception:
        return 0


def shrink_openai_tools_payload_for_api(tools: list[dict[str, Any]], *, max_json_bytes: int) -> list[dict[str, Any]]:
    """Shrink OpenAI ``tools`` JSON for strict OpenAI-compatible gateways."""
    if not tools or max_json_bytes <= 0:
        return tools
    if openai_tools_json_byte_length(tools) <= max_json_bytes:
        return tools
    flat: list[dict[str, Any]] = []
    for t in tools:
        if not isinstance(t, dict) or str(t.get("type") or "") != "function":
            continue
        fn = t.get("function")
        if not isinstance(fn, dict):
            continue
        name = str(fn.get("name") or "").strip()
        if not name:
            continue
        desc = str(fn.get("description") or "")
        flat.append({"type": "function", "function": {"name": name, "description": desc, "parameters": dict(_MIN_TOOL_PARAMETERS)}})
    if not flat:
        return tools

    def _serialized_with_desc_cap(cap: int) -> str:
        trimmed: list[dict[str, Any]] = []
        for x in flat:
            fn0 = x["function"]
            trimmed.append(
                {
                    "type": "function",
                    "function": {
                        "name": fn0["name"],
                        "description": (fn0.get("description") or "")[: max(0, cap)],
                        "parameters": fn0["parameters"],
                    },
                }
            )
        return json.dumps(trimmed, ensure_ascii=False, default=str)

    lo, hi = 0, min(8000, max_json_bytes)
    best_cap = 0
    while lo <= hi:
        mid = (lo + hi) // 2
        s = _serialized_with_desc_cap(mid)
        if len(s) <= max_json_bytes:
            best_cap = mid
            lo = mid + 1
        else:
            hi = mid - 1
    out_obj: list[dict[str, Any]] = json.loads(_serialized_with_desc_cap(best_cap))
    blob = json.dumps(out_obj, ensure_ascii=False, default=str)
    dropped = 0
    while len(out_obj) > 8 and len(blob) > max_json_bytes:
        out_obj.pop()
        dropped += 1
        blob = json.dumps(out_obj, ensure_ascii=False, default=str)
    logger.warning(
        "Shrunk OpenAI tools[] for API size limits: count=%d max_json_bytes=%d desc_cap=%d dropped=%d final_bytes=%d",
        len(out_obj),
        max_json_bytes,
        best_cap,
        dropped,
        len(blob),
    )
    return out_obj


def default_max_openai_tools_json_bytes(base_url: str | None) -> int | None:
    raw = str(os.getenv("AIA_OPENAI_TOOLS_MAX_JSON_CHARS") or "").strip()
    if raw.isdigit():
        return max(2000, int(raw))
    u = (base_url or "").lower()
    if "dashscope.aliyuncs.com" in u:
        return 28000
    if str(os.getenv("AIA_SHRINK_OPENAI_TOOLS") or "").strip().lower() in ("1", "true", "yes", "on"):
        mx = str(os.getenv("AIA_SHRINK_OPENAI_TOOLS_MAX_JSON") or "28000").strip()
        return max(2000, int(mx)) if mx.isdigit() else 28000
    return None


__all__ = [
    "default_max_openai_tools_json_bytes",
    "openai_tools_json_byte_length",
    "shrink_openai_tools_payload_for_api",
]

