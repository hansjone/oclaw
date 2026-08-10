from __future__ import annotations

from typing import Any

from runtime.scheduler.recipe import compile_playbook_instruction, recipe_has_playbook


def format_scheduled_user_reminder(prompt_text: str, *, lang: str = "en") -> str:
    body = str(prompt_text or "").strip()
    if not body:
        return ""
    if body.startswith("⏰"):
        return body
    if str(lang or "").lower().startswith("zh"):
        return f"⏰ 提醒：{body}"
    return f"⏰ Reminder: {body}"


def format_scheduled_success_summary(
    *,
    job_name: str = "",
    job_id: str = "",
    reply_text: str = "",
    attachment_count: int = 0,
    lang: str = "en",
    max_body_chars: int = 1200,
) -> str:
    """Short user-facing success notice; keeps body but caps length for WhatsApp."""
    name = str(job_name or "").strip() or str(job_id or "").strip() or "scheduled job"
    body = str(reply_text or "").strip()
    # Drop pure reminder fallbacks that just echo the job prompt.
    if body.startswith("⏰"):
        body = ""
    att_n = max(0, int(attachment_count or 0))
    cap = max(200, int(max_body_chars or 1200))
    if body and len(body) > cap:
        body = body[: cap - 3].rstrip() + "..."
    if str(lang or "").lower().startswith("zh"):
        head = f"[定时任务完成] {name}"
        if att_n:
            head += f"\n附件：{att_n} 个"
        if body:
            return f"{head}\n{body}"
        return head + ("\n（本次无文字摘要，请查看附件。）" if att_n else "\n（本次无摘要内容。）")
    head = f"[Scheduled job done] {name}"
    if att_n:
        head += f"\nAttachments: {att_n}"
    if body:
        return f"{head}\n{body}"
    return head + ("\n(No text summary; see attachment(s).)" if att_n else "\n(No summary content.)")


def format_scheduled_failure_summary(
    *,
    job_name: str = "",
    job_id: str = "",
    error: str = "",
    lang: str = "en",
) -> str:
    """Short user-facing failure notice for WhatsApp/WeChat scheduled delivery."""
    name = str(job_name or "").strip() or str(job_id or "").strip() or "scheduled job"
    err = " ".join(str(error or "").strip().split())
    if len(err) > 240:
        err = err[:237] + "..."
    if not err:
        err = "unknown error"
    if str(lang or "").lower().startswith("zh"):
        return f"[定时任务失败] {name}\n错误：{err}\n请检查任务配置或手动重试。"
    return f"[Scheduled job failed] {name}\nError: {err}\nCheck the job config or retry manually."


def format_scheduled_skip_summary(
    *,
    job_name: str = "",
    job_id: str = "",
    overlapping_run_id: str = "",
    lang: str = "en",
) -> str:
    """User-facing notice when a due tick is skipped because a prior run is still active."""
    name = str(job_name or "").strip() or str(job_id or "").strip() or "scheduled job"
    oid = str(overlapping_run_id or "").strip()
    if str(lang or "").lower().startswith("zh"):
        lines = [
            f"[定时任务跳过] {name}",
            "原因：上一轮仍在运行（overlapping），本轮已跳过以免叠跑。",
        ]
        if oid:
            lines.append(f"进行中的 run：{oid[:12]}")
        return "\n".join(lines)
    lines = [
        f"[Scheduled job skipped] {name}",
        "Reason: previous run still active (overlapping); this tick was skipped.",
    ]
    if oid:
        lines.append(f"Active run: {oid[:12]}")
    return "\n".join(lines)


