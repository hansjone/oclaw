from __future__ import annotations

from typing import Any

REMINDER_NAME = "SELF_IMPROVEMENT_REMINDER.md"
REMINDER_PATH = REMINDER_NAME

REMINDER_CONTENT = """## Self-Improvement Reminder

After completing tasks, evaluate whether any learnings should be captured.

Only log if this repo or workspace is using the self-improvement skill.

Before logging:
- Create only missing `.learnings/` files; never overwrite existing content
- Do not log secrets, tokens, private keys, environment variables, or raw transcripts
- Prefer short summaries or redacted excerpts over full command output

**Log when:**
- User corrects you → `.learnings/LEARNINGS.md`
- Command/operation fails → `.learnings/ERRORS.md`
- User wants missing capability → `.learnings/FEATURE_REQUESTS.md`
- You discover your knowledge was wrong → `.learnings/LEARNINGS.md`
- You find a better approach → `.learnings/LEARNINGS.md`

**Promote when pattern is proven:**
- Behavioral patterns → `SOUL.md`
- Workflow improvements → `AGENTS.md`
- Tool gotchas → `TOOLS.md`

Keep entries simple: date, title, what happened, and what to do differently."""


def _is_record(value: object) -> bool:
    return isinstance(value, dict)


def _is_injected_reminder_file(value: object) -> bool:
    if not _is_record(value) or str(value.get("path")) != REMINDER_PATH:  # type: ignore[union-attr]
        return False
    v = value  # type: ignore[assignment]
    return v.get("virtual") is True or v.get("content") == REMINDER_CONTENT


def handle(event: object) -> None:
    if getattr(event, "type", None) != "agent" or getattr(event, "action", None) != "bootstrap":
        return
    ctx = getattr(event, "context", None)
    if not isinstance(ctx, dict):
        return
    session_key = str(getattr(event, "sessionKey", "") or "")
    if ":subagent:" in session_key:
        return

    if not isinstance(ctx.get("bootstrapFiles"), list):
        return
    files: list[object] = list(ctx.get("bootstrapFiles") or [])

    occupied = any(
        _is_record(f) and str(f.get("path")) == REMINDER_PATH and not _is_injected_reminder_file(f)  # type: ignore[union-attr]
        for f in files
    )
    if occupied:
        return

    cleaned: list[object] = [
        f
        for i, f in enumerate(files)
        if (not _is_injected_reminder_file(f))
        or (next((j for j, c in enumerate(files) if _is_injected_reminder_file(c)), -1) == i)
    ]

    reminder_file: dict[str, Any] = {
        "name": REMINDER_NAME,
        "path": REMINDER_PATH,
        "content": REMINDER_CONTENT,
        "missing": False,
        "virtual": True,
    }
    existing_idx = next((i for i, f in enumerate(cleaned) if _is_injected_reminder_file(f)), -1)
    if existing_idx == -1:
        cleaned.append(reminder_file)
    else:
        cleaned[existing_idx] = reminder_file
    ctx["bootstrapFiles"] = cleaned
