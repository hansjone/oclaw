"""Detect ops short intents for WhatsApp/field English recipes."""

from __future__ import annotations

import re
from typing import Any

_BOT_MENTION_RE = re.compile(r"@\S+")

# intent -> (en hint, zh hint)
# Prefer report path strongly; keep CLI/inventory available with soft budget (not hard-hidden).
_HINTS: dict[str, tuple[str, str]] = {
    "excel_export": (
        "[Ops short-intent: Excel export. Prefer ume_alarm_xlsx_report(..., deliverable=true) now. "
        "write_xlsx / run_command are hidden this turn. "
        "CLI/inventory stay available with a soft budget for device checks — prefer one hetero targets batch, not single-NE loops.]",
        "[短指令：导出 Excel。优先 ume_alarm_xlsx_report(..., deliverable=true)。"
        "本轮已隐藏 write_xlsx/run_command。"
        "CLI/清单仍可用（soft budget）：核实设备优先一次 hetero targets batch，勿单台循环。]",
    ),
    "license": (
        "[Ops short-intent: license/capacity. Prefer ume_alarm_xlsx_report(mode=list, keyword=license, deliverable=true) "
        "or aggregateUmeAlarms/queryUmeAlarmsRaw. write_xlsx/run_command hidden; "
        "CLI available with soft budget for confirmation (one targets batch preferred).]",
        "[短指令：License/容量。优先 ume_alarm_xlsx_report(mode=list, keyword=license, deliverable=true) "
        "或 aggregate/queryUmeAlarmsRaw；write_xlsx/run_command 已隐藏；"
        "CLI 可用（soft budget），确认阶段优先一次 targets batch。]",
    ),
    "congestion": (
        "[Ops short-intent: bandwidth congestion. Prefer ume_alarm_xlsx_report(mode=list, deliverable=true) "
        "or aggregateUmeAlarms/queryUmeAlarmsRaw. write_xlsx/run_command hidden; "
        "CLI available with soft budget (one targets batch preferred).]",
        "[短指令：带宽拥塞。优先 ume_alarm_xlsx_report(mode=list, deliverable=true) 或 aggregate/query；"
        "write_xlsx/run_command 已隐藏；CLI 可用（soft budget），优先一次 targets batch。]",
    ),
    "fiber_cut": (
        "[Ops short-intent: fiber/LOS. Prefer ume_alarm_xlsx_report(mode=fiber_cut, deliverable=true) now. "
        "write_xlsx/run_command hidden. CLI/inventory available with soft budget — "
        "use at most one hetero targets batch for device confirmation, not listCliTargets→single-NE loops.]",
        "[短指令：断纤/LOS。优先 ume_alarm_xlsx_report(mode=fiber_cut, deliverable=true)。"
        "write_xlsx/run_command 已隐藏。CLI/清单可用（soft budget）："
        "设备核实最多一次 hetero targets batch，勿 listCliTargets→单台循环。]",
    ),
    "offline": (
        "[Ops short-intent: offline NE. Prefer ume_alarm_xlsx_report(mode=offline, deliverable=true) now. "
        "write_xlsx/run_command hidden; CLI/inventory with soft budget (one targets batch preferred).]",
        "[短指令：离线网元。优先 ume_alarm_xlsx_report(mode=offline, deliverable=true)。"
        "write_xlsx/run_command 已隐藏；CLI/清单 soft budget（优先一次 targets batch）。]",
    ),
    "alarm_tally": (
        "[Ops short-intent: alarm tally/top. Prefer ume_alarm_xlsx_report(mode=aggregate_by_host, deliverable=true) "
        "or aggregateUmeAlarms. write_xlsx/run_command hidden; CLI soft budget for spot checks.]",
        "[短指令：告警统计/Top。优先 ume_alarm_xlsx_report(mode=aggregate_by_host, deliverable=true) "
        "或 aggregateUmeAlarms；write_xlsx/run_command 已隐藏；CLI soft budget 仅作抽检。]",
    ),
    "continue": (
        "[Ops short-intent: continue/confirm. Resume the unfinished prior task immediately; "
        "do not re-ask confirmation or restart the query from scratch.]",
        "[短指令：继续/确认。立即承接上一未完成任务；勿再问确认或重开查询。]",
    ),
}

# Report-style short intents: soft-nudge toward alarm/xlsx; hide only shell/xlsx DIY.
_REPORT_TOOL_FILTER_INTENTS = frozenset(
    {"fiber_cut", "offline", "alarm_tally", "excel_export", "license", "congestion"}
)

# Soft CLI budgets during report short-intents (prefer report; allow limited device checks).
_SHORT_INTENT_CLI_SOFT_SINGLE = 2
_SHORT_INTENT_CLI_SOFT_FAIL = 2
_SHORT_INTENT_CLI_SOFT_BATCH = 1

# Only hard-hide DIY spreadsheet / shell paths — keep inventory + execManagedNe visible.
_SUPPRESSED_TOOL_NAMES = frozenset(
    {
        "run_command",
        "write_xlsx",
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


def ops_short_intent_cli_soft_budgets(intent: str | None) -> dict[str, int] | None:
    """Tighter execManagedNe budgets for report short-intents; None = use global defaults."""
    if not ops_short_intent_should_filter_tools(intent):
        return None
    return {
        "single": int(_SHORT_INTENT_CLI_SOFT_SINGLE),
        "fail": int(_SHORT_INTENT_CLI_SOFT_FAIL),
        "batch": int(_SHORT_INTENT_CLI_SOFT_BATCH),
    }


def is_ops_short_intent_suppressed_tool(tool_name: str, *, intent: str | None) -> bool:
    if not ops_short_intent_should_filter_tools(intent):
        return False
    key = _tool_name_key(tool_name)
    return bool(key) and key in _SUPPRESSED_TOOL_NAMES


def filter_tool_specs_for_ops_short_intent(tools: list[Any], *, intent: str | None) -> list[Any]:
    """Drop DIY xlsx/shell tools for report-style short intents (keep alarm path + CLI)."""
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
    base = zh if str(lang or "").strip().lower().startswith("zh") else en
    try:
        from runtime.tools.playbook_contracts import build_turn_checklist

        checklist = build_turn_checklist(intent=key, lang=lang)
        if checklist:
            return f"{base}\n{checklist}".strip()
    except Exception:
        pass
    return base


def maybe_ops_short_intent_system_hint(*, text: str, lang: str = "en") -> str:
    intent = detect_ops_short_intent(text)
    if not intent:
        return ""
    return build_ops_short_intent_hint(intent=intent, lang=lang)


__all__ = [
    "build_ops_short_intent_hint",
    "detect_ops_short_intent",
    "filter_tool_specs_for_ops_short_intent",
    "is_ops_short_intent_suppressed_tool",
    "maybe_ops_short_intent_system_hint",
    "normalize_ops_user_text",
    "ops_short_intent_cli_soft_budgets",
    "ops_short_intent_should_filter_tools",
]
