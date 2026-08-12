"""Canonical ops playbook tool contracts.

Keeps skill recipes (ops-netx-*-playbook) and runtime JSON schemas aligned by
providing executable examples used in:

- invalid-argument error payloads (self-correct without blind retry)
- short-intent turn checklists
- schema↔playbook regression tests
"""

from __future__ import annotations

from typing import Any

# Bare MCP tool names (without mcp__netx__) and always-on expert tools.
_PLAYBOOK_EXAMPLES: dict[str, dict[str, dict[str, Any]]] = {
    "ume_alarm_xlsx_report": {
        "fiber_cut": {"mode": "fiber_cut", "deliverable": True},
        "offline": {"mode": "offline", "deliverable": True},
        "alarm_tally": {"mode": "aggregate_by_host", "severity": "critical", "deliverable": True},
        "excel_export": {"mode": "list", "deliverable": True},
        "license": {"mode": "list", "keyword": "license", "deliverable": True},
        "congestion": {"mode": "list", "keyword": "bandwidth", "deliverable": True},
        "default": {"mode": "list", "deliverable": True},
    },
    "write_xlsx": {
        "excel_export": {
            "sheets": [{"name": "Sheet1", "headers": ["host_name", "count"], "rows": [["NE-1", 1]]}],
            "deliverable": True,
            "name": "alarms.xlsx",
        },
        "default": {
            "sheets": [{"name": "Sheet1", "headers": ["col"], "rows": [["val"]]}],
            "deliverable": True,
            "name": "report.xlsx",
        },
    },
    "aggregateumealarms": {
        "alarm_tally": {"severity": "critical", "top_ne": 20},
        "default": {"severity": "critical", "top_ne": 20},
    },
    "queryumealarms": {
        "default": {"host_name": "<host_name>", "page_size": 50},
    },
    "queryumealarmsraw": {
        "congestion": {"keyword": "bandwidth", "field_preset": "evidence", "page_size": 50},
        "license": {"keyword": "license", "field_preset": "evidence", "page_size": 50},
        "default": {"keyword": "<cause>", "field_preset": "evidence", "page_size": 50},
    },
    "runumediagnostics": {
        "default": {},
    },
    "listmanagedne": {
        "default": {"keyword": "<host_or_area>", "connect_status": "pass"},
    },
    "getmanagedne": {
        "default": {"ne_id": "<managed-ne-id-from-listManagedNe>"},
    },
    "execmanagedne": {
        "default": {
            "ume_ne_ids": ["<ume-uuid-1>", "<ume-uuid-2>"],
            "commands": ["show version"],
            "read_timeout_sec": 60,
        },
    },
    "listclitargets": {
        "default": {"source": "ume", "keyword": "<host_or_area>"},
    },
    "findtopologypaths": {
        "default": {
            "from_ume_ne_id": "<ume-uuid-a>",
            "to_ume_ne_id": "<ume-uuid-b>",
            "detail": "summary",
        },
    },
}

# Short-intent → preferred first tool + example key (playbook recipe).
_SHORT_INTENT_FIRST_STEP: dict[str, tuple[str, str]] = {
    "fiber_cut": ("ume_alarm_xlsx_report", "fiber_cut"),
    "offline": ("ume_alarm_xlsx_report", "offline"),
    "alarm_tally": ("ume_alarm_xlsx_report", "alarm_tally"),
    "excel_export": ("ume_alarm_xlsx_report", "excel_export"),
    "license": ("ume_alarm_xlsx_report", "license"),
    "congestion": ("ume_alarm_xlsx_report", "congestion"),
}


def canonical_tool_key(tool_name: str) -> str:
    raw = str(tool_name or "").strip()
    if not raw:
        return ""
    if "__" in raw:
        raw = raw.rsplit("__", 1)[-1]
    # Legacy snake_case netx_* → last segment style already handled by rsplit.
    if raw.lower().startswith("netx_"):
        raw = raw[5:]
    return raw.strip().lower()


def playbook_examples_for_tool(tool_name: str) -> dict[str, dict[str, Any]]:
    return dict(_PLAYBOOK_EXAMPLES.get(canonical_tool_key(tool_name)) or {})


