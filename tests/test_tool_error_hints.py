from __future__ import annotations

from runtime.tools.tool_error_hints import (
    enrich_mcp_scope_error,
    format_unregistered_tool_error,
    suggest_tool_names,
)


def test_suggest_tool_names_prefers_substring() -> None:
    pool = [
        "mcp__netx__queryUmeAlarms",
        "mcp__netx__queryUmeAlarmsRaw",
        "mcp__netx__aggregateUmeAlarms",
        "write_xlsx",
    ]
    hits = suggest_tool_names("mcp__netx__queryUmeAlarmsRaw", pool)
    assert "mcp__netx__queryUmeAlarmsRaw" in hits or "mcp__netx__queryUmeAlarms" in hits


def test_format_unregistered_includes_suggestions() -> None:
    out = format_unregistered_tool_error(
        "mcp__netx__queryUmeAlarmsRaw",
        ["mcp__netx__queryUmeAlarms", "mcp__netx__aggregateUmeAlarms", "ume_alarm_xlsx_report"],
        lang="en",
    )
    assert out["error_code"] == "tool_not_registered"
    assert out.get("suggestions")
    assert any("queryUmeAlarms" in s for s in out["suggestions"])


def test_enrich_mcp_scope_sql() -> None:
    raw = {"ok": False, "error_code": "mcp_rpc_error_-32001", "error": "insufficient_scope:sql:query"}
    out = enrich_mcp_scope_error(raw)
    assert out["error_code"] == "insufficient_scope"
    assert out.get("failure_class") == "auth"
    assert out.get("retry_forbidden") is True
    assert "aggregateUmeAlarms" in str(out.get("hint") or "")
    assert "SQL query is not enabled" in str(out.get("user_facing_hint") or "")
    assert out["required_scope"] == "sql:query"
    assert "fallback_tools" in out
    assert "ume_alarm_xlsx_report" in out["fallback_tools"]


def test_build_finalize_system_suffix() -> None:
    from runtime.tools.tool_error_hints import build_finalize_system_suffix

    en = build_finalize_system_suffix(
        lang="en",
        hit_tool_round_limit=True,
        user_facing_hints=["SQL query is not enabled for this bot token."],
    )
    assert "Tool-round limit" in en
    assert "SQL query is not enabled" in en
    assert "do NOT call" in en
    zh = build_finalize_system_suffix(lang="zh", hit_tool_round_limit=True)
    assert "工具轮次" in zh


def test_enrich_exec_auth() -> None:
    from runtime.tools.tool_error_hints import enrich_exec_managed_ne_error

    out = enrich_exec_managed_ne_error({"ok": False, "error": "authentication failed: Permission denied"})
    assert out["error_class"] == "auth"
