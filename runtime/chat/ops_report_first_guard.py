"""Report-first gate for ops short intents: CLI/inventory only after report path."""

from __future__ import annotations

import json
from typing import Any

from runtime.application.gateway.ops_short_intent import ops_short_intent_should_filter_tools
from runtime.tools.playbook_contracts import playbook_example_for_tool, short_intent_first_step

# Tools blocked until a report-path tool succeeds this turn.
_CLI_BEFORE_REPORT_TOOLS = frozenset(
    {
        "listclitargets",
        "listmanagedne",
        "getmanagedne",
        "execmanagedne",
        "queryumeneinventory",
        "getumene",
        "findtopologypaths",
        "sqlqueryume",
        "netx_list_managed_ne",
        "netx_get_managed_ne",
        "netx_exec_managed_ne",
        "netx_sql_query_ume",
        "netx_list_cli_targets",
    }
)

# Successful call to any of these unlocks CLI for the rest of the turn.
_REPORT_PATH_TOOLS = frozenset(
    {
        "ume_alarm_xlsx_report",
        "aggregateumealarms",
        "aggregateumealarmsraw",
    }
)


def _tool_key(name: str) -> str:
    raw = str(name or "").strip()
    if not raw:
        return ""
    if "__" in raw:
        raw = raw.rsplit("__", 1)[-1]
    return raw.strip().lower().replace("-", "_")


def is_cli_before_report_tool(tool_name: str) -> bool:
    return _tool_key(tool_name) in _CLI_BEFORE_REPORT_TOOLS


def is_report_path_tool(tool_name: str) -> bool:
    return _tool_key(tool_name) in _REPORT_PATH_TOOLS


def _parse_json_obj(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def turn_has_successful_report_path(
    store: Any,
    *,
    session_id: str,
    turn_uuid: str,
) -> bool:
    """True if this turn already has a successful report/aggregate tool result."""
    tu = str(turn_uuid or "").strip()
    sid = str(session_id or "").strip()
    if not tu or not sid or store is None:
        return False
    try:
        rows = store.get_messages(session_id=sid, limit=500)
    except Exception:
        return False
    for m in rows or []:
        if str(getattr(m, "role", "") or "").strip().lower() != "tool":
            continue
        if str(getattr(m, "turn_uuid", "") or "").strip() != tu:
            continue
        ep = _parse_json_obj(getattr(m, "event_payload", None))
        name = str(ep.get("tool_name") or "").strip()
        if not name:
            tc = _parse_json_obj(getattr(m, "tool_calls", None))
            name = str(tc.get("name") or "").strip()
        if not is_report_path_tool(name):
            continue
        if ep.get("ok") is True:
            return True
        try:
            payload = json.loads(str(getattr(m, "content", "") or "") or "{}")
        except Exception:
            payload = {}
        if isinstance(payload, dict) and payload.get("ok") is True:
            return True
    return False


def report_first_block_payload(*, intent: str | None, lang: str = "en") -> dict[str, Any]:
    en = str(lang or "").strip().lower().startswith("en")
    step = short_intent_first_step(intent)
    tool = "ume_alarm_xlsx_report"
    example = playbook_example_for_tool(tool, intent=intent) or {"mode": "list", "deliverable": True}
    if step:
        tool, example = step[0], step[1]
    hint = (
        f"Report-first gate: call {tool} successfully before CLI/inventory this turn. "
        "Device confirmation via execManagedNe is allowed only after the report path returns ok."
        if en
        else f"报表优先：本轮先成功调用 {tool}，再允许 CLI/清单。"
        "设备核实（execManagedNe）仅在报表路径 ok 之后。"
    )
    return {
        "ok": False,
        "error_code": "report_first_required",
        "failure_class": "report_first",
        "error": "report_first_required",
        "hint": hint,
        "next_tool": tool,
        "example": example,
        "intent": str(intent or ""),
    }


def maybe_block_cli_before_report(
    *,
    tool_name: str,
    intent: str | None,
    store: Any,
    session_id: str,
    turn_uuid: str,
    lang: str = "en",
    local_report_ok: bool = False,
) -> dict[str, Any] | None:
    """Return a block payload when CLI/inventory is used before report on short intents."""
    if not ops_short_intent_should_filter_tools(intent):
        return None
    if not is_cli_before_report_tool(tool_name):
        return None
    if local_report_ok:
        return None
    if turn_has_successful_report_path(store, session_id=session_id, turn_uuid=turn_uuid):
        return None
    return report_first_block_payload(intent=intent, lang=lang)


__all__ = [
    "is_cli_before_report_tool",
    "is_report_path_tool",
    "maybe_block_cli_before_report",
    "report_first_block_payload",
    "turn_has_successful_report_path",
]