def playbook_example_for_tool(
    tool_name: str,
    *,
    intent: str | None = None,
) -> dict[str, Any] | None:
    examples = playbook_examples_for_tool(tool_name)
    if not examples:
        return None
    key = str(intent or "").strip()
    if key and key in examples:
        return dict(examples[key])
    if "default" in examples:
        return dict(examples["default"])
    # First recipe as fallback.
    first = next(iter(examples.values()), None)
    return dict(first) if isinstance(first, dict) else None


def short_intent_first_step(intent: str | None) -> tuple[str, dict[str, Any]] | None:
    key = str(intent or "").strip()
    if not key:
        return None
    pair = _SHORT_INTENT_FIRST_STEP.get(key)
    if not pair:
        return None
    tool, example_key = pair
    example = playbook_example_for_tool(tool, intent=example_key) or {}
    return tool, example


def build_turn_checklist(
    *,
    intent: str | None = None,
    lang: str = "en",
    goal: str | None = None,
) -> str:
    """Compact in-turn checklist injected into system prompt (ops short intents)."""
    step = short_intent_first_step(intent)
    is_zh = str(lang or "").strip().lower().startswith("zh")
    lines: list[str] = []
    if is_zh:
        lines.append("[本轮 checklist — 先工具后结论，禁止只叙述不调用]")
    else:
        lines.append("[Turn checklist — call tools first; do not narrate-only]")
    goal_s = str(goal or "").strip()
    if goal_s:
        lines.append(f"- goal: {goal_s[:160]}")
    if step:
        tool, example = step
        lines.append(f"- step1 (REQUIRED first): {tool}({_fmt_args(example)})")
        if is_zh:
            lines.append("- 未完成 step1 前禁止 listCliTargets/execManagedNe/清单循环")
            lines.append("- 完成后用 Result/Evidence 短答；勿翻页或开无关 playbook")
        else:
            lines.append("- Do NOT call listCliTargets/execManagedNe/inventory before step1 succeeds")
            lines.append("- then reply with Result/Evidence; no pagination / unrelated playbooks")
    elif is_zh:
        lines.append("- 需要证据时立刻调用工具；失败时改参数或换 fallback，禁止相同参数盲重试")
    else:
        lines.append("- If evidence is required, call a tool now; on failure change args or switch tools")
    return "\n".join(lines)


def enrich_invalid_arguments_with_playbook(
    payload: dict[str, Any],
    *,
    tool_name: str,
    intent: str | None = None,
) -> dict[str, Any]:
    """Attach playbook-aligned example when schema validation fails."""
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    example = playbook_example_for_tool(tool_name, intent=intent)
    if example:
        # Prefer playbook recipe over generic schema-derived example.
        out["example"] = example
        out["playbook_example"] = True
        prior = str(out.get("hint") or "").strip()
        tip = f"Playbook recipe: {_fmt_args(example)}"
        if tip not in prior:
            out["hint"] = f"{prior} {tip}".strip() if prior else tip
    out["tool"] = str(tool_name or "").strip() or out.get("tool")
    return out


def schema_playbook_mismatches(
    tool_name: str,
    parameters: dict[str, Any] | None,
) -> list[str]:
    """Return human-readable mismatches between playbook examples and JSON schema."""
    from runtime.tools.tool_validation import validate_tool_arguments

    examples = playbook_examples_for_tool(tool_name)
    if not examples or not isinstance(parameters, dict) or not parameters:
        return []
    issues: list[str] = []
    for label, args in examples.items():
        ok, err = validate_tool_arguments(parameters, dict(args))
        if not ok:
            issues.append(f"{canonical_tool_key(tool_name)}/{label}: {err}")
    return issues


def _fmt_args(args: dict[str, Any]) -> str:
    parts: list[str] = []
    for k, v in (args or {}).items():
        if isinstance(v, bool):
            parts.append(f"{k}={'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            parts.append(f"{k}={v}")
        elif isinstance(v, str):
            parts.append(f'{k}="{v}"')
        else:
            parts.append(f"{k}=…")
    return ", ".join(parts)


__all__ = [
    "build_turn_checklist",
    "canonical_tool_key",
    "enrich_invalid_arguments_with_playbook",
    "playbook_example_for_tool",
    "playbook_examples_for_tool",
    "schema_playbook_mismatches",
    "short_intent_first_step",
]
