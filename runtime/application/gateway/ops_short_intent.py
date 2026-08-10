"""Detect ops short intents for WhatsApp/field English recipes."""

from __future__ import annotations

import re
import threading
import time
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
    "license": (
        "[Ops short-intent: license/capacity. Prefer aggregateUmeAlarms / queryUmeAlarmsRaw with license keywords, "
        "or ume_alarm_xlsx_report(mode=list, keyword=license); ≤3 tool calls — no CLI spam.]",
        "[短指令：License/容量。优先 aggregateUmeAlarms / queryUmeAlarmsRaw（license 关键字）"
        "或 ume_alarm_xlsx_report(mode=list, keyword=license)；≤3 次工具，勿刷 CLI。]",
    ),
    "congestion": (
        "[Ops short-intent: bandwidth congestion. Prefer aggregateUmeAlarms / queryUmeAlarmsRaw "
        "(bandwidth/utilization/congestion keywords) or ume_alarm_xlsx_report(mode=list); "
        "≤3 tool calls — no CLI spam / no sqlQueryUme unless scoped.]",
        "[短指令：带宽拥塞。优先 aggregateUmeAlarms / queryUmeAlarmsRaw（带宽/利用率/拥塞）"
        "或 ume_alarm_xlsx_report(mode=list)；≤3 次工具，勿刷 CLI / 勿先 sqlQueryUme。]",
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
    if any(k in t for k in ("congest", "bandwidth", "utilization", "拥塞", "带宽", "利用率", "端口忙")):
        return "congestion"
    if any(k in t for k in ("license", "licence", "capacity", "license到期")):
        return "license"
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


def build_group_mention_nudge_text(
    *,
    intent: str | None = None,
    lang: str = "en",
    triggers: list[str] | None = None,
) -> str:
    """Tell field users why a group ops ask was ignored (require @bot / trigger)."""
    extra = ""
    trigs = [str(x or "").strip() for x in (triggers or []) if str(x or "").strip()]
    if trigs:
        shown = ", ".join(trigs[:3])
        if str(lang or "").strip().lower().startswith("zh"):
            extra = f"或发送触发词（{shown}）"
        else:
            extra = f" or use a trigger ({shown})"
    label = str(intent or "").strip().replace("_", " ")
    if str(lang or "").strip().lower().startswith("zh"):
        topic = f"（识别到：{label}）" if label else ""
        return (
            f"群里需要先 @我{extra} 才会处理运维请求{topic}。"
            "请带上 @ 后重发（断纤/离线/告警/Excel/license 等）。"
        )
    topic = f" (detected: {label})" if label else ""
    return (
        f"In this group I only answer when @mentioned{extra}{topic}. "
        "Please re-send with @me for ops asks (fiber / offline / alarms / excel / license)."
    )


_MENTION_NUDGE_LOCK = threading.Lock()
_MENTION_NUDGE_LAST: dict[str, float] = {}
_MENTION_NUDGE_TTL_S = 12 * 60.0


def should_send_group_mention_nudge(
    *,
    account_id: str,
    chat_id: str,
    user_id: str,
    now: float | None = None,
    ttl_s: float | None = None,
) -> bool:
    """Throttle one nudge per sender/chat for a few minutes."""
    key = f"{str(account_id or '').strip()}|{str(chat_id or '').strip()}|{str(user_id or '').strip()}"
    if not key.strip("|"):
        return False
    ts = float(now if now is not None else time.monotonic())
    window = float(ttl_s if ttl_s is not None else _MENTION_NUDGE_TTL_S)
    with _MENTION_NUDGE_LOCK:
        prev = _MENTION_NUDGE_LAST.get(key)
        if prev is not None and (ts - float(prev)) < window:
            return False
        _MENTION_NUDGE_LAST[key] = ts
        if len(_MENTION_NUDGE_LAST) > 512:
            cutoff = ts - window
            stale = [k for k, v in _MENTION_NUDGE_LAST.items() if float(v) < cutoff]
            for k in stale[:128]:
                _MENTION_NUDGE_LAST.pop(k, None)
        return True


def reset_group_mention_nudge_throttle_for_tests() -> None:
    with _MENTION_NUDGE_LOCK:
        _MENTION_NUDGE_LAST.clear()


__all__ = [
    "build_group_mention_nudge_text",
    "build_ops_short_intent_hint",
    "detect_ops_short_intent",
    "maybe_ops_short_intent_system_hint",
    "normalize_ops_user_text",
    "reset_group_mention_nudge_throttle_for_tests",
    "should_send_group_mention_nudge",
]
