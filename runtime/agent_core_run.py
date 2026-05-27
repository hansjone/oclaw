from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Callable, Optional

from runtime.chat.turn_types import TurnRunOutcome
from runtime.agent_core_attempt import ALL_ATTEMPT_ERROR_CODES
from runtime.agent_core_attempt import AttemptRunnerInput, run_attempt
from runtime.memory_stage import compact_memory_context
from runtime.types import AttemptState, OclawMemoryContext, RunState, StandardMessage
from runtime.orchestration.trace import new_span_id

_AGENT_CORE_OC_STAGE: dict[str, str] = {
    "run_started": "run_start",
    "attempt_started": "attempt",
    "attempt_finished": "attempt_done",
    "run_finished": "run_done",
    "run_compact": "compact",
    "run_retry": "retry",
}


@dataclass(frozen=True)
class AgentCoreRunInput:
    msg: StandardMessage
    lang: str
    system_prompt: str
    model: Any
    tools: Any
    trace_id: str | None
    parent_span_id: str | None
    run_id: str | None = None
    max_messages: int = 80
    max_tool_rounds: int = 30
    max_tool_workers: int = 8
    max_attempts: int = 2
    memory_context: OclawMemoryContext | None = None
    on_token: Optional[Callable[[str], None]] = None
    on_progress: Optional[Callable[[str], None]] = None
    on_tool_ui: Optional[Callable[[str, dict[str, Any]], None]] = None
    should_stop: Optional[Callable[[], bool]] = None
    task_id: str | None = None
    worker_id: str | None = None
    # Backward-compatible aliases kept for older callsites/tests.
    oclaw_task_id: str | None = None
    oclaw_worker_id: str | None = None
    skill_binding_role: str | None = None
    wire_policy_role: str | None = None
    persisted_user_text: str | None = None


@dataclass(frozen=True)
class AgentCoreRunOutput:
    run_id: str
    run_state: RunState
    outcome: TurnRunOutcome


DEFAULT_RETRYABLE_ERROR_CODES = (
    "provider_timeout",
    "provider_rate_limited",
    "provider_temporary_error",
    "provider_unavailable",
    "tool_replay_protocol_mismatch",
    "context_overflow",
    "tool_execution_failed",
)


def resolve_retryable_error_codes(*, store: Any) -> set[str]:
    raw = ""
    try:
        raw = str(store.get_setting("AIA_OCLAW_RETRYABLE_ERROR_CODES") or "").strip()
    except Exception:
        raw = ""
    if not raw:
        return set(DEFAULT_RETRYABLE_ERROR_CODES)
    allowed = set(ALL_ATTEMPT_ERROR_CODES)
    out = {x.strip().lower() for x in raw.split(",") if x and x.strip()}
    out = {x for x in out if x in allowed}
    return out or set(DEFAULT_RETRYABLE_ERROR_CODES)


