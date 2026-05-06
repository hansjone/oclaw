from __future__ import annotations

AUTO_TITLE_CHAR_MAX = 18

# Minimal system prompts: naming-only role (full rules are enforced in finalize_auto_title).
AUTO_TITLE_SYSTEM_PROMPT_EN = (
    "Dedicated session naming agent: output one short title only, "
    f"≤{AUTO_TITLE_CHAR_MAX} characters, same language as the user lines."
)
AUTO_TITLE_SYSTEM_PROMPT_ZH = (
    "你是专职会话命名助手：只输出一条短标题，"
    f"至多{AUTO_TITLE_CHAR_MAX}个字，语种与用户发言一致。"
)
# One-line titles longer than this are almost never valid (model wrote prose).
_AUTO_TITLE_RAW_SOFT_MAX = 42


def _collapse_ws(raw: str) -> str:
    return " ".join(str(raw or "").strip().split())


def should_reject_auto_title(raw: str) -> bool:
    s = _collapse_ws(raw)
    if not s:
        return True
    if len(s) > _AUTO_TITLE_RAW_SOFT_MAX:
        return True
    low = s.lower()
    if "claude code" in low:
        return True
    if "软件工程助手" in s:
        return True
    if "您好" in s and "我是" in s and len(s) > 16:
        return True
    if low.startswith("hello! i am") or low.startswith("hi! i am"):
        return True
    return False


def finalize_auto_title(*, raw: str, fallback: str, max_chars: int = AUTO_TITLE_CHAR_MAX) -> str:
    """Turn model output into a short session title; reject prose and use fallback."""
    fb = _collapse_ws(fallback)
    pick = _collapse_ws(raw)
    if not pick or should_reject_auto_title(raw):
        base = fb
    else:
        base = pick
    if not base:
        return "会话"
    if len(base) <= max_chars:
        return base
    return base[:max_chars]


__all__ = [
    "AUTO_TITLE_CHAR_MAX",
    "AUTO_TITLE_SYSTEM_PROMPT_EN",
    "AUTO_TITLE_SYSTEM_PROMPT_ZH",
    "finalize_auto_title",
    "should_reject_auto_title",
]
