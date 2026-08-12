from __future__ import annotations

from runtime.application.gateway.ops_short_intent import (
    detect_ops_short_intent,
    filter_tool_specs_for_ops_short_intent,
    is_ops_short_intent_suppressed_tool,
    maybe_ops_short_intent_system_hint,
)
from runtime.tools.base import ToolSpec
from runtime.tools.tool_error_hints import enrich_exec_managed_ne_error, enrich_get_managed_ne_error


def test_detect_ops_short_intent_english_field() -> None:
    assert detect_ops_short_intent("@bot fiber cut sites") == "fiber_cut"
    assert detect_ops_short_intent("offline NE list") == "offline"
    assert detect_ops_short_intent("please continue") == "continue"
    assert detect_ops_short_intent("YES") == "continue"
    assert detect_ops_short_intent("export excel") == "excel_export"
    assert detect_ops_short_intent("critical top alarms") == "alarm_tally"
    assert detect_ops_short_intent("hello there how are you doing today with something else") is None


def test_ops_short_intent_suppresses_inventory_cli_tools() -> None:
    assert is_ops_short_intent_suppressed_tool("mcp__netx__listCliTargets", intent="fiber_cut")
    assert is_ops_short_intent_suppressed_tool("mcp__netx__execManagedNe", intent="offline")
    assert is_ops_short_intent_suppressed_tool("run_command", intent="excel_export")
    assert is_ops_short_intent_suppressed_tool("write_xlsx", intent="fiber_cut")
    assert is_ops_short_intent_suppressed_tool("write_xlsx", intent="excel_export")
    assert not is_ops_short_intent_suppressed_tool("ume_alarm_xlsx_report", intent="fiber_cut")
    assert not is_ops_short_intent_suppressed_tool("mcp__netx__queryUmeAlarmsRaw", intent="alarm_tally")
    assert not is_ops_short_intent_suppressed_tool("mcp__netx__execManagedNe", intent="continue")


def test_filter_tool_specs_for_ops_short_intent_keeps_report_path() -> None:
    def _spec(name: str) -> ToolSpec:
        return ToolSpec(
            name=name,
            description="t",
            parameters={"type": "object", "properties": {}},
            handler=lambda _a: {"ok": True},
        )

    tools = [
        _spec("mcp__netx__listCliTargets"),
        _spec("mcp__netx__execManagedNe"),
        _spec("ume_alarm_xlsx_report"),
        _spec("mcp__netx__aggregateUmeAlarms"),
        _spec("write_xlsx"),
        _spec("run_command"),
    ]
    kept = filter_tool_specs_for_ops_short_intent(tools, intent="fiber_cut")
    names = {t.name for t in kept}
    assert "ume_alarm_xlsx_report" in names
    assert "mcp__netx__aggregateUmeAlarms" in names
    assert "write_xlsx" not in names
    assert "mcp__netx__listCliTargets" not in names
    assert "mcp__netx__execManagedNe" not in names
    assert "run_command" not in names
    assert len(filter_tool_specs_for_ops_short_intent(tools, intent="continue")) == len(tools)


def test_ops_short_intent_hint_english_default() -> None:
    hint = maybe_ops_short_intent_system_hint(text="LOS on these sites", lang="en")
    assert "fiber" in hint.lower() or "LOS" in hint
    assert "ume_alarm_xlsx_report" in hint
    assert "断纤" not in hint


def test_enrich_exec_timeout() -> None:
    out = enrich_exec_managed_ne_error(
        {"ok": False, "error_code": "tool_timeout_or_failed", "error": "timeout"}
    )
    assert out["error_class"] == "timeout"
    assert "read_timeout_sec" in out["hint"]


def test_enrich_exec_unreachable_nested_json() -> None:
    nested = '{"ok": false, "error": "ssh_connect failed: host unreachable"}'
    out = enrich_exec_managed_ne_error(
        {"ok": False, "error_code": "mcp_tool_call_failed", "error": nested}
    )
    assert out["error_class"] == "unreachable"
    assert "unreachable" in out["hint"].lower()


def test_enrich_get_managed_ne_not_found() -> None:
    out = enrich_get_managed_ne_error(
        {"ok": False, "error": "netx_http_404", "error_code": "netx_http_404", "detail": "Not Found"}
    )
    assert out["error_class"] == "not_found"
    assert "listManagedNe" in out["hint"]
    assert "ume_ne_id" in out["hint"]
    assert "listManagedNe" in " ".join(out.get("next_tools") or [])


def test_enrich_get_managed_ne_id_required() -> None:
    out = enrich_get_managed_ne_error(
        {"ok": False, "error": "ne_id_required", "error_code": "ne_id_required"}
    )
    assert out["error_class"] == "ne_id_required"
    assert "listManagedNe" in out["hint"]
    assert out.get("example")
