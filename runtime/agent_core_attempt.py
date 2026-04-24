from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from oclaw.runtime.chat.turn_types import TurnRunOutcome
from oclaw.runtime.direct_loop import run_direct_loop
from oclaw.runtime.memory_stage import after_turn_memory
from oclaw.runtime.types import AttemptState, OclawMemoryContext, StandardMessage
from oclaw.runtime.orchestration.trace import new_span_id

def _workspace_owner_session_id_from_msg(msg: StandardMessage) -> str | None:
    md = msg.metadata if isinstance(msg.metadata, dict) else {}
    w = str(md.get("workspace_owner_session_id") or "").strip()
    return w or None


ALL_ATTEMPT_ERROR_CODES = (
    "relay_envelope_invalid",
    "relay_envelope_unsupported_version",
    "control_interrupted",
    "auth_invalid_credentials",
    "input_invalid_request",
    "context_overflow",
    "tool_loop_guard",
    "tool_execution_failed",
    "provider_timeout",
    "provider_rate_limited",
    "provider_temporary_error",
    "provider_unavailable",
    "runtime_unknown_error",
)


@dataclass(frozen=True)
class AttemptRunnerInput:
    attempt_no: int
    msg: StandardMessage
    lang: str
    system_prompt: str
    model: Any
    tools: Any
    trace_id: str | None
    parent_span_id: str | None
    max_messages: int
    max_tool_rounds: int
    max_tool_workers: int
    memory_context: OclawMemoryContext | None
    persist_user_message: bool = True
    on_token: Optional[Callable[[str], None]] = None
    on_progress: Optional[Callable[[str], None]] = None
    on_tool_ui: Optional[Callable[[str, dict[str, Any]], None]] = None
    should_stop: Optional[Callable[[], bool]] = None
    run_id: str | None = None
    workspace_dir: str | None = None
    skill_binding_role: str | None = None
    wire_policy_role: str | None = None


@dataclass(frozen=True)
class AttemptRunnerOutput:
    state: AttemptState
    outcome: TurnRunOutcome


def _classify_attempt_error(exc: Exception) -> tuple[str, str, bool]:
    raw = f"{type(exc).__name__}:{exc}"
    low = raw.lower()
    if "relay_envelope_unsupported_version" in low:
        return ("relay_envelope_unsupported_version", raw[:500], False)
    if "relay_envelope_invalid" in low:
        return ("relay_envelope_invalid", raw[:500], False)
    if "interrupted" in low or "cancel" in low or "stopped" in low:
        return ("control_interrupted", raw[:500], False)
    if "api_key" in low or "invalid api key" in low or "unauthorized" in low or "401" in low or "forbidden" in low or "403" in low:
        return ("auth_invalid_credentials", raw[:500], False)
    if "invalid_request" in low or "bad_request" in low or "400" in low:
        return ("input_invalid_request", raw[:500], False)
    if "context_length" in low or "token limit" in low or "max context" in low:
        return ("context_overflow", raw[:500], True)
    if "tool_loop_guard" in low:
        return ("tool_loop_guard", raw[:500], False)
    if "tool_timeout_or_failed" in low or "tool_execution_error" in low:
        return ("tool_execution_failed", raw[:500], True)
    if "timeout" in low:
        return ("provider_timeout", raw[:500], True)
    if "rate" in low and "limit" in low:
        return ("provider_rate_limited", raw[:500], True)
    if "temporary" in low or "temporar" in low:
        return ("provider_temporary_error", raw[:500], True)
    if "connection" in low or "network" in low or "503" in low or "502" in low:
        return ("provider_unavailable", raw[:500], True)
    return ("runtime_unknown_error", raw[:500], False)


def run_attempt(*, store: Any, data: AttemptRunnerInput) -> AttemptRunnerOutput:
    try:
        outcome = run_direct_loop(
            store=store,
            session_id=data.msg.session_id,
            lang=data.lang,
            system_prompt=data.system_prompt,
            model=data.model,
            tools=data.tools,
            user_text=data.msg.text,
            attachments=data.msg.attachments,
            trace_id=data.trace_id,
            parent_span_id=data.parent_span_id,
            run_id=data.run_id,
            attempt_no=data.attempt_no,
            max_messages=data.max_messages,
            max_tool_rounds=data.max_tool_rounds,
            max_tool_workers=data.max_tool_workers,
            on_token=data.on_token,
            on_progress=data.on_progress,
            on_tool_ui=data.on_tool_ui,
            should_stop=data.should_stop,
            workspace_owner_session_id=_workspace_owner_session_id_from_msg(data.msg),
            path_policy_tenant_id=str(data.msg.metadata.get("tenant_id") or "") if isinstance(data.msg.metadata, dict) else None,
            path_policy_user_id=str(data.msg.metadata.get("user_id") or "") if isinstance(data.msg.metadata, dict) else None,
            workspace_dir=data.workspace_dir,
            memory_context=data.memory_context,
            persist_user_message=bool(data.persist_user_message),
            skill_binding_role=data.skill_binding_role,
            wire_policy_role=data.wire_policy_role,
        )
        after_turn_memory(
            store=store,
            session_id=data.msg.session_id,
            tenant_id=data.msg.tenant_id,
            user_id=data.msg.user_id,
            user_text=data.msg.text,
            assistant_text=outcome.final_text,
            turn_uuid=outcome.turn_uuid,
        )
        if data.trace_id:
            try:
                store.add_trace_event(
                    session_id=data.msg.session_id,
                    trace_id=str(data.trace_id),
                    span_id=new_span_id(),
                    parent_span_id=data.parent_span_id,
                    event_type="after_turn_memory",
                    payload={
                        "pipeline": "oclaw_agent_core",
                        "oc_stage": "memory_done",
                        "run_id": str(data.run_id or ""),
                        "attempt_no": int(data.attempt_no),
                    },
                )
            except Exception:
                pass
        st = AttemptState(
            attempt_no=int(data.attempt_no),
            status="success",
            reason="completed",
            error_code="",
            tool_trace_count=len(outcome.tool_traces),
            compact_triggered=False,
        )
        return AttemptRunnerOutput(state=st, outcome=outcome)
    except Exception as exc:
        err_code, reason, retryable = _classify_attempt_error(exc)
        state = AttemptState(
            attempt_no=int(data.attempt_no),
            status="retry" if retryable else "failed",
            reason=reason,
            error_code=err_code,
            tool_trace_count=0,
            compact_triggered=False,
        )
        return AttemptRunnerOutput(
            state=state,
            outcome=TurnRunOutcome(
                final_text="",
                tool_traces=tuple(),
                handoff_note=f"{err_code}:{reason}",
                turn_uuid="",
            ),
        )


__all__ = [
    "ALL_ATTEMPT_ERROR_CODES",
    "AttemptRunnerInput",
    "AttemptRunnerOutput",
    "run_attempt",
]

