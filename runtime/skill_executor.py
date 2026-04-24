from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from oclaw.runtime.chat.tool_runtime import (
    ToolExecutionConfig,
    ToolExecutionContext,
    ToolExecutor,
)
from oclaw.runtime.orchestration.trace import new_span_id
from oclaw.platform.llm.chat_models import LLMToolCall
from oclaw.runtime.tools.base import ToolRegistry


@dataclass(frozen=True)
class SkillExecutionContext:
    store: Any
    tools: ToolRegistry
    session_id: str
    lang: str = "zh"
    user_text: str = ""
    specialist: str = "oclaw"
    trace_id: str | None = None
    parent_span_id: str | None = None
    workspace_owner_session_id: str | None = None
    path_policy_tenant_id: str | None = None
    path_policy_user_id: str | None = None
    run_id: str | None = None
    attempt_no: int | None = None
    turn_uuid: str | None = None


class SkillExecutor:
    """Skill-oriented execution bridge.

    Phase-1 delegates execution to ToolExecutor while emitting skill_ui events.
    """

    def __init__(self, *, config: ToolExecutionConfig | None = None):
        self._tool_exec = ToolExecutor(config=config or ToolExecutionConfig())

    @staticmethod
    def _trace(ctx: SkillExecutionContext, *, event_type: str, payload: dict[str, Any]) -> None:
        if not str(ctx.trace_id or "").strip():
            return
        try:
            ctx.store.add_trace_event(
                session_id=ctx.session_id,
                trace_id=str(ctx.trace_id),
                span_id=new_span_id(),
                parent_span_id=ctx.parent_span_id,
                event_type=str(event_type),
                payload={
                    "pipeline": "oclaw_skill_executor",
                    "trace_id": str(ctx.trace_id or ""),
                    "run_id": str(ctx.run_id or ""),
                    "attempt_no": int(ctx.attempt_no) if ctx.attempt_no is not None else None,
                    **dict(payload or {}),
                },
            )
        except Exception:
            pass

    def execute_skill_uses(
        self,
        *,
        ctx: SkillExecutionContext,
        assistant_msg_id: int,
        skill_uses: list[LLMToolCall],
        on_tool_ui: Optional[Callable[[str, dict[str, Any]], None]] = None,
        on_skill_ui: Optional[Callable[[str, dict[str, Any]], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
        signature_budget: int = 2,
    ) -> tuple[list[dict[str, Any]], dict[str, tuple[dict[str, Any], int]]]:
        for su in skill_uses or []:
            self._trace(
                ctx,
                event_type="skill_selected",
                payload={
                    "skill_name": str(getattr(su, "name", "") or ""),
                    "skill_call_id": str(getattr(su, "id", "") or ""),
                },
            )

        def _emit(event: str, payload: dict[str, Any]) -> None:
            if on_tool_ui:
                on_tool_ui(event, payload)
            if on_skill_ui and on_skill_ui is not on_tool_ui:
                ev = str(event or "")
                if ev.startswith("tool_"):
                    ev = "skill_" + ev[len("tool_") :]
                on_skill_ui(ev, payload)

        tool_messages, results_by_id = self._tool_exec.execute_tool_uses(
            ctx=ToolExecutionContext(
                store=ctx.store,
                tools=ctx.tools,
                session_id=ctx.session_id,
                lang=ctx.lang,
                user_text=ctx.user_text,
                specialist=ctx.specialist,
                task_kind="turn",
                policy_engine=None,
                trace_id=ctx.trace_id,
                parent_span_id=ctx.parent_span_id,
                workspace_owner_session_id=ctx.workspace_owner_session_id,
                path_policy_tenant_id=ctx.path_policy_tenant_id,
                path_policy_user_id=ctx.path_policy_user_id,
                turn_uuid=ctx.turn_uuid,
            ),
            assistant_msg_id=assistant_msg_id,
            tool_uses=skill_uses,
            on_tool_ui=_emit,
            should_stop=should_stop,
            signature_budget=signature_budget,
        )
        for su in skill_uses or []:
            result, dur = results_by_id.get(str(getattr(su, "id", "") or ""), ({}, 0))
            self._trace(
                ctx,
                event_type="skill_executed",
                payload={
                    "skill_name": str(getattr(su, "name", "") or ""),
                    "skill_call_id": str(getattr(su, "id", "") or ""),
                    "ok": bool((result or {}).get("ok")) if isinstance(result, dict) else None,
                    "duration_ms": int(dur or 0),
                    "error_code": str((result or {}).get("error_code") or "") if isinstance(result, dict) else "",
                },
            )
        return tool_messages, results_by_id


__all__ = ["SkillExecutionContext", "SkillExecutor"]

