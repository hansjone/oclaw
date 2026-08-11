"""Playbook contracts ↔ tool schema alignment + idle guard."""

from __future__ import annotations

from runtime.chat.turn_idle_guard import TurnIdleTracker
from runtime.tools.experts.network_ops.ume_alarm_xlsx_report import ume_alarm_xlsx_report_tool
from runtime.tools.playbook_contracts import (
    build_turn_checklist,
    enrich_invalid_arguments_with_playbook,
    playbook_example_for_tool,
    schema_playbook_mismatches,
    short_intent_first_step,
)
from runtime.tools.public.write_xlsx_tool import write_xlsx_tool
from runtime.tools.tool_validation import format_invalid_arguments_error


def test_ume_alarm_xlsx_playbook_examples_match_schema() -> None:
    tool = ume_alarm_xlsx_report_tool()
    issues = schema_playbook_mismatches(tool.name, tool.parameters)
    assert issues == [], issues


def test_write_xlsx_playbook_examples_match_schema() -> None:
    tool = write_xlsx_tool()
    issues = schema_playbook_mismatches(tool.name, tool.parameters)
    assert issues == [], issues


def test_short_intent_first_step_fiber_cut() -> None:
    step = short_intent_first_step("fiber_cut")
    assert step is not None
    tool, example = step
    assert tool == "ume_alarm_xlsx_report"
    assert example.get("mode") == "fiber_cut"
    assert example.get("deliverable") is True


def test_checklist_contains_step1_tool() -> None:
    text = build_turn_checklist(intent="offline", lang="en", goal="offline NE list")
    assert "ume_alarm_xlsx_report" in text
    assert "mode=\"offline\"" in text or "offline" in text
    assert "Turn checklist" in text


def test_invalid_args_enriched_with_playbook_example() -> None:
    tool = ume_alarm_xlsx_report_tool()
    raw = format_invalid_arguments_error(
        tool.parameters or {},
        "'bogus' is not one of ['list', 'aggregate_by_host', 'fiber_cut', 'offline']",
        lang="en",
        tool_name="ume_alarm_xlsx_report",
        intent="fiber_cut",
    )
    assert raw.get("playbook_example") is True
    assert raw.get("example", {}).get("mode") == "fiber_cut"
    assert "Playbook recipe" in str(raw.get("hint") or "")


def test_enrich_invalid_arguments_mcp_alias() -> None:
    base = {
        "ok": False,
        "error_code": "tool_invalid_arguments",
        "example": {"severity": "x"},
        "hint": "fix it",
    }
    out = enrich_invalid_arguments_with_playbook(
        base,
        tool_name="mcp__netx__aggregateUmeAlarms",
        intent="alarm_tally",
    )
    assert out["example"].get("top_ne") == 20
    assert out.get("playbook_example") is True


def test_idle_guard_nudges_short_intent_narration() -> None:
    tracker = TurnIdleTracker(lang="en", short_intent="fiber_cut")
    d1 = tracker.decide_after_assistant_no_tools()
    assert d1.action == "nudge"
    assert "Idle guard" in d1.nudge_text
    assert "ume_alarm_xlsx_report" in d1.nudge_text
    d2 = tracker.decide_after_assistant_no_tools()
    assert d2.action == "continue"


def test_idle_guard_early_finalize_on_idle_streak() -> None:
    tracker = TurnIdleTracker(lang="en", short_intent="alarm_tally", max_idle_rounds=2)
    # Round 1: all failures
    s1 = tracker.record_from_traces(
        round_idx=1,
        had_tool_calls=True,
        round_traces=[{"name": "ume_alarm_xlsx_report", "ok": False}],
        results_by_id={
            "1": (
                {
                    "ok": False,
                    "error_code": "tool_invalid_arguments",
                    "failure_class": "schema_validation",
                },
                10,
            )
        },
    )
    d1 = tracker.decide_after_tools(s1)
    assert d1.action in {"nudge", "continue", "early_finalize"}
    # Round 2: still no success
    s2 = tracker.record_from_traces(
        round_idx=2,
        had_tool_calls=True,
        round_traces=[{"name": "ume_alarm_xlsx_report", "ok": False}],
        results_by_id={
            "2": (
                {
                    "ok": False,
                    "error_code": "identical_retry_blocked",
                    "failure_class": "retry_guard",
                },
                5,
            )
        },
    )
    d2 = tracker.decide_after_tools(s2)
    assert d2.action == "early_finalize"
    assert d2.reason in {"idle_no_progress", "schema_fail_budget"}


def test_playbook_example_for_mcp_namespaced_tool() -> None:
    ex = playbook_example_for_tool("mcp__netx__execManagedNe")
    assert ex is not None
    assert "commands" in ex
