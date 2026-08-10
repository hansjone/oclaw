from __future__ import annotations

import json
import re
from typing import Any


COMPLEX_PROMPT_HINTS = (
    "刚才",
    "之前",
    "继续",
    "按刚才",
    "同样的",
    "那件事",
    "那套",
    "流程",
    "步骤",
    "生成",
    "报告",
    "文档",
    "pdf",
    "xlsx",
    "附件",
    "发群",
    "发给",
    "执行",
    "整理",
    "汇总",
    "拉取",
    "爬取",
    "监控",
    "same as",
    "continue",
    "as before",
    "workflow",
    "report",
    "generate",
    "attach",
)


def _as_str_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        item = raw.strip()
        return [item] if item else []
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        text = str(item or "").strip()
        if text:
            out.append(text)
    return out


def _as_str_dict(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in raw.items():
        k = str(key or "").strip()
        if not k:
            continue
        out[k] = str(value if value is not None else "").strip()
    return out


def parse_recipe_arg(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except Exception:
            return None
    return None


def normalize_recipe(raw: Any) -> dict[str, Any]:
    data = parse_recipe_arg(raw) or {}
    goal = str(data.get("goal") or "").strip()
    steps = _as_str_list(data.get("steps"))
    constraints = _as_str_list(data.get("constraints"))
    success_criteria = _as_str_list(data.get("success_criteria") or data.get("successCriteria"))
    inputs_raw = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    constants = _as_str_dict(inputs_raw.get("constants"))
    from_context = _as_str_list(inputs_raw.get("from_context") or inputs_raw.get("fromContext"))
    output_raw = data.get("output") if isinstance(data.get("output"), dict) else {}
    source_raw = data.get("source") if isinstance(data.get("source"), dict) else {}
    version = int(data.get("version") or 1)
    recipe: dict[str, Any] = {
        "version": max(1, version),
        "goal": goal,
        "steps": steps,
        "constraints": constraints,
        "success_criteria": success_criteria,
        "inputs": {
            "constants": constants,
            "from_context": from_context,
        },
        "output": {
            "style": str(output_raw.get("style") or "channel_update").strip() or "channel_update",
            "need_attachments": bool(output_raw.get("need_attachments") or output_raw.get("needAttachments")),
        },
        "source": {
            "session_id": str(source_raw.get("session_id") or source_raw.get("sessionId") or "").strip(),
            "compiled_at": str(source_raw.get("compiled_at") or source_raw.get("compiledAt") or "").strip(),
            "compiled_from": str(source_raw.get("compiled_from") or source_raw.get("compiledFrom") or "").strip(),
        },
    }
    return recipe


def recipe_is_empty(recipe: dict[str, Any] | None) -> bool:
    if not recipe:
        return True
    norm = normalize_recipe(recipe)
    return not (norm.get("goal") or norm.get("steps") or norm.get("success_criteria") or norm.get("constraints"))


def recipe_has_playbook(recipe: dict[str, Any] | None) -> bool:
    if not recipe:
        return False
    norm = normalize_recipe(recipe)
    steps = list(norm.get("steps") or [])
    goal = str(norm.get("goal") or "").strip()
    return bool(goal) and len(steps) >= 2


def recipe_missing_fields(recipe: dict[str, Any] | None) -> list[str]:
    norm = normalize_recipe(recipe or {})
    missing: list[str] = []
    if not str(norm.get("goal") or "").strip():
        missing.append("goal")
    steps = list(norm.get("steps") or [])
    if len(steps) < 2:
        missing.append("steps")
    if not list(norm.get("success_criteria") or []):
        missing.append("success_criteria")
    return missing


def looks_like_complex_schedule_prompt(prompt_text: str, *, recipe: dict[str, Any] | None = None) -> bool:
    """Heuristic: multi-step / referential prompts need a recipe."""
    if recipe_has_playbook(recipe):
        return True
    text = str(prompt_text or "").strip()
    if not text:
        return False
    low = text.lower()
    if any(hint in low or hint in text for hint in COMPLEX_PROMPT_HINTS):
        # Short pure reminders like "提醒喝水" should stay simple.
        if len(text) <= 12 and ("提醒" in text or "remind" in low) and "步骤" not in text:
            return False
        return True
    if len(text) >= 80:
        return True
    if text.count("\n") >= 2:
        return True
    if re.search(r"(1[\.\)]|第一步|step\s*1)", text, flags=re.I):
        return True
    return False


_STEP_HEADER_RE = re.compile(
    r"(?im)^\s*(?:"
    r"step\s*\d+\s*[—\-–:.]?\s*"
    r"|第[0-9一二三四五六七八九十百]+步\s*[—\-–:.]?\s*"
    r"|\d+\s*[\.\)\-—–]\s+"
    r").+$"
)


def _extract_numbered_steps(prompt_text: str) -> tuple[str, list[str]]:
    """Split prompt into (preamble, step bodies) when Step N / 1. headers exist."""
    text = str(prompt_text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return "", []
    matches = list(_STEP_HEADER_RE.finditer(text))
    if len(matches) < 2:
        return text, []
    preamble = text[: matches[0].start()].strip()
    steps: list[str] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk = text[m.start() : end].strip()
        # Drop leading "Step N —" / "1." so compile_playbook can re-number cleanly.
        body = re.sub(
            r"(?is)^\s*(?:step\s*\d+|第[0-9一二三四五六七八九十百]+步)\s*[—\-–:.]?\s*",
            "",
            chunk,
            count=1,
        )
        body = re.sub(r"(?is)^\s*\d+\s*[\.\)\-—–]\s+", "", body, count=1).strip()
        if body:
            steps.append(body)
        elif chunk:
            steps.append(chunk)
    return preamble, steps


def synthesize_recipe_from_prompt(prompt_text: str, *, session_id: str = "") -> dict[str, Any] | None:
    """
    Build a durable playbook recipe from a long/structured prompt.

    Used when field jobs stored algorithm text in prompt_text but left recipe_json empty.
    Returns None when the prompt is too thin to treat as a playbook.
    """
    text = str(prompt_text or "").strip()
    if not text or not looks_like_complex_schedule_prompt(text):
        return None

    preamble, steps = _extract_numbered_steps(text)
    low = text.lower()
    need_attachments = any(
        tok in low or tok in text
        for tok in ("xlsx", "csv", "pdf", "attachment", "附件", "save_deliverable", "write_xlsx")
    )

    if len(steps) >= 2:
        goal = preamble.split("\n\n", 1)[0].strip() if preamble else ""
        goal = re.sub(r"(?is)^\s*critical\s*[—\-–:]?\s*", "", goal).strip()
        if not goal:
            goal = steps[0][:240]
        if len(goal) > 400:
            goal = goal[:397].rstrip() + "..."
        # Prefer keeping full algorithm fidelity: if preamble is short, fold remaining
        # non-step prose into constraints rather than losing it.
        constraints: list[str] = []
        if preamble and preamble != goal and len(preamble) > len(goal) + 20:
            rest = preamble[len(goal) :].strip() if preamble.startswith(goal) else preamble
            if rest:
                constraints.append(rest[:800])
        success = [
            "Follow every step end-to-end with tools as needed.",
            "Deliver a useful channel update reflecting completed work.",
        ]
        if need_attachments:
            success.append("Generated files are saved via save_deliverable_attachment.")
        recipe = normalize_recipe(
            {
                "version": 1,
                "goal": goal,
                "steps": steps,
                "constraints": constraints,
                "success_criteria": success,
                "output": {"need_attachments": need_attachments, "style": "channel_update"},
                "source": {
                    "session_id": str(session_id or "").strip(),
                    "compiled_at": "",
                    "compiled_from": "prompt_text",
                },
            }
        )
        # Preserve compiled_from beyond normalize (normalize only keeps session_id/compiled_at).
        recipe.setdefault("source", {})["compiled_from"] = "prompt_text"
        return recipe

    # No clear Step N headers: still promote long ops prompts so they are not
    # misclassified as short "reminder" turns.
    if len(text) < 80 and text.count("\n") < 2:
        return None
    goal = text.split("\n\n", 1)[0].strip()
    if len(goal) > 400:
        goal = goal[:397].rstrip() + "..."
    steps = [
        "Execute the full algorithm described in the goal/prompt end-to-end. Use tools as needed; do not reply with only a short reminder.",
        "Deliver a useful channel update that reflects completed work"
        + (" (call save_deliverable_attachment for any generated files)." if need_attachments else "."),
    ]
    if text != goal:
        steps.insert(1, f"Full prompt/algorithm to follow:\n{text}")
    recipe = normalize_recipe(
        {
            "version": 1,
            "goal": goal,
            "steps": steps,
            "constraints": [],
            "success_criteria": [
                "Workflow completed with tools as required.",
                "Channel update delivered.",
            ],
            "output": {"need_attachments": need_attachments, "style": "channel_update"},
            "source": {"session_id": str(session_id or "").strip(), "compiled_at": ""},
        }
    )
    recipe.setdefault("source", {})["compiled_from"] = "prompt_text"
    return recipe


def resolve_effective_playbook_recipe(
    *,
    recipe: dict[str, Any] | None,
    prompt_text: str,
    session_id: str = "",
) -> dict[str, Any] | None:
    """Return a playbook recipe from stored recipe or synthesized prompt; else None."""
    if recipe_has_playbook(recipe):
        return normalize_recipe(recipe)
    synth = synthesize_recipe_from_prompt(prompt_text, session_id=session_id)
    if recipe_has_playbook(synth):
        return synth
    return None


def prompt_summary_from_recipe(recipe: dict[str, Any] | None, *, fallback: str = "") -> str:
    norm = normalize_recipe(recipe or {})
    goal = str(norm.get("goal") or "").strip()
    if goal:
        return goal
    steps = list(norm.get("steps") or [])
    if steps:
        return steps[0]
    return str(fallback or "").strip()


def recipe_list_summary(recipe: dict[str, Any] | None) -> dict[str, Any]:
    """Compact playbook signals for schedule_list / admin tables."""
    norm = normalize_recipe(recipe or {})
    steps = list(norm.get("steps") or [])
    goal = str(norm.get("goal") or "").strip()
    playbook = bool(goal) and len(steps) >= 2
    return {
        "playbook": playbook,
        "has_recipe": not recipe_is_empty(norm),
        "steps_n": len(steps),
        "recipe_goal": goal[:240],
    }


def preview_markdown(
    *,
    name: str,
    schedule_kind: str,
    schedule_expr: str,
    timezone_name: str,
    recipe: dict[str, Any],
    lang: str = "zh",
) -> str:
    norm = normalize_recipe(recipe)
    is_en = str(lang or "").lower().startswith("en")
    lines: list[str] = []
    if is_en:
        lines.append("## Scheduled workflow draft (confirm before create)")
        lines.append(f"- **Name**: {name or '(untitled)'}")
        lines.append(f"- **Schedule**: `{schedule_kind}` `{schedule_expr}` ({timezone_name or 'system'})")
        lines.append(f"- **Goal**: {norm.get('goal') or '(missing)'}")
        lines.append("### Steps")
        for i, step in enumerate(list(norm.get("steps") or []), start=1):
            lines.append(f"{i}. {step}")
        constraints = list(norm.get("constraints") or [])
        if constraints:
            lines.append("### Constraints")
            for item in constraints:
                lines.append(f"- {item}")
        criteria = list(norm.get("success_criteria") or [])
        if criteria:
            lines.append("### Success criteria")
            for item in criteria:
                lines.append(f"- {item}")
        constants = dict((norm.get("inputs") or {}).get("constants") or {})
        if constants:
            lines.append("### Fixed inputs")
            for key, value in constants.items():
                lines.append(f"- `{key}`: {value}")
        lines.append("")
        lines.append("Reply **confirm** to create, or list the edits you want.")
    else:
        lines.append("## 定时工作流草稿（请确认后再创建）")
        lines.append(f"- **名称**：{name or '（未命名）'}")
        lines.append(f"- **时间**：`{schedule_kind}` `{schedule_expr}`（{timezone_name or '系统时区'}）")
        lines.append(f"- **目标**：{norm.get('goal') or '（缺失）'}")
        lines.append("### 步骤")
        for i, step in enumerate(list(norm.get("steps") or []), start=1):
            lines.append(f"{i}. {step}")
        constraints = list(norm.get("constraints") or [])
        if constraints:
            lines.append("### 约束")
            for item in constraints:
                lines.append(f"- {item}")
        criteria = list(norm.get("success_criteria") or [])
        if criteria:
            lines.append("### 成功标准")
            for item in criteria:
                lines.append(f"- {item}")
        constants = dict((norm.get("inputs") or {}).get("constants") or {})
        if constants:
            lines.append("### 固定输入")
            for key, value in constants.items():
                lines.append(f"- `{key}`：{value}")
        lines.append("")
        lines.append("请回复**确认**以创建，或说明要修改的地方。")
    return "\n".join(lines).strip()


def compile_playbook_instruction(*, recipe: dict[str, Any], lang: str = "zh") -> str:
    norm = normalize_recipe(recipe)
    is_en = str(lang or "").lower().startswith("en")
    steps = list(norm.get("steps") or [])
    constraints = list(norm.get("constraints") or [])
    criteria = list(norm.get("success_criteria") or [])
    constants = dict((norm.get("inputs") or {}).get("constants") or {})
    from_context = list((norm.get("inputs") or {}).get("from_context") or [])
    need_attachments = bool((norm.get("output") or {}).get("need_attachments"))

    if is_en:
        lines = [
            "[Scheduled playbook — internal instruction, not a user message]",
            f"Goal: {norm.get('goal') or '(unspecified)'}",
            "Execute this recurring playbook end-to-end. Use tools as needed.",
            "Do not reply with only a short reminder unless the playbook is truly reminder-only.",
            "Steps:",
        ]
        for i, step in enumerate(steps, start=1):
            lines.append(f"{i}. {step}")
        if constraints:
            lines.append("Constraints:")
            lines.extend(f"- {c}" for c in constraints)
        if criteria:
            lines.append("Success criteria:")
            lines.extend(f"- {c}" for c in criteria)
        if constants:
            lines.append("Fixed inputs:")
            lines.extend(f"- {k}: {v}" for k, v in constants.items())
        if from_context:
            lines.append("Pull from context when needed:")
            lines.extend(f"- {item}" for item in from_context)
        if need_attachments:
            lines.append(
                "If files are produced, call save_deliverable_attachment so channel delivery includes them."
            )
        lines.append("Deliver a useful channel update that reflects completed work.")
        return "\n".join(lines)

    lines = [
        "【定时工作流·内部指令，不是用户发言】",
        f"目标：{norm.get('goal') or '（未指定）'}",
        "请按下方 playbook 完整执行本轮定时任务；按需调用工具。",
        "除非任务本身只是提醒，否则不要只回一句短提醒。",
        "步骤：",
    ]
    for i, step in enumerate(steps, start=1):
        lines.append(f"{i}. {step}")
    if constraints:
        lines.append("约束：")
        lines.extend(f"- {c}" for c in constraints)
    if criteria:
        lines.append("成功标准：")
        lines.extend(f"- {c}" for c in criteria)
    if constants:
        lines.append("固定输入：")
        lines.extend(f"- {k}：{v}" for k, v in constants.items())
    if from_context:
        lines.append("需要时从上下文获取：")
        lines.extend(f"- {item}" for item in from_context)
    if need_attachments:
        lines.append("若产生文件，必须调用 save_deliverable_attachment，渠道才会随消息发送附件。")
    lines.append("完成后向渠道发送能体现已完成工作的更新消息。")
    return "\n".join(lines)


def load_recipe_from_job(job: Any) -> dict[str, Any]:
    raw = getattr(job, "recipe_json", None)
    if raw is None and isinstance(job, dict):
        raw = job.get("recipe_json") or job.get("recipe")
    if isinstance(raw, dict):
        return normalize_recipe(raw)
    text = str(raw or "").strip()
    if not text:
        return normalize_recipe({})
    try:
        data = json.loads(text)
    except Exception:
        return normalize_recipe({})
    return normalize_recipe(data if isinstance(data, dict) else {})


# Built-in ops playbooks for WhatsApp field schedules (English-first).
_OPS_RECIPE_TEMPLATE_ALIASES: dict[str, str] = {
    "alarm_tally": "ume_alarm_tally_daily",
    "alarm_tally_daily": "ume_alarm_tally_daily",
    "critical_xlsx": "ume_critical_xlsx_daily",
    "critical_xlsx_daily": "ume_critical_xlsx_daily",
    "license_check": "ne_license_check_weekly",
    "license_weekly": "ne_license_check_weekly",
    "congestion": "bandwidth_congestion_daily",
    "bandwidth": "bandwidth_congestion_daily",
    "bandwidth_congestion": "bandwidth_congestion_daily",
}

OPS_RECIPE_TEMPLATES: dict[str, dict[str, Any]] = {
    "ume_alarm_tally_daily": {
        "version": 1,
        "goal": "Post daily UME open-alarm tally to the ops WhatsApp group",
        "steps": [
            "Call runUmeDiagnostics or aggregateUmeAlarms for current open alarms",
            "Summarize by_severity, top NEs, and freshness in concise English",
            "Post a short WhatsApp update (skip xlsx unless counts are very large)",
        ],
        "constraints": [
            "Prefer English for WhatsApp field ops",
            "Do not re-list CLI targets/inventory unless required",
            "Do not blind-retry identical failing tool calls",
        ],
        "success_criteria": [
            "Group receives a severity tally that includes freshness",
        ],
        "output": {"need_attachments": False},
    },
    "ume_critical_xlsx_daily": {
        "version": 1,
        "goal": "Send daily critical UME alarm Excel to the ops WhatsApp group",
        "steps": [
            "Call ume_alarm_xlsx_report(mode=aggregate_by_host, severity=critical, deliverable=true)",
            "If that tool is unavailable: aggregateUmeAlarms then write_xlsx(deliverable=true)",
            "Confirm the file is marked deliverable and summarize top hosts in English",
        ],
        "constraints": [
            "Prefer ume_alarm_xlsx_report over multi-step query+xlsx",
            "Never claim a file was sent without deliverable marking",
            "Prefer English for WhatsApp field ops",
        ],
        "success_criteria": [
            "WhatsApp group receives an xlsx attachment of critical alarms by host",
        ],
        "output": {"need_attachments": True},
    },
    "ne_license_check_weekly": {
        "version": 1,
        "goal": "Weekly NE license/capacity check summary for ops WhatsApp",
        "steps": [
            "Resolve target NEs via listManagedNe or known constants (avoid repeated listCliTargets)",
            "Run execManagedNe license/capacity show commands with read_timeout_sec>=60",
            "Summarize near-limit or failed NEs in English; attach xlsx only if many rows",
        ],
        "constraints": [
            "Prefer English for WhatsApp field ops",
            "On timeout/unreachable, classify failure and do not blind-retry identical args",
            "Keep the group update short and actionable",
        ],
        "success_criteria": [
            "Group receives a license/capacity status summary for the target set",
        ],
        "output": {"need_attachments": False},
    },
    "bandwidth_congestion_daily": {
        "version": 1,
        "goal": "Daily bandwidth congestion / utilization hotspot summary for ops WhatsApp",
        "steps": [
            "Call aggregateUmeAlarms or queryUmeAlarmsRaw with bandwidth/congestion/utilization keywords",
            "Optionally ume_alarm_xlsx_report(mode=list) if the user wants a file (deliverable=true)",
            "Summarize top congested hosts/ports in concise English — avoid sqlQueryUme unless scoped",
        ],
        "constraints": [
            "Prefer English for WhatsApp field ops",
            "Do not spam CLI or identical alarm re-queries",
            "If insufficient_scope on SQL, switch to aggregate/report tools immediately",
        ],
        "success_criteria": [
            "Group receives a congestion/utilization hotspot summary with freshness",
        ],
        "output": {"need_attachments": False},
    },
}


def _normalize_template_id(template_id: str) -> str:
    tid = str(template_id or "").strip().lower().replace("-", "_")
    return _OPS_RECIPE_TEMPLATE_ALIASES.get(tid, tid)


def resolve_ops_recipe_template(template_id: str) -> dict[str, Any] | None:
    """Return a normalized recipe for a built-in ops template id, or None."""
    tid = _normalize_template_id(template_id)
    raw = OPS_RECIPE_TEMPLATES.get(tid)
    if not raw:
        return None
    recipe = normalize_recipe(raw)
    src = dict(recipe.get("source") or {})
    src["template_id"] = tid
    recipe["source"] = src
    return recipe


def list_ops_recipe_templates() -> list[dict[str, Any]]:
    """List built-in ops recipe templates (id + goal + attachment hint)."""
    items: list[dict[str, Any]] = []
    for tid, raw in OPS_RECIPE_TEMPLATES.items():
        recipe = normalize_recipe(raw)
        items.append(
            {
                "id": tid,
                "goal": str(recipe.get("goal") or ""),
                "need_attachments": bool((recipe.get("output") or {}).get("need_attachments")),
                "aliases": sorted(k for k, v in _OPS_RECIPE_TEMPLATE_ALIASES.items() if v == tid),
            }
        )
    return items


__all__ = [
    "COMPLEX_PROMPT_HINTS",
    "OPS_RECIPE_TEMPLATES",
    "compile_playbook_instruction",
    "list_ops_recipe_templates",
    "load_recipe_from_job",
    "looks_like_complex_schedule_prompt",
    "normalize_recipe",
    "parse_recipe_arg",
    "preview_markdown",
    "prompt_summary_from_recipe",
    "recipe_has_playbook",
    "recipe_is_empty",
    "recipe_list_summary",
    "recipe_missing_fields",
    "resolve_effective_playbook_recipe",
    "resolve_ops_recipe_template",
    "synthesize_recipe_from_prompt",
]
