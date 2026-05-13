from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Full minimal object schema for ``function.parameters`` (wire / shrink / tier_minimal).
# A bare ``{type, additionalProperties}`` alone has led strict gateways to emit or validate
# ``required: null`` / missing array fields — always send explicit ``properties`` + ``required``.
_MIN_TOOL_PARAMETERS: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "required": [],
    "additionalProperties": True,
}

_COMBO_KEYS = frozenset({"allOf", "anyOf", "oneOf", "prefixItems"})


def _schema_type_tags(t: Any) -> set[str]:
    if t is None:
        return set()
    if isinstance(t, list):
        return {str(x).strip().lower() for x in t if x is not None and str(x).strip()}
    s = str(t).strip().lower()
    return {s} if s else set()


def complete_json_schema_for_openai_tools(obj: Any) -> Any:
    """Recursively ensure JSON-schema fragments match what strict OpenAI-compat gateways expect.

    This is **structural completion** for our wire path (tier/shrink/SDK), not a general MCP fix-all:
    every ``type: object`` node gets explicit ``properties`` + ``required`` (list); every
    ``type: array`` gets ``items`` (object). Combo keywords that must be arrays and are ``null``
    are dropped; list elements that are ``null`` are removed.
    """

    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            key = str(k)
            if key in _COMBO_KEYS and v is None:
                if key in ("allOf", "prefixItems"):
                    out[key] = []
                continue
            out[key] = complete_json_schema_for_openai_tools(v)

        for combo in _COMBO_KEYS:
            if combo not in out:
                continue
            val = out[combo]
            if not isinstance(val, list):
                continue
            cleaned = [complete_json_schema_for_openai_tools(x) for x in val if x is not None]
            if combo in ("anyOf", "oneOf") and not cleaned:
                out.pop(combo, None)
            else:
                out[combo] = cleaned

        if isinstance(out.get("properties"), dict):
            t0 = out.get("type")
            if t0 is None or (isinstance(t0, str) and not str(t0).strip()):
                out["type"] = "object"

        tags = _schema_type_tags(out.get("type"))
        if "object" in tags:
            if not isinstance(out.get("properties"), dict):
                out["properties"] = {}
            r = out.get("required")
            if r is None or not isinstance(r, list):
                out["required"] = []
        if "array" in tags:
            if out.get("items") is None:
                out["items"] = {}
            elif isinstance(out.get("items"), dict):
                out["items"] = complete_json_schema_for_openai_tools(out["items"])
        return out
    if isinstance(obj, list):
        return [complete_json_schema_for_openai_tools(x) for x in obj]
    return obj


def complete_openai_tools_wire_parameters(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply :func:`complete_json_schema_for_openai_tools` to each function's ``parameters``."""
    out: list[dict[str, Any]] = []
    for ent in tools or []:
        if not isinstance(ent, dict):
            continue
        if str(ent.get("type") or "") != "function":
            out.append(ent)
            continue
        fn = ent.get("function")
        if not isinstance(fn, dict):
            out.append(ent)
            continue
        params = fn.get("parameters")
        if not isinstance(params, dict):
            row = dict(ent)
            row["function"] = {**dict(fn), "parameters": dict(_MIN_TOOL_PARAMETERS)}
            out.append(row)
            continue
        row = dict(ent)
        row["function"] = {**dict(fn), "parameters": complete_json_schema_for_openai_tools(dict(params))}
        out.append(row)
    return out


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
    "MIN_OPENAI_FUNCTION_PARAMETERS",
    "complete_json_schema_for_openai_tools",
    "complete_openai_tools_wire_parameters",
    "default_max_openai_tools_json_bytes",
    "openai_tools_json_byte_length",
    "shrink_openai_tools_payload_for_api",
]

MIN_OPENAI_FUNCTION_PARAMETERS = _MIN_TOOL_PARAMETERS
