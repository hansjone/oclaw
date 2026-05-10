from __future__ import annotations

from typing import Any

REMINDER_NAME = "SELF_IMPROVEMENT_REMINDER.md"
REMINDER_PATH = REMINDER_NAME

REMINDER_CONTENT = """## 自我改进提醒

任务完成后，请评估是否产生可沉淀学习。

仅在当前仓库/工作区启用 self-improvement 技能时记录。

记录前：
- 使用 memory_wiki_* 工具写入 `improvement/` 下的 Wiki 笔记
- 不记录密钥、令牌、私钥、环境变量或原始对话全文
- 优先使用简短摘要或脱敏片段，避免完整命令输出

**以下情况应记录：**
- 用户纠正你 → `improvement/learnings.md`
- 命令/操作失败 → `improvement/errors.md`
- 用户提出缺失能力 → `improvement/feature-requests.md`
- 发现认知错误 → `improvement/learnings.md`
- 发现更优做法 → `improvement/learnings.md`

**当模式被验证后进行提升：**
- 行为模式 → `SOUL.md`
- 工作流改进 → `AGENTS.md`
- 工具易错点 → `TOOLS.md`

条目保持简洁：时间、标题、发生了什么、后续应如何做。"""


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
