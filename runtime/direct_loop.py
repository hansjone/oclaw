from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable, Optional

from oclaw.runtime.chat.agent_messages import build_llm_messages
from oclaw.runtime.chat.tool_runtime import ToolExecutionConfig
from oclaw.runtime.chat.turn_types import TurnRunOutcome
from oclaw.runtime.skill_executor import SkillExecutionContext, SkillExecutor
from oclaw.runtime.skills import build_skill_manifest
from oclaw.platform.llm.chat_models import ChatModel
from oclaw.runtime.system_prompt import build_oclaw_executor_system_prompt
from oclaw.runtime.types import OclawMemoryContext
from oclaw.runtime.orchestration.trace import new_span_id
from oclaw.runtime.tools.base import ToolRegistry

_OCLAW_TOOL_RESULT_HARD_CAP_CHARS = 24_000

_DIRECT_LOOP_OC_STAGE: dict[str, str] = {
    "tool_wire_filter": "wire_filter",
    "tool_result_context_guard": "tool_context_guard",
}
_THINK_BLOCK_RE = re.compile(r"<(think|redacted_thinking)>\s*(.*?)\s*</\1>\s*", flags=re.IGNORECASE | re.DOTALL)


def _emit_direct_loop_trace(
    *,
    store: Any,
    session_id: str,
    trace_id: str | None,
    parent_span_id: str | None,
    event_type: str,
    payload: dict[str, Any],
    run_id: str | None,
    attempt_no: int | None,
    lang: str,
) -> None:
    if not trace_id:
        return
    merged: dict[str, Any] = dict(payload or {})
    merged.setdefault("pipeline", "oclaw_direct_loop")
    merged.setdefault("trace_id", str(trace_id))
    merged.setdefault("lang", str(lang or ""))
    merged["oc_stage"] = _DIRECT_LOOP_OC_STAGE.get(event_type, event_type)
    rid = str(run_id or "").strip()
    if rid:
        merged.setdefault("run_id", rid)
    if attempt_no is not None:
        merged.setdefault("attempt_no", int(attempt_no))
    try:
        store.add_trace_event(
            session_id=session_id,
            trace_id=str(trace_id),
            span_id=new_span_id(),
            parent_span_id=parent_span_id,
            event_type=event_type,
            payload=merged,
        )
    except Exception:
        pass


@dataclass(frozen=True)
class _LoopStepResult:
    assistant_text: str
    llm_tool_calls: list[Any]
    assistant_msg_id: int


