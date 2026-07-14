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


def prompt_summary_from_recipe(recipe: dict[str, Any] | None, *, fallback: str = "") -> str:
    norm = normalize_recipe(recipe or {})
    goal = str(norm.get("goal") or "").strip()
    if goal:
        return goal
    steps = list(norm.get("steps") or [])
    if steps:
        return steps[0]
    return str(fallback or "").strip()


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


__all__ = [
    "COMPLEX_PROMPT_HINTS",
    "compile_playbook_instruction",
    "load_recipe_from_job",
    "looks_like_complex_schedule_prompt",
    "normalize_recipe",
    "parse_recipe_arg",
    "preview_markdown",
    "prompt_summary_from_recipe",
    "recipe_has_playbook",
    "recipe_is_empty",
    "recipe_missing_fields",
]
