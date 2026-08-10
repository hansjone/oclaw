"""Detect ops short intents for WhatsApp/field English recipes."""

from __future__ import annotations

import re
from typing import Any

_BOT_MENTION_RE = re.compile(r"@\S+")

# intent -> (en hint, zh hint)
_HINTS: dict[str, tuple[str, str]] = {
    "fiber_cut": (
        "[Ops short-intent: fiber/LOS. Prefer ume_alarm_xlsx_report(mode=fiber_cut) in ≤3 tool calls; "
        "do not paginate or re-list CLI targets first.]",
        "[短指令：断纤/LOS。优先 ume_alarm_xlsx_report(mode=fiber_cut)，≤3 次工具；勿先翻页或反复 listCliTargets。]",
    ),
    "offline": (
        "[Ops short-intent: offline NE. Prefer ume_alarm_xlsx_report(mode=offline) in ≤3 tool calls.]",
        "[短指令：离线网元。优先 ume_alarm_xlsx_report(mode=offline)，≤3 次工具。]",
    ),
    "alarm_tally": (
        "[Ops short-intent: alarm tally/top. Prefer aggregateUmeAlarms or "
        "ume_alarm_xlsx_report(mode=aggregate_by_host); ≤3 tool calls.]",
        "[短指令：告警统计/Top。优先 aggregateUmeAlarms 或 ume_alarm_xlsx_report(mode=aggregate_by_host)；≤3 次工具。]",
    ),
    "excel_export": (
        "[Ops short-intent: Excel export. Prefer ume_alarm_xlsx_report or write_xlsx(deliverable=true); "
        "do not build xlsx via run_command.]",
        "[短指令：导出 Excel。优先 ume_alarm_xlsx_report 或 write_xlsx(deliverable=true)；禁止 run_command 造表。]",
    ),
    "continue": (
        "[Ops short-intent: continue/confirm. Resume the unfinished prior task immediately; "
        "do not re-ask confirmation or restart the query from scratch.]",
        "[短指令：继续/确认。立即承接上一未完成任务；勿再问确认或重开查询。]",
    ),
}


def normalize_ops_user_text(text: str) -> str:
    s = str(text or "").strip()
    if not s:
        return ""
    s = _BOT_MENTION_RE.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def detect_ops_short_intent(text: str) -> str | None:
    """Return a recipe key for ultra-short field asks, else None."""
    t = normalize_ops_user_text(text)
    if not t or len(t) > 160:
        return None

    if re.fullmatch(r"(yes|y|ok|okay|confirm|continue|please continue|go ahead|可以|确认|继续|好的|行)", t):
        return "continue"
    if any(k in t for k in ("fiber", "los", "cable cut", "optical", "断纤", "光缆", "光路")):
        return "fiber_cut"
    if any(k in t for k in ("offline", "board offline", "ne communication", "离线", "单板离线", "通信中断")):
        return "offline"
    if any(k in t for k in ("excel", "xlsx", "spreadsheet", "export", "send me the table", "表格", "导出")):
        return "excel_export"
    if any(
        k in t
        for k in (
            "alarm",
            "critical",
            "tally",
            "top ne",
            "how many",
            "告警",
            "统计",
            "多少",
        )
    ):
        return "alarm_tally"
    return None


def build_ops_short_intent_hint(*, intent: str, lang: str = "en") -> str:
    key = str(intent or "").strip()
    pair = _HINTS.get(key)
    if not pair:
        return ""
    en, zh = pair
    return zh if str(lang or "").strip().lower().startswith("zh") else en


def maybe_ops_short_intent_system_hint(*, text: str, lang: str = "en") -> str:
    intent = detect_ops_short_intent(text)
    if not intent:
        return ""
    return build_ops_short_intent_hint(intent=intent, lang=lang)


__all__ = [
    "build_ops_short_intent_hint",
    "detect_ops_short_intent",
    "maybe_ops_short_intent_system_hint",
    "normalize_ops_user_text",
]
