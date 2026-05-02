from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .manager import PlanModeManagerV2
from .models import PLAN_MODE_PLAN
from .prompt_injector import build_plan_mode_prefix, inject_plan_context
from .trace import emit_plan_agent_v2_trace


@dataclass(frozen=True)
class PlanAgentV2Decision:
    action: str  # enter_plan | stay_plan | run_agent
    reply_text: str
    plan_state: dict[str, Any]
    system_prompt_override: str = ""


def _is_confirm_text(text: str) -> bool:
    t = str(text or "").strip().lower()
    return t in {"确认", "确认计划", "同意", "通过", "approve", "approved", "confirm", "yes"}


def _normalize_user_text(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def _is_low_signal_continue(text_norm: str) -> bool:
    t = str(text_norm or "").strip().lower()
    return t in {
        "继续",
        "继续啊",
        "继续吧",
        "可以",
        "好的",
        "好",
        "ok",
        "okay",
        "go on",
        "continue",
    }


def _confirm_strategy(store: Any) -> str:
    try:
        raw = str(store.get_setting("AIA_EXPERT_PLAN_CONFIRM_STRATEGY") or "").strip().lower()
    except Exception:
        raw = ""
    if raw in {"auto", "strict", "off"}:
        return raw
    return "strict"


def _last_user_text_norm_from_history(*, store: Any, session_id: str) -> str:
    """Most recent persisted user message (current turn is usually not persisted yet)."""
    try:
        msgs = store.get_messages(session_id=session_id, limit=120)
    except Exception:
        return ""
    for m in reversed(msgs):
        if str(getattr(m, "role", "") or "").strip().lower() == "user":
            return _normalize_user_text(str(getattr(m, "content", "") or ""))
    return ""


def _agent_conversation_stall_suffix(*, lang: str) -> str:
    is_en = str(lang or "").startswith("en")
    if is_en:
        return (
            "\n\n[Conversation stall guard — agent mode]\n"
            "The user's latest message matches their previous user message in this session.\n"
            "- Do not repeat your last assistant reply or restate \"I will now…\" boilerplate.\n"
            "- Make substantive progress: execute the next concrete tool step, produce new actionable output, "
            "or ask exactly one specific blocking question.\n"
        )
    return (
        "\n\n【对话停滞防护 · agent 模式】\n"
        "检测到用户本条输入与上一轮用户输入相同（会话已持久化部分）。\n"
        "- 禁止复述上一轮助手回复或重复「接下来我将…」式独白。\n"
        "- 必须给出实质进展：执行具体工具步骤、写出新的可执行结果，或只提一个关键追问。\n"
    )


def evaluate_for_expert_mode(
    *,
    store: Any,
    session_id: str,
    lang: str,
    requested_specialist: str,
    user_text: str,
    execution_mode: str = "agent",
    base_system_prompt: str,
    trace_id: str | None = None,
    parent_span_id: str | None = None,
) -> PlanAgentV2Decision:
    mgr = PlanModeManagerV2(store=store)
    st = mgr.load_state(session_id=session_id)
    txt = str(user_text or "").strip()
    txt_norm = _normalize_user_text(txt)
    exec_mode = str(execution_mode or "").strip().lower()
    if exec_mode not in {"agent", "plan"}:
        exec_mode = "plan"
    confirm_strategy = _confirm_strategy(store)

    if exec_mode == "agent" and st.mode != PLAN_MODE_PLAN:
        emit_plan_agent_v2_trace(
            store=store,
            session_id=session_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            event_type="plan_mode_bypassed",
            payload={"requested_mode": "agent", "plan_mode_state": str(st.mode or "")},
        )
        last_user_norm = _last_user_text_norm_from_history(store=store, session_id=session_id)
        stall = bool(txt_norm and last_user_norm and txt_norm == last_user_norm)
        override = ""
        if stall:
            emit_plan_agent_v2_trace(
                store=store,
                session_id=session_id,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                event_type="agent_mode_conversation_stall",
                payload={"reason": "repeated_user_message"},
            )
            base = str(base_system_prompt or "").strip()
            suffix = _agent_conversation_stall_suffix(lang=lang).strip()
            override = f"{base}\n\n{suffix}".strip()
        return PlanAgentV2Decision(
            action="run_agent",
            reply_text="",
            plan_state=st.to_dict(),
            system_prompt_override=override,
        )

    if st.mode != PLAN_MODE_PLAN:
        entered = mgr.enter(session_id=session_id, owner_specialist=requested_specialist, force_new_plan=False)
        emit_plan_agent_v2_trace(
            store=store,
            session_id=session_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            event_type="plan_mode_entered",
            payload={"owner_specialist": entered.owner_specialist, "plan_id": entered.plan_id},
        )
        prefix = build_plan_mode_prefix(state=entered, lang=lang)
        return PlanAgentV2Decision(
            action="run_agent",
            reply_text="",
            plan_state=entered.to_dict(),
            system_prompt_override=f"{prefix}\n\n{str(base_system_prompt or '').strip()}".strip(),
        )

    st = mgr.refresh_plan_content(session_id=session_id)
    st = mgr.update_loop_guard(session_id=session_id, user_text_norm=txt_norm)
    if _is_confirm_text(txt):
        if exec_mode != "agent" and confirm_strategy == "strict":
            emit_plan_agent_v2_trace(
                store=store,
                session_id=session_id,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                event_type="plan_mode_confirm_blocked",
                payload={
                    "reason": "execution_mode_not_agent",
                    "requested_mode": exec_mode,
                    "confirm_strategy": confirm_strategy,
                },
            )
            blocked_reply = (
                "Plan is ready. Please switch to agent mode, then confirm to execute."
                if str(lang or "").startswith("en")
                else "计划已就绪。请先切换到 agent 模式，再回复“确认”开始执行。"
            )
            return PlanAgentV2Decision(
                action="stay_plan",
                reply_text=blocked_reply,
                plan_state=st.to_dict(),
                system_prompt_override="",
            )
        if exec_mode != "agent" and confirm_strategy == "auto":
            emit_plan_agent_v2_trace(
                store=store,
                session_id=session_id,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                event_type="plan_mode_confirm_auto_switched",
                payload={"from_mode": exec_mode, "to_mode": "agent", "confirm_strategy": confirm_strategy},
            )
        confirmed = mgr.confirm(session_id=session_id)
        emit_plan_agent_v2_trace(
            store=store,
            session_id=session_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            event_type="plan_mode_confirmed",
            payload={
                "plan_id": confirmed.plan_id,
                "plan_confirmed": bool(confirmed.plan_confirmed),
                "confirm_strategy": confirm_strategy,
            },
        )
        next_system = inject_plan_context(base_system=base_system_prompt, state=confirmed, lang=lang)
        reply = mgr.build_approved_execution_message(state=confirmed, lang=lang)
        return PlanAgentV2Decision(
            action="run_agent",
            reply_text=reply,
            plan_state=confirmed.to_dict(),
            system_prompt_override=next_system,
        )

    if _is_low_signal_continue(txt_norm):
        emit_plan_agent_v2_trace(
            store=store,
            session_id=session_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            event_type="plan_mode_active",
            payload={"plan_id": st.plan_id, "plan_path": st.plan_path, "loop_guard": "low_signal_continue"},
        )
        low_signal_reply = (
            "Plan mode detected a low-information continuation. "
            "Please provide concrete plan adjustments, or switch to agent mode and reply 'confirm' to execute."
            if str(lang or "").startswith("en")
            else "检测到低信息续写（如“继续/可以”）。请给出具体计划修改点，或切换到 agent 模式后回复“确认”直接执行。"
        )
        return PlanAgentV2Decision(
            action="stay_plan",
            reply_text=low_signal_reply,
            plan_state=st.to_dict(),
            system_prompt_override="",
        )

    if int(st.plan_loop_count or 0) >= 2:
        emit_plan_agent_v2_trace(
            store=store,
            session_id=session_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            event_type="plan_mode_active",
            payload={"plan_id": st.plan_id, "plan_path": st.plan_path, "loop_guard": "hard_block"},
        )
        anti_loop_reply = (
            "I am in plan mode. I will only output a concise executable plan. "
            "If you want me to execute, switch to agent mode and reply 'confirm'."
            if str(lang or "").startswith("en")
            else "当前为 plan 模式，我只输出可执行计划。若要开始执行，请切换到 agent 模式并回复“确认”。"
        )
        return PlanAgentV2Decision(
            action="stay_plan",
            reply_text=anti_loop_reply,
            plan_state=st.to_dict(),
            system_prompt_override="",
        )

    prefix = build_plan_mode_prefix(state=st, lang=lang)
    anti_loop_suffix = (
        "\n\n[Anti-loop guard]\n"
        "- Do not repeat the previous response.\n"
        "- If user asks similarly, refine with more concrete steps, checks, and fallback.\n"
        "- Keep output as plan only; do not pretend execution is complete."
    )
    emit_plan_agent_v2_trace(
        store=store,
        session_id=session_id,
        trace_id=trace_id,
        parent_span_id=parent_span_id,
        event_type="plan_mode_active",
        payload={"plan_id": st.plan_id, "plan_path": st.plan_path, "loop_count": int(st.plan_loop_count or 0)},
    )
    return PlanAgentV2Decision(
        action="run_agent",
        reply_text="",
        plan_state=st.to_dict(),
        system_prompt_override=f"{prefix}{anti_loop_suffix}\n\n{str(base_system_prompt or '').strip()}".strip(),
    )


__all__ = ["PlanAgentV2Decision", "evaluate_for_expert_mode"]

