from __future__ import annotations

from pathlib import Path

from .models import PLAN_MODE_PLAN, PlanAgentStateV2


def _plan_file_info(state: PlanAgentStateV2) -> str:
    plan_path = str(state.plan_path or "").strip()
    if not plan_path:
        return "No plan file path is available yet."
    p = Path(plan_path)
    if p.exists():
        return (
            f"A plan file already exists at {plan_path}. "
            "You can read it and make incremental edits."
        )
    return (
        f"No plan file exists yet. You should create your plan at {plan_path}."
    )


def build_plan_mode_prefix(*, state: PlanAgentStateV2, lang: str) -> str:
    if state.mode != PLAN_MODE_PLAN:
        return ""
    is_en = str(lang or "").startswith("en")
    file_info = _plan_file_info(state)
    if is_en:
        return (
            "Plan mode is active. The user does not want execution yet.\n"
            "You MUST NOT make real project edits, run non-readonly tools, or claim implementation is done.\n"
            "## Execution discipline (critical)\n"
            "- Do NOT narrate as if you will run scripts, migrate files, or touch disk *in this turn*. "
            "Phrases like \"I'll write the script and run it\", \"starting migration now\", or "
            "\"let me execute\" mislead the user—refuse that pattern.\n"
            "- If the user needs real execution, say explicitly: switch to **agent mode** in the UI, "
            "then confirm; you cannot perform execution while plan mode is active.\n"
            "- Do NOT repeat the same \"next I will…\" monologue across turns. On vague follow-ups, "
            "edit the plan file or ask **one** concrete question—do not restate boilerplate.\n"
            "- Do not ask the user to \"approve the plan\" in chat when the product expects mode switch + "
            "confirm; instead tell them the handoff: agent mode → confirm to execute.\n\n"
            "## Plan File Info\n"
            f"{file_info}\n"
            "Only the plan file is allowed to be edited while in plan mode.\n\n"
            "## Plan Workflow\n"
            "### Phase 1: Initial Understanding\n"
            "- Understand the request and inspect relevant codepaths.\n"
            "- Reuse existing functions/utilities/patterns when possible.\n\n"
            "### Phase 2: Design\n"
            "- Propose a concrete implementation strategy with trade-offs.\n\n"
            "### Phase 3: Review\n"
            "- Validate alignment with user intent and constraints.\n"
            "- Clarify unresolved requirements only when necessary.\n\n"
            "### Phase 4: Final Plan\n"
            "- Output sections: Context, Changes, Critical files, Verification.\n"
            "- Prefer one recommended approach over listing many alternatives.\n\n"
            "### Phase 5: Execution Handoff\n"
            "- Ask user to switch to agent mode and confirm before execution.\n"
            "- Do not execute while still in plan mode.\n\n"
            "## Plan mode tools (lifecycle)\n"
            "- Built-in tools `enter_plan_mode_v2` and `exit_plan_mode_v2` mirror cc-mini-style "
            "Enter/Exit plan mode: they bind or release plan-mode state for this session.\n"
            "- Prefer updating the plan file in place while staying in plan mode; only call "
            "`enter_plan_mode_v2` with `force_new_plan: true` when the user explicitly wants a new plan document.\n"
            "- When the written plan is ready for review, either keep plan mode and summarize next steps for the user, "
            "or call `exit_plan_mode_v2`. Use `confirm: true` only when the user has explicitly approved executing "
            "this plan; use `confirm: false` to leave plan mode without marking the plan approved for execution.\n"
            "- If the user sends low-content prompts such as 'continue' or 'ok', do not repeat long boilerplate; "
            "revise the plan file or ask one concrete clarification."
        )
    return (
        "当前处于 plan 模式，用户暂不要求执行。\n"
        "你必须不做真实项目改动、不调用非只读工具，也不要声称已经实现完成。\n"
        "## 执行纪律（必须遵守）\n"
        "- 禁止用「我现在写脚本并执行」「开始迁移/复制」「让我跑一下」等表述，假装本回合会动磁盘或执行命令。\n"
        "- 若用户需要真实执行，必须明确说明：请在界面切换到 **agent 模式**，再按产品流程确认；"
        "在 plan 模式下你无法代为执行。\n"
        "- 禁止多轮重复同一套「接下来我将……」的独白；用户只说「继续/好的」时，应小幅改计划文件或只提一个具体问题，"
        "不要复读长模板。\n"
        "- 不要用闲聊式「你同意这个计划吗？」代替产品要求的 **切 agent + 确认**；应提示用户按界面切换到 agent 模式后再确认执行。\n\n"
        "## 计划文件信息\n"
        f"{file_info}\n"
        "在 plan 模式下，只允许围绕计划文件进行编辑。\n\n"
        "## 计划工作流\n"
        "### 阶段1：理解问题\n"
        "- 先理解需求并检查相关代码路径。\n"
        "- 优先复用现有函数、工具和既有模式。\n\n"
        "### 阶段2：方案设计\n"
        "- 给出可落地的实现方案，并说明关键取舍。\n\n"
        "### 阶段3：对齐复核\n"
        "- 核对是否满足用户目标与约束。\n"
        "- 仅在必要时提出澄清问题。\n\n"
        "### 阶段4：最终计划\n"
        "- 输出结构：背景、改动点、关键文件、验证方式。\n"
        "- 推荐一个主方案，不要只堆备选项。\n\n"
        "### 阶段5：执行切换\n"
        "- 明确提示用户先切换到 agent 模式并确认后再执行。\n"
        "- 在 plan 模式下不要执行实现。\n\n"
        "## 计划模式工具（生命周期）\n"
        "- 内置工具 `enter_plan_mode_v2` 与 `exit_plan_mode_v2` 对应 cc-mini 风格的进入/退出计划模式，用于绑定或释放本会话的 plan 状态。\n"
        "- 优先在 plan 模式下就地更新计划文件；仅在用户明确要求新开计划文档时，才对 `enter_plan_mode_v2` 使用 `force_new_plan: true`。\n"
        "- 计划文档写完后，可继续保持 plan 模式并给用户摘要；也可调用 `exit_plan_mode_v2`。仅在用户已明确同意按该计划执行时使用 "
        "`confirm: true`；若只是结束规划、尚未批准执行，使用 `confirm: false`。\n"
        "- 若用户输入信息量低的续写（如「继续」「好的」），不要重复大段套话，应小幅修订计划文件或提出一个具体问题。"
    )


def inject_plan_context(*, base_system: str, state: PlanAgentStateV2, lang: str, max_chars: int = 3000) -> str:
    plan_text = str(state.plan_content or "").strip()
    if not plan_text:
        return base_system
    if len(plan_text) > max_chars:
        plan_text = plan_text[:max_chars] + "\n...<plan_truncated>"
    is_en = str(lang or "").startswith("en")
    header = "Approved plan context:\n" if is_en else "已确认计划上下文：\n"
    return f"{header}{plan_text}\n\n{str(base_system or '').strip()}".strip()


__all__ = ["build_plan_mode_prefix", "inject_plan_context"]