def build_scheduled_turn_instruction(
    *,
    prompt_text: str,
    mode: str,
    lang: str,
    recipe: dict[str, Any] | None = None,
    previous_run: dict[str, Any] | None = None,
) -> str:
    """Internal LLM instruction for proactive scheduled reminders/playbooks (not user-facing)."""
    _ = str(mode or "scheduled").strip()
    if recipe_has_playbook(recipe):
        text = compile_playbook_instruction(recipe=recipe or {}, lang=lang)
    else:
        intent = str(prompt_text or "").strip()
        is_en = str(lang or "").lower().startswith("en")
        if is_en:
            text = (
                "[Scheduled proactive reminder — internal instruction, not a user message]\n"
                f"Reminder intent: {intent}\n"
                "Write a short, friendly proactive reminder TO the user (second person). "
                "Do not say you received a reminder or that you will remind someone; speak directly to the user."
            )
        else:
            text = (
                "【定时主动提醒·内部指令，不是用户发言】\n"
                f"提醒意图：{intent}\n"
                "请生成一条简短、自然、第二人称的主动提醒消息直接对用户说。"
                "不要写「收到提醒」「好的我来提醒用户」等元对话；不要假装用户刚说了话。"
            )
    return append_previous_run_context(text, previous_run=previous_run, lang=lang)


def append_previous_run_context(
    instruction: str,
    *,
    previous_run: dict[str, Any] | None,
    lang: str = "en",
    max_body_chars: int = 800,
) -> str:
    """Append a short prior-run note so recurring jobs can compare deltas."""
    base = str(instruction or "").rstrip()
    if not previous_run or not isinstance(previous_run, dict):
        return base
    status = str(previous_run.get("status") or "").strip() or "unknown"
    finished = str(previous_run.get("finished_at") or previous_run.get("created_at") or "").strip()
    err = " ".join(str(previous_run.get("error") or "").split())
    body = " ".join(str(previous_run.get("reply_text") or "").split())
    # Prefer error text on failures; otherwise the outbound summary.
    if status.lower() in {"failed", "error"} and err:
        body = err
    cap = max(120, int(max_body_chars or 800))
    if len(body) > cap:
        body = body[: cap - 3].rstrip() + "..."
    if not body and not finished:
        return base
    is_en = str(lang or "").lower().startswith("en")
    if is_en:
        lines = [
            "",
            "[Previous run context — for continuity only; still execute this run fully]",
            f"Status: {status}" + (f" | Finished: {finished}" if finished else ""),
        ]
        if body:
            lines.append(f"Summary: {body}")
        lines.append(
            "Use this for deltas/comparisons when useful; do not skip work just because the prior run succeeded."
        )
    else:
        lines = [
            "",
            "【上一轮运行摘要·仅供对照；本轮仍须完整执行】",
            f"状态：{status}" + (f"｜完成时间：{finished}" if finished else ""),
        ]
        if body:
            lines.append(f"摘要：{body}")
        lines.append("可参考做环比/差异，但不要因上轮成功而跳过本轮步骤。")
    return base + "\n" + "\n".join(lines)


def scheduled_turn_system_suffix(*, lang: str, playbook: bool = False) -> str:
    is_en = str(lang or "").lower().startswith("en")
    if playbook:
        if is_en:
            return (
                "\n\n[Scheduled playbook mode] You are executing a recurring workflow for the user. "
                "Follow the playbook steps, use tools as needed, and deliver a useful update "
                "(including save_deliverable_attachment for generated files). "
                "Lead the final reply with a short English summary (3–8 lines: what ran, key counts, "
                "ok/failed highlights), then optional detail. "
                "Do not pretend the user just messaged you."
            )
        return (
            "\n\n【定时工作流模式】你正在执行周期性工作流。"
            "按 playbook 步骤完成任务，按需调用工具；若生成文件须 save_deliverable_attachment。"
            "最终回复先给 3–8 行摘要（做了什么、关键计数、成败），再写细节。"
            "不要假装用户刚刚发了消息，不要只回一句空提醒。"
        )
    if is_en:
        return (
            "\n\n[Scheduled job mode] You are sending a proactive reminder to the user. "
            "Reply with the reminder text only; do not role-play as the user."
        )
    return (
        "\n\n【定时任务模式】你正在主动向用户发送提醒。"
        "只输出提醒正文，不要扮演用户，不要写「收到/好的」等对话式应答。"
    )


__all__ = [
    "append_previous_run_context",
    "build_scheduled_turn_instruction",
    "format_scheduled_failure_summary",
    "format_scheduled_skip_summary",
    "format_scheduled_success_summary",
    "format_scheduled_user_reminder",
    "scheduled_turn_system_suffix",
]