def _json_dumps_safe(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        return json.dumps({"ok": False, "error": "not_json_serializable"}, ensure_ascii=False)


def _split_reasoning_and_body(text: str, *, explicit_reasoning: str | None = None) -> tuple[list[str], str]:
    explicit = str(explicit_reasoning or "").strip()
    raw = str(text or "")
    if not raw:
        return ([explicit] if explicit else []), ""
    if explicit:
        body = _THINK_BLOCK_RE.sub("", raw).strip()
        return [explicit], body
    chunks: list[str] = []
    for m in _THINK_BLOCK_RE.finditer(raw):
        t = str(m.group(2) or "").strip()
        if t:
            chunks.append(t)
    body = _THINK_BLOCK_RE.sub("", raw).strip()
    return chunks, body


def _guard_tool_results_for_llm_context(
    *,
    store: Any,
    session_id: str,
    store_messages: list[Any],
    trace_id: str | None,
    parent_span_id: str | None,
    hard_cap_chars: int,
    run_id: str | None = None,
    attempt_no: int | None = None,
    lang: str = "",
) -> list[Any]:
    """Hard-guard overlarge `role=tool` message contents before sending to model.

    This does NOT rewrite DB history (tool_log / chat_message). It only guards the
    in-flight LLM context to prevent provider context overflow spirals.
    """
    cap = max(4096, min(int(hard_cap_chars or _OCLAW_TOOL_RESULT_HARD_CAP_CHARS), 500_000))
    out: list[Any] = []
    for m in store_messages or []:
        role = str(getattr(m, "role", "") or "")
        if role != "tool":
            out.append(m)
            continue
        raw = str(getattr(m, "content", "") or "")
        if len(raw) <= cap:
            out.append(m)
            continue
        # Best-effort parse tool JSON for a minimal summary.
        ok = None
        error_code = ""
        error = ""
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                ok = obj.get("ok")
                error_code = str(obj.get("error_code") or "").strip()
                error = str(obj.get("error") or "").strip()
        except Exception:
            obj = None
        preview = raw[: max(1, min(4000, cap - 400))] + "\n...<tool_result_guard_truncated>"
        guarded_obj = {
            "ok": bool(ok) if ok is not None else None,
            "error_code": error_code,
            "error": error,
            "_tool_result_guarded": True,
            "original_chars": len(raw),
            "guard_cap_chars": cap,
            "preview": preview,
            "hint": (
                "Tool output was too large for safe context replay; it was truncated for the model context. "
                "Use narrower queries (e.g., smaller glob/max_results) or adjust AIA_TOOL_LLM_MESSAGE_MAX_CHARS. / "
                "工具输出过大，已在发给模型的上下文中强制截断；请缩小范围或配置 AIA_TOOL_LLM_MESSAGE_MAX_CHARS。"
            ),
        }
        guarded = _json_dumps_safe(guarded_obj)
        out.append(
            SimpleNamespace(
                id=getattr(m, "id", 0),
                session_id=getattr(m, "session_id", session_id),
                role="tool",
                content=guarded,
                tool_calls=getattr(m, "tool_calls", None),
                timestamp=getattr(m, "timestamp", ""),
                attachments=getattr(m, "attachments", None),
            )
        )
        if trace_id:
            _emit_direct_loop_trace(
                store=store,
                session_id=session_id,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                event_type="tool_result_context_guard",
                payload={
                    "message_id": int(getattr(m, "id", 0) or 0),
                    "original_chars": int(len(raw)),
                    "guarded_chars": int(len(guarded)),
                    "guard_cap_chars": int(cap),
                },
                run_id=run_id,
                attempt_no=attempt_no,
                lang=lang,
            )
    return out


def _check_stop(should_stop: Optional[Callable[[], bool]]) -> None:
    if should_stop and should_stop():
        raise RuntimeError("generation interrupted by user")


def _build_model_context(
    *,
    store: Any,
    session_id: str,
    max_messages: int,
    system_prompt: str,
    model: ChatModel,
    lang: str,
    memory_context: OclawMemoryContext | None,
    trace_id: str | None,
    parent_span_id: str | None,
    tools: ToolRegistry | None = None,
    base_url: str = "",
    run_id: str | None = None,
    attempt_no: int | None = None,
    workspace_dir: str | None = None,
    skill_binding_role: str | None = None,
) -> list[dict[str, Any]]:
    rows = store.get_messages(session_id=session_id, limit=int(max_messages))
    rows = _guard_tool_results_for_llm_context(
        store=store,
        session_id=session_id,
        store_messages=rows,
        trace_id=trace_id,
        parent_span_id=parent_span_id,
        hard_cap_chars=_OCLAW_TOOL_RESULT_HARD_CAP_CHARS,
        run_id=run_id,
        attempt_no=attempt_no,
        lang=lang,
    )
    final_system = build_oclaw_executor_system_prompt(
        store=store,
        tools=tools,
        base_url=str(base_url or ""),
        base_system=str(system_prompt or ""),
        memory_context=memory_context,
        lang=lang,
        workspace_dir=workspace_dir,
        skill_binding_role=skill_binding_role,
    )
    return build_llm_messages(store_messages=rows, system_prompt=final_system, model=model, lang=lang)


def _prepare_llm_tools(
    *,
    store: Any,
    tools: ToolRegistry,
    base_url: str,
    session_id: str,
    trace_id: str | None,
    parent_span_id: str | None,
    run_id: str | None = None,
    attempt_no: int | None = None,
    lang: str = "",
    wire_policy_role: str | None = None,
) -> list[dict[str, Any]]:
    runtime_enabled = True
    try:
        raw_flag = str(store.get_setting("AIA_SKILL_RUNTIME_ENABLED") or "").strip().lower()
        if raw_flag:
            runtime_enabled = raw_flag in {"1", "true", "yes", "on"}
    except Exception:
        runtime_enabled = True
    if runtime_enabled:
        skill_specs, _ = build_skill_manifest(registry=tools, store=store, base_url=base_url)
        raw_llm_tools = [s.as_openai_tool() for s in skill_specs]
    else:
        raw_llm_tools = tools.as_openai_tools()
    from oclaw.runtime.tools.exposure_plan import build_llm_tools_plan

    plan = build_llm_tools_plan(
        store=store,
        role=str(wire_policy_role or "").strip().lower() or "generalist",
        base_url=base_url or None,
        max_json_bytes=None,
        include_mcp=False,
        preview_internal=False,
        raw_openai_tools_override=raw_llm_tools,
    )
    llm_tools = plan.tools_wired
    if trace_id:
        try:
            import os

            raw_names = {
                str(((t.get("function") or {}) if isinstance(t, dict) else {}).get("name") or "")
                for t in (raw_llm_tools or [])
                if isinstance(t, dict)
            }
            raw_names.discard("")
            hidden = list(plan.removed_names)
            hidden_mcp = list(plan.removed_mcp_names)
            _emit_direct_loop_trace(
                store=store,
                session_id=session_id,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                event_type="tool_wire_filter",
                payload={
                    "runner": "oclaw_direct",
                    "base_url": base_url,
                    "wire_policy_role": str(wire_policy_role or ""),
                    "tools_before": len(raw_names),
                    "tools_after": int(len(_tool_names_for_trace(llm_tools))),
                    "hidden_total": int(len(hidden)),
                    "hidden_mcp_total": int(len(hidden_mcp)),
                    "hidden_mcp_preview": list(hidden_mcp)[:20],
                    "role_mode": str(plan.role_mode or ""),
                    "wire_policy_effective": bool(plan.wire_policy_effective),
                    "max_json_bytes": plan.max_json_bytes,
                    "changed_total": int(len(plan.changed_names)),
                },
                run_id=run_id,
                attempt_no=attempt_no,
                lang=lang,
            )

            # Optional richer snapshot for debugging (may be large).
            trace_plan_enabled = False
            try:
                raw = str(store.get_setting("AIA_TRACE_TOOL_EXPOSURE_PLAN") or "").strip()
                if raw:
                    trace_plan_enabled = raw.lower() in {"1", "true", "yes", "on"}
                else:
                    trace_plan_enabled = str(os.getenv("AIA_TRACE_TOOL_EXPOSURE_PLAN") or "").strip().lower() in {
                        "1",
                        "true",
                        "yes",
                        "on",
                    }
            except Exception:
                trace_plan_enabled = str(os.getenv("AIA_TRACE_TOOL_EXPOSURE_PLAN") or "").strip().lower() in {
                    "1",
                    "true",
                    "yes",
                    "on",
                }
            if trace_plan_enabled:
                _emit_direct_loop_trace(
                    store=store,
                    session_id=session_id,
                    trace_id=trace_id,
                    parent_span_id=parent_span_id,
                    event_type="tool_exposure_plan",
                    payload={
                        "runner": "oclaw_direct",
                        "base_url": base_url,
                        "wire_policy_role": str(wire_policy_role or ""),
                        "role_mode": str(plan.role_mode or ""),
                        "wire_policy_effective": bool(plan.wire_policy_effective),
                        "max_json_bytes": plan.max_json_bytes,
                        "raw_names": sorted(list(raw_names))[:300],
                        "wired_names": sorted(list(set(_tool_names_for_trace(llm_tools))))[:300],
                        "removed_names": list(plan.removed_names)[:300],
                        "removed_mcp_names": list(plan.removed_mcp_names)[:300],
                        "added_names": list(plan.added_names)[:300],
                        "changed_names": list(plan.changed_names)[:300],
                    },
                    run_id=run_id,
                    attempt_no=attempt_no,
                    lang=lang,
                )
        except Exception:
            pass
    return llm_tools


def _tool_names_for_trace(tools: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for t in tools or []:
        if not isinstance(t, dict):
            continue
        fn = t.get("function")
        if not isinstance(fn, dict):
            continue
        nm = str(fn.get("name") or "").strip()
        if nm:
            out.append(nm)
    return out


def _persist_assistant_step(
    *,
    store: Any,
    session_id: str,
    turn_uuid: str,
    assistant_text: str,
    reasoning_text: str,
    llm_tool_calls: list[Any],
) -> _LoopStepResult:
    stored_tool_calls = []
    for tc in llm_tool_calls:
        stored_tool_calls.append(
            {
                "id": str(getattr(tc, "id", "") or ""),
                "name": str(getattr(tc, "name", "") or ""),
                "arguments": dict(getattr(tc, "arguments", {}) or {}),
                "thought_signature": getattr(tc, "thought_signature", None),
            }
        )

    reasoning_chunks, assistant_body = _split_reasoning_and_body(
        assistant_text,
        explicit_reasoning=reasoning_text,
    )
    for idx, chunk in enumerate(reasoning_chunks):
        store.add_message(
            session_id=session_id,
            role="assistant",
            content=chunk,
            turn_uuid=turn_uuid,
            event_type="reasoning",
            event_payload={"chunk_index": int(idx), "chunk_count": len(reasoning_chunks)},
        )
    assistant_row = store.add_message(
        session_id=session_id,
        role="assistant",
        content=assistant_body,
        tool_calls=stored_tool_calls or None,
        turn_uuid=turn_uuid,
        event_type="tool_call" if stored_tool_calls else "assistant_text",
    )
    return _LoopStepResult(
        assistant_text=assistant_body,
        llm_tool_calls=llm_tool_calls,
        assistant_msg_id=int(getattr(assistant_row, "id", 0) or 0),
    )


def _execute_tool_step(
    *,
    skill_exec: SkillExecutor,
    store: Any,
    tools: ToolRegistry,
    session_id: str,
    lang: str,
    user_text: str,
    trace_id: str | None,
    parent_span_id: str | None,
    workspace_owner_session_id: str | None,
    path_policy_tenant_id: str | None,
    path_policy_user_id: str | None,
    assistant_msg_id: int,
    llm_tool_calls: list[Any],
    on_tool_ui: Optional[Callable[[str, dict[str, Any]], None]],
    should_stop: Optional[Callable[[], bool]],
    signature_budget: int,
    run_id: str | None = None,
    attempt_no: int | None = None,
    turn_uuid: str | None = None,
) -> tuple[int, dict[str, tuple[dict[str, Any], int]]]:
    t0 = time.perf_counter()
    _tool_messages, results_by_id = skill_exec.execute_skill_uses(
        ctx=SkillExecutionContext(
            store=store,
            tools=tools,
            session_id=session_id,
            lang=lang,
            user_text=user_text,
            specialist="oclaw",
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            workspace_owner_session_id=workspace_owner_session_id,
            path_policy_tenant_id=path_policy_tenant_id,
            path_policy_user_id=path_policy_user_id,
            run_id=run_id,
            attempt_no=attempt_no,
            turn_uuid=turn_uuid,
        ),
        assistant_msg_id=assistant_msg_id,
        skill_uses=llm_tool_calls,
        on_tool_ui=None,
        on_skill_ui=on_tool_ui,
        should_stop=should_stop,
        signature_budget=signature_budget,
    )
    return int((time.perf_counter() - t0) * 1000), results_by_id


def run_oclaw_direct_loop(
    *,
    store: Any,
    session_id: str,
    lang: str,
    system_prompt: str,
    model: ChatModel,
    tools: ToolRegistry,
    user_text: str,
    attachments: list[dict[str, Any]] | None = None,
    trace_id: str | None = None,
    parent_span_id: str | None = None,
    run_id: str | None = None,
    attempt_no: int | None = None,
    max_messages: int = 80,
    max_tool_rounds: int = 8,
    max_tool_workers: int = 8,
    on_token: Optional[Callable[[str], None]] = None,
    on_progress: Optional[Callable[[str], None]] = None,
    on_tool_ui: Optional[Callable[[str, dict[str, Any]], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
    workspace_owner_session_id: str | None = None,
    path_policy_tenant_id: str | None = None,
    path_policy_user_id: str | None = None,
    workspace_dir: str | None = None,
    memory_context: OclawMemoryContext | None = None,
    persist_user_message: bool = True,
    tool_signature_budget: int = 2,
    skill_binding_role: str | None = None,
    wire_policy_role: str | None = None,
) -> TurnRunOutcome:
    """A minimal oclaw-style loop: model -> tool_uses -> execute -> tool_results -> continue."""
    _check_stop(should_stop)
    turn_uuid = str(uuid.uuid4())
    if persist_user_message:
        store.add_message(
            session_id=session_id,
            role="user",
            content=str(user_text or ""),
            attachments=attachments,
            turn_uuid=turn_uuid,
            event_type="user_text",
        )

    skill_exec = SkillExecutor(config=ToolExecutionConfig(max_workers=max(1, min(int(max_tool_workers or 8), 32))))
    tool_traces: list[dict[str, Any]] = []
    final_text = ""

    base_url = str(getattr(model, "base_url", "") or "")

    for round_idx in range(max(1, int(max_tool_rounds or 1))):
        _check_stop(should_stop)
        if on_progress:
            on_progress(f"oclaw: think ({round_idx + 1})…")

        msgs = _build_model_context(
            store=store,
            session_id=session_id,
            max_messages=max_messages,
            system_prompt=system_prompt,
            model=model,
            lang=lang,
            memory_context=memory_context,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            tools=tools,
            base_url=base_url,
            run_id=run_id,
            attempt_no=attempt_no,
            workspace_dir=workspace_dir,
            skill_binding_role=skill_binding_role,
        )
        llm_tools = _prepare_llm_tools(
            store=store,
            tools=tools,
            base_url=base_url,
            session_id=session_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            run_id=run_id,
            attempt_no=attempt_no,
            lang=lang,
        wire_policy_role=wire_policy_role,
        )
        resp = model.chat(msgs, llm_tools, on_token=on_token)
        assistant_text = str(getattr(resp, "content", "") or "")
        reasoning_text = str(getattr(resp, "reasoning_content", "") or "")
        llm_tool_calls = list(getattr(resp, "tool_calls", []) or [])

        step = _persist_assistant_step(
            store=store,
            session_id=session_id,
            turn_uuid=turn_uuid,
            assistant_text=assistant_text,
            reasoning_text=reasoning_text,
            llm_tool_calls=llm_tool_calls,
        )
        final_text = step.assistant_text
        if not step.llm_tool_calls:
            break

        elapsed_ms, results_by_id = _execute_tool_step(
            skill_exec=skill_exec,
            store=store,
            tools=tools,
            session_id=session_id,
            lang=lang,
            user_text=str(user_text or ""),
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            workspace_owner_session_id=workspace_owner_session_id,
            path_policy_tenant_id=path_policy_tenant_id,
            path_policy_user_id=path_policy_user_id,
            assistant_msg_id=step.assistant_msg_id,
            llm_tool_calls=step.llm_tool_calls,
            on_tool_ui=on_tool_ui,
            should_stop=should_stop,
            signature_budget=tool_signature_budget,
            run_id=run_id,
            attempt_no=attempt_no,
            turn_uuid=turn_uuid,
        )

        for tc in step.llm_tool_calls:
            result, dur = results_by_id.get(str(getattr(tc, "id", "") or ""), ({}, 0))
            tool_traces.append(
                {
                    "name": str(getattr(tc, "name", "") or ""),
                    "tool_call_id": str(getattr(tc, "id", "") or ""),
                    "ok": bool((result or {}).get("ok")) if isinstance(result, dict) else None,
                    "duration_ms": int(dur),
                    "round": int(round_idx + 1),
                }
            )

        if on_progress:
            on_progress(f"oclaw: tools done ({elapsed_ms}ms)")

    return TurnRunOutcome(
        final_text=str(final_text or ""),
        tool_traces=tuple(tool_traces),
        handoff_note="",
        turn_uuid=turn_uuid,
    )


def run_direct_loop(**kwargs: Any) -> TurnRunOutcome:
    return run_oclaw_direct_loop(**kwargs)


__all__ = ["run_oclaw_direct_loop", "run_direct_loop"]

