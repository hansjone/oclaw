from __future__ import annotations

from typing import Any

from runtime.scheduler.recipe import compile_playbook_instruction, recipe_has_playbook


def format_scheduled_user_reminder(prompt_text: str) -> str:
    body = str(prompt_text or "").strip()
    if not body:
        return ""
    if body.startswith("⏰"):
        return body
    return f"⏰ 提醒：{body}"


def build_scheduled_turn_instruction(
    *,
    prompt_text: str,
    mode: str,
    lang: str,
    recipe: dict[str, Any] | None = None,
) -> str:
    """Internal LLM instruction for proactive scheduled reminders/playbooks (not user-facing)."""
    _ = str(mode or "scheduled").strip()
    if recipe_has_playbook(recipe):
        return compile_playbook_instruction(recipe=recipe or {}, lang=lang)

    intent = str(prompt_text or "").strip()
    is_en = str(lang or "").lower().startswith("en")
    if is_en:
        return (
            "[Scheduled proactive reminder — internal instruction, not a user message]\n"
            f"Reminder intent: {intent}\n"
            "Write a short, friendly proactive reminder TO the user (second person). "
            "Do not say you received a reminder or that you will remind someone; speak directly to the user."
        )
    return (
        "【定时主动提醒·内部指令，不是用户发言】\n"
        f"提醒意图：{intent}\n"
        "请生成一条简短、自然、第二人称的主动提醒消息直接对用户说。"
        "不要写「收到提醒」「好的我来提醒用户」等元对话；不要假装用户刚说了话。"
    )


def scheduled_turn_system_suffix(*, lang: str, playbook: bool = False) -> str:
    is_en = str(lang or "").lower().startswith("en")
    if playbook:
        if is_en:
            return (
                "\n\n[Scheduled playbook mode] You are executing a recurring workflow for the user. "
                "Follow the playbook steps, use tools as needed, and deliver a useful update "
                "(including save_deliverable_attachment for generated files). "
                "Do not pretend the user just messaged you."
            )
        return (
            "\n\n【定时工作流模式】你正在执行周期性工作流。"
            "按 playbook 步骤完成任务，按需调用工具；若生成文件须 save_deliverable_attachment。"
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
    "build_scheduled_turn_instruction",
    "format_scheduled_user_reminder",
    "scheduled_turn_system_suffix",
]
