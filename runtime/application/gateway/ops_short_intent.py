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
        "[Ops short-intent: fiber/LOS. Call ume_alarm_xlsx_report(mode=fiber_cut, deliverable=true) now. "
        "Inventory/CLI tools are hidden this turn — do not try listCliTargets/execManagedNe.]",
        "[短指令：断纤/LOS。立即 ume_alarm_xlsx_report(mode=fiber_cut, deliverable=true)。"
        "本轮已隐藏清单/CLI 工具，勿调用 listCliTargets/execManagedNe。]",
    ),
    "offline": (
        "[Ops short-intent: offline NE. Call ume_alarm_xlsx_report(mode=offline, deliverable=true) now. "
        "Inventory/CLI tools are hidden this turn.]",
        "[短指令：离线网元。立即 ume_alarm_xlsx_report(mode=offline, deliverable=true)。本轮已隐藏清单/CLI。]",
    ),
    "alarm_tally": (
        "[Ops short-intent: alarm tally/top. Prefer ume_alarm_xlsx_report(mode=aggregate_by_host) or "
        "aggregateUmeAlarms; inventory/CLI tools are hidden this turn.]",
        "[短指令：告警统计/Top。优先 ume_alarm_xlsx_report(mode=aggregate_by_host) 或 aggregateUmeAlarms；"
        "本轮已隐藏清单/CLI。]",
    ),
    "excel_export": (
        "[Ops short-intent: Excel export. Prefer ume_alarm_xlsx_report or write_xlsx(deliverable=true). "
        "Inventory/CLI/run_command are hidden this turn — do not build xlsx via shell.]",
        "[短指令：导出 Excel。优先 ume_alarm_xlsx_report 或 write_xlsx(deliverable=true)；"
        "本轮已隐藏清单/CLI/run_command。]",
    ),
    "license": (
        "[Ops short-intent: license/capacity. Prefer ume_alarm_xlsx_report(mode=list, keyword=license) or "
        "aggregateUmeAlarms/queryUmeAlarmsRaw; CLI/inventory tools are hidden this turn.]",
        "[短指令：License/容量。优先 ume_alarm_xlsx_report(mode=list, keyword=license) 或 "
        "aggregate/queryUmeAlarmsRaw；本轮已隐藏 CLI/清单。]",
    ),
    "congestion": (
        "[Ops short-intent: bandwidth congestion. Prefer ume_alarm_xlsx_report(mode=list) or "
        "aggregateUmeAlarms/queryUmeAlarmsRaw; CLI/inventory/sql are hidden this turn.]",
        "[短指令：带宽拥塞。优先 ume_alarm_xlsx_report(mode=list) 或 aggregate/query；"
        "本轮已隐藏 CLI/清单/sql。]",
    ),
    "continue": (
        "[Ops short-intent: continue/confirm. Resume the unfinished prior task immediately; "
        "do not re-ask confirmation or restart the query from scratch.]",
        "[短指令：继续/确认。立即承接上一未完成任务；勿再问确认或重开查询。]",
    ),
}

# Report-style short intents: hide inventory/CLI loops that dominate WA tool spam.
_REPORT_TOOL_FILTER_INTENTS = frozenset(
    {"fiber_cut", "offline", "alarm_tally", "excel_export", "license", "congestion"}
)

# Match bare tool names and mcp__netx__* / legacy netx_* aliases.
_SUPPRESSED_TOOL_NAMES = frozenset(
    {
        "listclitargets",
        "listmanagedne",
        "getmanagedne",
        "execmanagedne",
        "queryumeneinventory",
        "getumene",
        "findtopologypaths",
        "sqlqueryume",
        "run_command",
        "netx_list_managed_ne",
        "netx_get_managed_ne",
        "netx_exec_managed_ne",
        "netx_sql_query_ume",
        "netx_list_cli_targets",
    }
)


def _tool_name_key(name: str) -> str:
    raw = str(name or "").strip()
    if not raw:
        return ""
    # mcp__netx__listManagedNe -> listManagedNe
    if "__" in raw:
        raw = raw.rsplit("__", 1)[-1]
    return raw.strip().lower()


def ops_short_intent_should_filter_tools(intent: str | None) -> bool:
    return str(intent or "").strip() in _REPORT_TOOL_FILTER_INTENTS


def is_ops_short_intent_suppressed_tool(tool_name: str, *, intent: str | None) -> bool:
    if not ops_short_intent_should_filter_tools(intent):
        return False
    key = _tool_name_key(tool_name)
    return bool(key) and key in _SUPPRESSED_TOOL_NAMES


def filter_tool_specs_for_ops_short_intent(tools: list[Any], *, intent: str | None) -> list[Any]:
    """Drop inventory/CLI tools for report-style short intents (keep alarm/xlsx path)."""
    if not ops_short_intent_should_filter_tools(intent):
        return list(tools or [])
    out: list[Any] = []
    for spec in tools or []:
        name = str(getattr(spec, "name", "") or "")
        if is_ops_short_intent_suppressed_tool(name, intent=intent):
            continue
        out.append(spec)
    return out


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
    "filter_tool_specs_for_ops_short_intent",
    "is_ops_short_intent_suppressed_tool",
    "maybe_ops_short_intent_system_hint",
    "normalize_ops_user_text",
    "ops_short_intent_should_filter_tools",
    "reset_group_mention_nudge_throttle_for_tests",
    "should_send_group_mention_nudge",
]
