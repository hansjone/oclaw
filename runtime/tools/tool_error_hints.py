from __future__ import annotations

import difflib
from typing import Any, Iterable


def suggest_tool_names(requested: str, available: Iterable[str], *, n: int = 5) -> list[str]:
    """Suggest close tool names for unregistered-tool errors."""
    name = str(requested or "").strip()
    pool = [str(x).strip() for x in available if str(x).strip()]
    if not name or not pool:
        return []
    # Prefer substring matches (mcp__netx__foo vs netx__foo / queryUmeAlarmsRaw).
    low = name.lower()
    substr = [p for p in pool if low in p.lower() or p.lower() in low]
    close = difflib.get_close_matches(name, pool, n=max(n, 8), cutoff=0.45)
    out: list[str] = []
    for x in substr + close:
        if x not in out:
            out.append(x)
        if len(out) >= n:
            break
    return out


def format_unregistered_tool_error(
    tool_name: str,
    available: Iterable[str],
    *,
    lang: str = "zh",
) -> dict[str, Any]:
    suggestions = suggest_tool_names(tool_name, available)
    if str(lang or "").startswith("en"):
        err = f"Unregistered tool: {tool_name}"
        hint = (
            "Use one of suggestions, or refresh MCP tools for this specialist."
            if suggestions
            else "Tool is not in the current registry; check MCP enablement / specialist binding."
        )
    else:
        err = f"未注册的工具: {tool_name}"
        hint = (
            "请改用 suggestions 中的工具名，或检查该专家的 MCP 绑定/启用状态。"
            if suggestions
            else "当前工具目录中无此工具；请检查 MCP 是否启用及专家绑定。"
        )
    out: dict[str, Any] = {
        "ok": False,
        "error_code": "tool_not_registered",
        "error": err,
        "hint": hint,
    }
    if suggestions:
        out["suggestions"] = suggestions
    return out


def enrich_mcp_scope_error(result: dict[str, Any]) -> dict[str, Any]:
    """Rewrite insufficient_scope MCP errors into actionable ops guidance."""
    if not isinstance(result, dict) or result.get("ok") is not False:
        return result
    err = str(result.get("error") or "")
    code = str(result.get("error_code") or "")
    blob = f"{err} {code}".lower()
    if "insufficient_scope" not in blob and "insufficient_scope" not in err:
        return result
    scope = ""
    marker = "insufficient_scope:"
    if marker in err:
        scope = err.split(marker, 1)[1].strip().split()[0].strip("\"'")
    elif marker in code:
        scope = code.split(marker, 1)[1].strip()
    out = dict(result)
    out["error_code"] = "insufficient_scope"
    if scope:
        out["required_scope"] = scope
    out["error"] = f"insufficient_scope:{scope}" if scope else "insufficient_scope"
    if scope == "sql:query":
        out["hint"] = (
            "Current netx token lacks sql:query. Prefer aggregateUmeAlarms / queryUmeAlarmsRaw / "
            "ume_alarm_xlsx_report; ask an admin to grant sql:query only if SQL is required."
        )
        out["fallback_tools"] = [
            "mcp__netx__aggregateUmeAlarms",
            "mcp__netx__queryUmeAlarmsRaw",
            "ume_alarm_xlsx_report",
        ]
    else:
        out["hint"] = (
            f"Current netx token lacks scope {scope or '(unknown)'}. "
            "Ask an admin to grant it on the netx API token, or use tools that do not need this scope."
        )
    return out


__all__ = [
    "enrich_mcp_scope_error",
    "format_unregistered_tool_error",
    "suggest_tool_names",
]