def _trace(
    store: Any,
    *,
    data: AgentCoreRunInput,
    run_id: str,
    attempt_no: int | None,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    if not data.trace_id:
        return
    merged: dict[str, Any] = dict(payload or {})
    merged.setdefault("pipeline", "oclaw_agent_core")
    merged.setdefault("trace_id", str(data.trace_id))
    merged.setdefault("lang", str(data.lang or ""))
    merged.setdefault("run_id", run_id)
    if attempt_no is not None:
        merged.setdefault("attempt_no", int(attempt_no))
    merged["oc_stage"] = _AGENT_CORE_OC_STAGE.get(event_type, event_type)
    tid = str(data.task_id or data.oclaw_task_id or "").strip()
    if tid:
        merged.setdefault("task_id", tid)
        merged.setdefault("oclaw_task_id", tid)
    wid = str(data.worker_id or data.oclaw_worker_id or "").strip()
    if wid:
        merged.setdefault("worker_id", wid)
        merged.setdefault("oclaw_worker_id", wid)
    try:
        store.add_trace_event(
            session_id=data.msg.session_id,
            trace_id=str(data.trace_id),
            span_id=new_span_id(),
            parent_span_id=data.parent_span_id,
            event_type=event_type,
            payload=merged,
        )
    except Exception:
        pass


def _persist_run(store: Any, *, run_id: str, msg: StandardMessage, status: str, payload: dict[str, Any]) -> None:
    try:
        store.oclaw_run_upsert(
            run_id=run_id,
            tenant_id=msg.tenant_id,
            session_id=msg.session_id,
            status=status,
            payload=payload,
        )
    except Exception:
        pass


def _relay_envelope_stats(msg: StandardMessage) -> dict[str, Any]:
    md = msg.metadata if isinstance(msg.metadata, dict) else {}
    env = md.get("relay_share_envelope")
    present = isinstance(env, dict)
    ptr_count = 0
    if present:
        ad = env.get("attachments")
        if isinstance(ad, dict):
            ps = ad.get("pointers")
            if isinstance(ps, list):
                ptr_count = len([x for x in ps if isinstance(x, dict)])
    return {
        "relay_envelope_present": bool(present),
        "relay_envelope_pointer_count": int(ptr_count),
    }


def run_agent_core(*, store: Any, data: AgentCoreRunInput) -> AgentCoreRunOutput:
    run_id = str(data.run_id or "").strip() or str(uuid.uuid4())
    user_turn_uuid = str(uuid.uuid4())
    attempts: list[AttemptState] = []
    compact_count = 0
    outcome = TurnRunOutcome(final_text="", tool_traces=tuple(), handoff_note="", turn_uuid="")
    retryable_error_codes = resolve_retryable_error_codes(store=store)
    _trace(
        store,
        data=data,
        run_id=run_id,
        attempt_no=None,
        event_type="run_started",
        payload={
            "max_attempts": int(max(1, data.max_attempts)),
            "retryable_error_codes": sorted(retryable_error_codes),
            **_relay_envelope_stats(data.msg),
        },
    )
    _persist_run(
        store,
        run_id=run_id,
        msg=data.msg,
        status="running",
        payload={"max_attempts": int(max(1, data.max_attempts)), "retryable_error_codes": sorted(retryable_error_codes)},
    )

    mem_ctx = data.memory_context
    for idx in range(1, max(1, int(data.max_attempts or 1)) + 1):
        _trace(
            store,
            data=data,
            run_id=run_id,
            attempt_no=idx,
            event_type="attempt_started",
            payload={**_relay_envelope_stats(data.msg)},
        )
        out = run_attempt(
            store=store,
            data=AttemptRunnerInput(
                attempt_no=idx,
                msg=data.msg,
                lang=data.lang,
                system_prompt=data.system_prompt,
                model=data.model,
                tools=data.tools,
                trace_id=data.trace_id,
                parent_span_id=data.parent_span_id,
                max_messages=data.max_messages,
                max_tool_rounds=data.max_tool_rounds,
                max_tool_workers=data.max_tool_workers,
                memory_context=mem_ctx,
                persist_user_message=(idx == 1),
                on_token=data.on_token,
                on_progress=data.on_progress,
                on_tool_ui=data.on_tool_ui,
                should_stop=data.should_stop,
                run_id=run_id,
                workspace_dir=(
                    str(data.msg.metadata.get("workspaceDir") or data.msg.metadata.get("workspace_dir") or "").strip()
                    if isinstance(data.msg.metadata, dict)
                    else None
                ),
                skill_binding_role=data.skill_binding_role,
                wire_policy_role=data.wire_policy_role,
                prompt_build_context=(dict(data.msg.metadata or {}) if isinstance(data.msg.metadata, dict) else None),
                turn_uuid=user_turn_uuid,
                persisted_user_text=data.persisted_user_text,
            ),
        )
        attempts.append(out.state)
        outcome = out.outcome
        try:
            store.oclaw_attempt_append(
                run_id=run_id,
                tenant_id=data.msg.tenant_id,
                session_id=data.msg.session_id,
                attempt_no=idx,
                status=out.state.status,
                reason=out.state.reason,
                payload={"tool_trace_count": int(out.state.tool_trace_count), "error_code": str(out.state.error_code or "")},
            )
        except Exception:
            pass
        _trace(
            store,
            data=data,
            run_id=run_id,
            attempt_no=idx,
            event_type="attempt_finished",
            payload={
                "status": out.state.status,
                "reason": out.state.reason,
                "error_code": out.state.error_code,
                "tool_trace_count": int(out.state.tool_trace_count),
            },
        )
        if out.state.status == "success":
            rs = RunState(
                run_id=run_id,
                session_id=data.msg.session_id,
                status="success",
                attempts=tuple(attempts),
                compact_count=compact_count,
                stop_reason="success",
            )
            _persist_run(store, run_id=run_id, msg=data.msg, status="success", payload={"stop_reason": "success", "attempts": len(attempts)})
            _trace(
                store,
                data=data,
                run_id=run_id,
                attempt_no=None,
                event_type="run_finished",
                payload={"status": "success", "attempts": len(attempts)},
            )
            return AgentCoreRunOutput(run_id=run_id, run_state=rs, outcome=outcome)

        retryable = out.state.status == "retry" and str(out.state.error_code or "") in retryable_error_codes
        if not retryable:
            rs_fail = RunState(
                run_id=run_id,
                session_id=data.msg.session_id,
                status="failed",
                attempts=tuple(attempts),
                compact_count=compact_count,
                last_error_code=str(out.state.error_code or "attempt_failed"),
                stop_reason="non_retryable_error" if out.state.status != "retry" else "retry_matrix_blocked",
            )
            _persist_run(
                store,
                run_id=run_id,
                msg=data.msg,
                status="failed",
                payload={
                    "stop_reason": "non_retryable_error" if out.state.status != "retry" else "retry_matrix_blocked",
                    "attempts": len(attempts),
                    "last_error_code": str(out.state.error_code or "attempt_failed"),
                },
            )
            _trace(
                store,
                data=data,
                run_id=run_id,
                attempt_no=None,
                event_type="run_finished",
                payload={
                    "status": "failed",
                    "attempts": len(attempts),
                    "stop_reason": "non_retryable_error" if out.state.status != "retry" else "retry_matrix_blocked",
                    "last_error_code": str(out.state.error_code or "attempt_failed"),
                },
            )
            return AgentCoreRunOutput(run_id=run_id, run_state=rs_fail, outcome=outcome)

        # retry path with memory compaction
        compact_count += 1
        mem_ctx = compact_memory_context(
            store=store,
            session_id=data.msg.session_id,
            tenant_id=data.msg.tenant_id,
            user_id=data.msg.user_id,
        )
        _trace(
            store,
            data=data,
            run_id=run_id,
            attempt_no=idx,
            event_type="run_compact",
            payload={"compact_count": compact_count},
        )
        _trace(
            store,
            data=data,
            run_id=run_id,
            attempt_no=None,
            event_type="run_retry",
            payload={"next_attempt_no": idx + 1},
        )

    rs = RunState(
        run_id=run_id,
        session_id=data.msg.session_id,
        status="failed",
        attempts=tuple(attempts),
        compact_count=compact_count,
        last_error_code="attempt_failed",
        stop_reason="max_attempts_reached",
    )
    _persist_run(
        store,
        run_id=run_id,
        msg=data.msg,
        status="failed",
        payload={"stop_reason": "max_attempts_reached", "attempts": len(attempts), "last_error_code": "attempt_failed"},
    )
    _trace(
        store,
        data=data,
        run_id=run_id,
        attempt_no=None,
        event_type="run_finished",
        payload={"status": "failed", "attempts": len(attempts), "stop_reason": "max_attempts_reached"},
    )
    return AgentCoreRunOutput(run_id=run_id, run_state=rs, outcome=outcome)


__all__ = [
    "AgentCoreRunInput",
    "AgentCoreRunOutput",
    "DEFAULT_RETRYABLE_ERROR_CODES",
    "resolve_retryable_error_codes",
    "run_agent_core",
]

