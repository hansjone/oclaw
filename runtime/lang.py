from __future__ import annotations

import re
from typing import Any

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")


def detect_text_lang(text: str) -> str | None:
    """Heuristic zh/en from user message; None if ambiguous."""
    t = str(text or "").strip()
    if not t:
        return None
    cjk = len(_CJK_RE.findall(t))
    latin = sum(1 for ch in t if ch.isascii() and ch.isalpha())
    if cjk >= 2 and cjk >= latin:
        return "zh"
    if latin >= 6 and latin > cjk * 2:
        return "en"
    return None


def resolve_runtime_lang(
    *,
    store: Any | None = None,
    hint: str | None = None,
    user_text: str | None = None,
) -> str:
    """Resolve zh/en for agent runtime (WS, worker, HTTP share this helper).

    User message language wins over UI hint so English prompts get English replies
    even when the admin UI is still set to Chinese.
    """
    detected = detect_text_lang(user_text or "")
    if detected in ("zh", "en"):
        return detected
    raw = str(hint or "").strip().lower()
    if raw in ("zh", "en"):
        return raw
    if store is not None:
        try:
            v = str(store.get_setting("ui_lang") or "zh").strip().lower()
        except Exception:
            v = "zh"
        if v in ("zh", "en"):
            return v
    return "zh"


__all__ = ["detect_text_lang", "resolve_runtime_lang"]
