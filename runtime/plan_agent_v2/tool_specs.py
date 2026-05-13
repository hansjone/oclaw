from __future__ import annotations

from typing import Any

from .manager import PlanModeManagerV2
from .models import PLAN_MODE_PLAN
from .trace import emit_plan_agent_v2_trace
from runtime.tools.base import ToolSpec

DEFAULT_SESSION_KEY = "AIA_PLAN_AGENT_V2_DEFAULT_SESSION_ID"


def _emit_tool_trace(
    *,
    store: Any,
    session_id: str,
    args: dict[str, Any],
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> None:
    trace_id = str(args.get("trace_id") or "").strip()
    if not trace_id:
        return
    parent_raw = str(args.get("parent_span_id") or "").strip()
    emit_plan_agent_v2_trace(
        store=store,
        session_id=session_id,
        trace_id=trace_id,
        parent_span_id=parent_raw or None,
        event_type=event_type,
        payload=payload,
    )


def _resolve_session_id(*, store: Any, args: dict[str, Any]) -> str:
    sid = str(args.get("session_id") or "").strip()
    if sid:
        return sid
    try:
        return str(store.get_setting(DEFAULT_SESSION_KEY) or "").strip()
    except Exception:
        return ""


def enter_plan_mode_v2_tool(*, store: Any) -> ToolSpec:
    mgr = PlanModeManagerV2(store=store)

    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        session_id = _resolve_session_id(store=store, args=args)
        if not session_id:
            return {"ok": False, "error_code": "session_id_required", "error": "session_id_required"}
        specialist = str(args.get("owner_specialist") or "generalist").strip().lower() or "generalist"
        force_new = bool(args.get("force_new_plan"))
        st = mgr.enter(session_id=session_id, owner_specialist=specialist, force_new_plan=force_new)
        _emit_tool_trace(
            store=store,
            session_id=session_id,
            args=args,
            event_type="plan_mode_tool_enter",
            payload={
                "tool": "enter_plan_mode_v2",
                "owner_specialist": specialist,
                "force_new_plan": force_new,
                "plan_id": st.plan_id,
            },
        )
        return {"ok": True, "state": st.to_dict()}

    return ToolSpec(
        name="enter_plan_mode_v2",
        description=(
            "Enter plan mode for this session (shadow v2), cc-mini-style: binds a dedicated plan file path. "
            "Use when the user wants structured planning. Set force_new_plan=true only when starting a brand-new "
            "plan document; otherwise reuse the existing plan when possible. Optional trace_id / parent_span_id "
            "attach observability to the current trace."
        ),
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "owner_specialist": {"type": "string"},
                "force_new_plan": {"type": "boolean", "default": False},
                "trace_id": {"type": "string"},
                "parent_span_id": {"type": "string"},
            },
            "required": [],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"plan_mode", "shadow_v2", "read"}),
        read_only=True,
        risk_level="low",
    )


def exit_plan_mode_v2_tool(*, store: Any) -> ToolSpec:
    mgr = PlanModeManagerV2(store=store)

    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        session_id = _resolve_session_id(store=store, args=args)
        if not session_id:
            return {"ok": False, "error_code": "session_id_required", "error": "session_id_required"}
        confirm = bool(args.get("confirm"))
        st = mgr.confirm(session_id=session_id) if confirm else mgr.exit_without_confirm(session_id=session_id)
        _emit_tool_trace(
            store=store,
            session_id=session_id,
            args=args,
            event_type="plan_mode_tool_exit",
            payload={
                "tool": "exit_plan_mode_v2",
                "confirmed": bool(confirm),
                "plan_id": st.plan_id,
                "plan_confirmed": bool(st.plan_confirmed),
            },
        )
        return {"ok": True, "confirmed": bool(confirm), "state": st.to_dict()}

    return ToolSpec(
        name="exit_plan_mode_v2",
        description=(
            "Exit plan mode for this session (shadow v2). confirm=true marks the plan as approved for execution "
            "(same intent as the user confirming in agent mode). confirm=false leaves plan mode without approving "
            "execution—use when ending planning without a run approval yet. Optional trace_id / parent_span_id for "
            "trace correlation."
        ),
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "confirm": {"type": "boolean", "default": False},
                "trace_id": {"type": "string"},
                "parent_span_id": {"type": "string"},
            },
            "required": [],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"plan_mode", "shadow_v2", "write"}),
        read_only=False,
        risk_level="high",
    )


def materialize_plan_mode_v2_tools(*, store: Any) -> list[ToolSpec]:
    return [enter_plan_mode_v2_tool(store=store), exit_plan_mode_v2_tool(store=store)]


def is_plan_mode_v2_active(*, store: Any, session_id: str) -> bool:
    mgr = PlanModeManagerV2(store=store)
    return mgr.load_state(session_id=session_id).mode == PLAN_MODE_PLAN


__all__ = [
    "enter_plan_mode_v2_tool",
    "exit_plan_mode_v2_tool",
    "materialize_plan_mode_v2_tools",
    "is_plan_mode_v2_active",
    "DEFAULT_SESSION_KEY",
]

