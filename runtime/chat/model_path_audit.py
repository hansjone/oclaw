from __future__ import annotations

from typing import Any

_MIN_B64_CHARS = 200


def ensure_no_tool_or_embedded_image_payload(*, messages: list[dict[str, Any]], path: str) -> None:
    """Guard non-turn model paths and degrade in place instead of raising.

    - `role=tool` is downgraded to assistant text summary.
    - Embedded image/base64 payloads are replaced with safe text placeholders.
    """
    for m in messages or []:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "").strip().lower()
        if role == "tool":
            m["role"] = "assistant"
            m["content"] = f"[model_path_audit:{path}] tool payload omitted"
            continue
        content = m.get("content")
        if _contains_embedded_image_payload(content):
            m["content"] = _sanitize_content(content, path=path)


def _contains_embedded_image_payload(obj: Any) -> bool:
    if isinstance(obj, str):
        return _contains_large_base64_like_text(obj)
    if isinstance(obj, list):
        return any(_contains_embedded_image_payload(x) for x in obj)
    if not isinstance(obj, dict):
        return False
    typ = str(obj.get("type") or "").strip().lower()
    if typ in {"image", "input_image"}:
        for k in ("data", "image_base64"):
            v = obj.get(k)
            if isinstance(v, str) and len(v.strip()) >= _MIN_B64_CHARS:
                return True
    for v in obj.values():
        if _contains_embedded_image_payload(v):
            return True
    return False


def _contains_large_base64_like_text(text: str) -> bool:
    s = str(text or "").strip()
    if len(s) < _MIN_B64_CHARS:
        return False
    if s.startswith("data:") and ";base64," in s:
        s = s.split(";base64,", 1)[1]
    head = s[: min(4096, len(s))]
    if len(head) < _MIN_B64_CHARS:
        return False
    allowed = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=\n\r-_")
    noise = sum(1 for ch in head if ch not in allowed)
    # Similar heuristic to media redaction: mostly base64 alphabet over a long span.
    return noise <= max(4, len(head) // 200)


def _sanitize_content(content: Any, *, path: str) -> Any:
    if isinstance(content, str):
        if _contains_large_base64_like_text(content):
            return f"[model_path_audit:{path}] base64 payload omitted"
        return content
    if isinstance(content, list):
        out: list[Any] = []
        for item in content:
            if isinstance(item, dict):
                typ = str(item.get("type") or "").strip().lower()
                if typ in {"image", "input_image"}:
                    out.append({"type": "text", "text": f"[model_path_audit:{path}] image payload omitted"})
                    continue
            out.append(_sanitize_content(item, path=path))
        return out
    if isinstance(content, dict):
        out: dict[str, Any] = {}
        for k, v in content.items():
            if str(k) in {"data", "image_base64"} and isinstance(v, str) and _contains_large_base64_like_text(v):
                out[k] = f"[model_path_audit:{path}] payload omitted"
                continue
            out[k] = _sanitize_content(v, path=path)
        return out
    return content


__all__ = ["ensure_no_tool_or_embedded_image_payload"]
