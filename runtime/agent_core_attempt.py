from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Optional

from runtime.chat.turn_types import TurnRunOutcome
from runtime.direct_loop import run_direct_loop
from runtime.memory_stage import after_turn_memory
from runtime.types import AttemptState, OclawMemoryContext, StandardMessage
from runtime.orchestration.trace import new_span_id

def _workspace_owner_session_id_from_msg(msg: StandardMessage) -> str | None:
    md = msg.metadata if isinstance(msg.metadata, dict) else {}
    w = str(md.get("workspace_owner_session_id") or "").strip()
    return w or None


def _should_after_turn_memory(msg: StandardMessage) -> bool:
    # Wiki memory must be agent-initiated only.
    # Disable passive/automatic capture path in agent core.
    _ = msg
    return False


ALL_ATTEMPT_ERROR_CODES = (
    "relay_envelope_invalid",
    "relay_envelope_unsupported_version",
    "control_interrupted",
    "auth_invalid_credentials",
    "input_invalid_request",
    "tool_replay_protocol_mismatch",
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
    prompt_build_context: dict[str, Any] | None = None
    turn_uuid: str | None = None
    persisted_user_text: str | None = None


@dataclass(frozen=True)
class AttemptRunnerOutput:
    state: AttemptState
    outcome: TurnRunOutcome


def _exception_reason_for_chat(exc: BaseException, *, max_chars: int = 12000) -> str:
    """Human-visible attempt failure text (WS/chat reads ``AttemptState.reason``).

    OpenAI Python SDK's ``APIError`` often carries a decoded JSON ``body``; include it so oclaw /chat
    can show the full upstream validation payload instead of only ``str(exc)``.
    """
    head = f"{type(exc).__name__}:{exc}"
    blob = ""
    cur: BaseException | None = exc
    seen_ids: set[int] = set()
    depth = 0
    while cur is not None and depth < 16:
        if id(cur) in seen_ids:
            break
        seen_ids.add(id(cur))
        depth += 1
        body = getattr(cur, "body", None)
        if body is not None:
            try:
                blob = json.dumps(body, ensure_ascii=False, indent=2) if isinstance(body, (dict, list)) else str(body)
            except Exception:
                blob = str(body)
            break
        cur = cur.__cause__
    out = head if not blob else f"{head}\n\nupstream_json_body:\n{blob}"
    if len(out) > max_chars:
        out = out[: max_chars - 24] + "\n...[truncated]"
    return out


def _classify_attempt_error(exc: Exception) -> tuple[str, str, bool]:
    raw = f"{type(exc).__name__}:{exc}"
    low = raw.lower()
    reason = _exception_reason_for_chat(exc)
    if "relay_envelope_unsupported_version" in low:
        return ("relay_envelope_unsupported_version", reason, False)
    if "relay_envelope_invalid" in low:
        return ("relay_envelope_invalid", reason, False)
    if "interrupted" in low or "cancel" in low or "stopped" in low:
        return ("control_interrupted", reason, False)
    if "api_key" in low or "invalid api key" in low or "unauthorized" in low or "401" in low or "forbidden" in low or "403" in low:
        return ("auth_invalid_credentials", reason, False)
    if "invalid tool_result sequence" in low or "unexpected tool_use_id" in low:
        return ("tool_replay_protocol_mismatch", reason, True)
    if "invalid_request" in low or "bad_request" in low or "400" in low:
        return ("input_invalid_request", reason, False)
    if "context_length" in low or "token limit" in low or "max context" in low:
        return ("context_overflow", reason, True)
    if "tool_loop_guard" in low:
        return ("tool_loop_guard", reason, False)
    if "tool_timeout_or_failed" in low or "tool_execution_error" in low:
        return ("tool_execution_failed", reason, True)
    if "timeout" in low:
        return ("provider_timeout", reason, True)
    if "rate" in low and "limit" in low:
        return ("provider_rate_limited", reason, True)
    if "temporary" in low or "temporar" in low:
        return ("provider_temporary_error", reason, True)
    if "connection" in low or "network" in low or "503" in low or "502" in low:
        return ("provider_unavailable", reason, True)
    return ("runtime_unknown_error", reason, False)


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
            persisted_user_text=data.persisted_user_text,
            skill_binding_role=data.skill_binding_role,
            wire_policy_role=data.wire_policy_role,
            prompt_build_context=data.prompt_build_context,
            turn_uuid=data.turn_uuid,
        )
        if _should_after_turn_memory(data.msg):
            after_turn_memory(
                store=store,
                session_id=data.msg.session_id,
                tenant_id=data.msg.tenant_id,
                user_id=data.msg.user_id,
                user_text=str(data.persisted_user_text if data.persisted_user_text is not None else data.msg.text or ""),
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

