from __future__ import annotations

from dataclasses import dataclass

from runtime.orchestration.protocol import AgentTask

_HIGH_RISK_ACTIONS = ("删除", "drop", "重启", "批量", "扫描", "写入", "变更")


@dataclass(frozen=True)
class GuardrailResult:
    allowed: bool
    needs_confirmation: bool
    reason: str


def evaluate_risk(task: AgentTask) -> GuardrailResult:
    text = (task.user_text or "").lower()
    high_risk = task.risk_level == "high" or any(k in text for k in _HIGH_RISK_ACTIONS)
    if high_risk:
        return GuardrailResult(
            allowed=True,
            needs_confirmation=True,
            reason="High-risk action detected, require explicit confirmation token.",
        )
    return GuardrailResult(allowed=True, needs_confirmation=False, reason="Low-risk request")


_AFFIRMATIVE_SHORT = frozenset(
    {
        "yes",
        "y",
        "ok",
        "okay",
        "confirm",
        "continue",
        "please continue",
        "go ahead",
        "可以",
        "确认",
        "继续",
        "好的",
        "行",
        "是",
    }
)


def has_explicit_confirmation(user_text: str) -> bool:
    return has_explicit_confirmation_token(user_text, token=None)


def has_explicit_confirmation_token(user_text: str, token: str | None) -> bool:
    text = (user_text or "").strip()
    if not text:
        return False
    low = text.lower()
    if low.startswith("confirm "):
        if token:
            parts = low.split()
            return len(parts) >= 2 and parts[1].strip() == token.lower()
        return True
    if "[confirm]" in low or "确认执行" in low:
        return True
    if token:
        t = token.strip()
        if not t:
            return False
        if f"[confirm:{t}]".lower() in low or f"confirm:{t}".lower() in low:
            return True
        # WhatsApp field: short YES/continue while a token is outstanding.
        import re

        compact = re.sub(r"@\S+", " ", low)
        compact = " ".join(compact.split())
        if compact in _AFFIRMATIVE_SHORT:
            return True
    return False


__all__ = ["GuardrailResult", "evaluate_risk", "has_explicit_confirmation", "has_explicit_confirmation_token"]
