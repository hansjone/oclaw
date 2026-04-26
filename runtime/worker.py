from __future__ import annotations

import json
import threading
import time
import uuid
from typing import Any

from oclaw.runtime.agents.factory import build_gateway_executor
from oclaw.runtime.agent_core_run import AgentCoreRunInput, run_agent_core
from oclaw.runtime.memory_stage import build_memory_context
from oclaw.runtime.relay_pointer import build_acp_relay_result, validate_relay_share_envelope
from oclaw.runtime.types import StandardMessage

_LOCK = threading.Lock()
_THREAD: threading.Thread | None = None
_SESSION_TITLE_MAX_LEN = 120
_AUTO_TITLE_STAGE_KEY_PREFIX = "AIA_SESSION_AUTO_TITLE_STAGE:"
_TITLE_TRIGGER_ROUND = 3
_TITLE_BODIES_MAX_CHARS = 4000


def _maybe_rename_from_first_user_message(*, store: Any, session_id: str, user_text: str, attachments: list[dict[str, Any]] | None) -> None:
    sid = str(session_id or "").strip()
    if not sid:
        return
    try:
        stage_raw = str(store.get_setting(f"{_AUTO_TITLE_STAGE_KEY_PREFIX}{sid}") or "").strip()
    except Exception:
        stage_raw = ""
    if stage_raw in ("1", "3"):
        return
    try:
        sess = store.get_session(sid)
    except Exception:
        sess = None
    if not sess:
        return
    cur_title = str(getattr(sess, "title", "") or "").strip()
    if cur_title not in ("新会话", "New Chat"):
        return
    try:
        rows = store.get_messages(session_id=sid, limit=20)
    except Exception:
        rows = []
    user_count = 0
    for r in rows or []:
        if str(getattr(r, "role", "") or "").strip().lower() == "user":
            user_count += 1
    if user_count > 1:
        return
    title = str(user_text or "").strip().replace("\n", " ")
    if not title:
        atts = attachments if isinstance(attachments, list) else []
        if atts and isinstance(atts[0], dict):
            title = str(atts[0].get("name") or "").strip()
    if not title:
        return
    try:
        store.rename_session(sid, title[:_SESSION_TITLE_MAX_LEN])
        try:
            store.set_setting(f"{_AUTO_TITLE_STAGE_KEY_PREFIX}{sid}", "1")
        except Exception:
            pass
    except Exception:
        pass


def _maybe_generate_title_on_third_round(*, store: Any, msg: StandardMessage, model: Any | None) -> None:
    """Generate title once on round-3 using user text only (no tools/reasoning context)."""
    if model is None or not callable(getattr(model, "chat", None)):
        return
    sid = str(msg.session_id or "").strip()
    if not sid:
        return
    try:
        stage_raw = str(store.get_setting(f"{_AUTO_TITLE_STAGE_KEY_PREFIX}{sid}") or "").strip()
    except Exception:
        stage_raw = ""
    try:
        sess = store.get_session(sid)
    except Exception:
        sess = None
    if not sess:
        return
    cur_title = str(getattr(sess, "title", "") or "").strip()
    # Two-stage naming:
    # - stage "1": renamed from first user message
    # - stage "3": renamed on third user message (final)
    if stage_raw == "3":
        return
    if (cur_title not in ("新会话", "New Chat")) and (stage_raw != "1"):
        return
    try:
        rows = store.get_messages(session_id=sid, limit=200)
    except Exception:
        rows = []
    bodies: list[str] = []
    for r in rows or []:
        role = str(getattr(r, "role", "") or "").strip().lower()
        if role != "user":
            continue
        txt = str(getattr(r, "content", "") or "").strip()
        if txt:
            bodies.append(txt)
    cur_txt = str(msg.text or "").strip()
    if cur_txt:
        bodies.append(cur_txt)
    if len(bodies) != _TITLE_TRIGGER_ROUND:
        return
    body = "\n".join(f"{i+1}. {t}" for i, t in enumerate(bodies))
    body = body[:_TITLE_BODIES_MAX_CHARS]
    try:
        lang_is_en = str(msg.metadata.get("lang") if isinstance(msg.metadata, dict) else "").lower().startswith("en")
        sys = (
            "Generate a concise chat title from these user messages only. "
            "Use the dominant language used by the user content body. "
            "Return title text only, no quotes, no markdown, max 18 chars."
            if lang_is_en
            else "仅基于以下用户正文生成简短会话标题。请使用对话内容主体语言命名。"
            "只返回标题文本，不要引号，不要markdown，最多18个字。"
        )
        resp = model.chat(
            [{"role": "system", "content": sys}, {"role": "user", "content": body}],
            [],
            on_token=None,
        )
        title = str(getattr(resp, "content", "") or "").strip().replace("\n", " ")
        title = title.strip("\"'` ").strip()
        if not title:
            return
        store.rename_session(sid, title[:_SESSION_TITLE_MAX_LEN])
        try:
            store.set_setting(f"{_AUTO_TITLE_STAGE_KEY_PREFIX}{sid}", "3")
        except Exception:
            pass
    except Exception:
        return


def ensure_worker_started(*, store: Any, poll_interval_s: float = 1.0) -> str:
    global _THREAD
    with _LOCK:
        if _THREAD and _THREAD.is_alive():
            return _THREAD.name
        wid = f"oclaw-worker-{uuid.uuid4().hex[:8]}"
        t = threading.Thread(
            target=_worker_loop,
            name=wid,
            kwargs={"store": store, "worker_id": wid, "poll_interval_s": max(0.3, float(poll_interval_s or 1.0))},
            daemon=True,
        )
        t.start()
        _THREAD = t
        return wid


def _worker_loop(*, store: Any, worker_id: str, poll_interval_s: float) -> None:
    while True:
        task = None
        try:
            task = store.oclaw_task_claim(worker_id=worker_id, lease_seconds=90)
        except Exception:
            task = None
        if not task:
            time.sleep(poll_interval_s)
            continue

        payload: dict[str, Any] = {}
        try:
            payload = json.loads(task.payload or "{}")
            if not isinstance(payload, dict):
                payload = {}
        except Exception:
            payload = {}

            trace_id = str(payload.get("trace_id") or "")
            run_id = str(payload.get("run_id") or "").strip() or None
        session_id = str(task.session_id or "")
        try:
            if trace_id:
                store.add_trace_event(
                    session_id=session_id,
                    trace_id=trace_id,
                    span_id=str(uuid.uuid4()),
                    parent_span_id=None,
                    event_type="task_claimed",
                    payload={"task_id": task.id, "worker_id": worker_id, "attempt_count": int(task.attempt_count or 0)},
                )
        except Exception:
            pass

        try:
            lang = str(payload.get("lang") or "zh")
            session_id = str(payload.get("session_id") or task.session_id or "")
            user_text = str(payload.get("text") or "")
            attachments = payload.get("attachments") or []
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
            relay_share_envelope = payload.get("relay_share_envelope") if isinstance(payload.get("relay_share_envelope"), dict) else {}
            if relay_share_envelope and "relay_share_envelope" not in metadata:
                metadata["relay_share_envelope"] = relay_share_envelope
            acp_parent_run_id = str(payload.get("acp_parent_run_id") or "").strip()
            acp_child_run_id = str(payload.get("acp_child_run_id") or "").strip()
            if acp_parent_run_id or acp_child_run_id:
                ok_env, env_err, env_norm = validate_relay_share_envelope(relay_share_envelope)
                if not ok_env:
                    fail_result = {
                        "ok": False,
                        "error_code": str(env_err or "relay_envelope_invalid"),
                        "retryable": False,
                        "acp_parent_run_id": acp_parent_run_id,
                        "acp_child_run_id": acp_child_run_id,
                    }
                    store.oclaw_task_fail(task_id=task.id, error=str(env_err or "relay_envelope_invalid"), result=fail_result)
                    if trace_id:
                        store.add_trace_event(
                            session_id=session_id,
                            trace_id=trace_id,
                            span_id=str(uuid.uuid4()),
                            parent_span_id=None,
                            event_type="task_failed",
                            payload={
                                "task_id": task.id,
                                "ok": False,
                                "error": str(env_err or "relay_envelope_invalid"),
                                "error_code": str(env_err or "relay_envelope_invalid"),
                                "retryable": False,
                                "acp_parent_run_id": acp_parent_run_id,
                                "acp_child_run_id": acp_child_run_id,
                            },
                        )
                    continue
                relay_share_envelope = env_norm
                metadata["relay_share_envelope"] = relay_share_envelope
            tenant_id = str(payload.get("tenant_id") or "")
            user_id = str(payload.get("user_id") or "")
            viewer_username = str(payload.get("viewer_username") or "")
            model_profile_id = str(payload.get("model_profile_id") or "") or None
            selected_specialist = str(payload.get("selected_specialist") or "") or str(metadata.get("selected_specialist") or "")
            memory_ctx = build_memory_context(
                store=store,
                session_id=session_id,
                tenant_id=tenant_id,
                user_id=user_id,
                query_text=user_text,
            )
            executor = build_gateway_executor(
                store,
                lang=lang,
                specialist=selected_specialist or "generalist",
                profile_id=model_profile_id,
                viewer_user_id=user_id or None,
                viewer_username=viewer_username or None,
                viewer_tenant_id=tenant_id or None,
                policy_session_id=session_id or None,
                path_policy_tenant_id=tenant_id or None,
                path_policy_user_id=user_id or None,
            )
            system_prompt = ""
            if hasattr(executor, "_compose_system_prompt"):
                try:
                    system_prompt = str(executor._compose_system_prompt() or "")
                except Exception:
                    system_prompt = ""
            if not system_prompt:
                system_prompt = str(getattr(executor, "system_prompt", "") or "")

            max_messages = int(store.get_setting("AIA_TURN_MAX_CONTEXT_MESSAGES") or 80)
            max_tool_rounds = int(store.get_setting("AIA_TURN_MAX_TOOL_ROUNDS") or 8)
            max_tool_workers = int(store.get_setting("AIA_TURN_MAX_TOOL_WORKERS") or 8)

            msg = StandardMessage(
                session_id=session_id,
                tenant_id=tenant_id,
                user_id=user_id,
                role=str(payload.get("role") or "member"),
                channel=str(payload.get("channel") or "admin_chat"),  # type: ignore[arg-type]
                text=user_text,
                attachments=list(attachments or []),
                metadata=dict(metadata or {}),
            )
            _maybe_rename_from_first_user_message(
                store=store,
                session_id=session_id,
                user_text=user_text,
                attachments=list(attachments or []),
            )
            _maybe_generate_title_on_third_round(
                store=store,
                msg=msg,
                model=getattr(executor, "model", None),
            )
            run_out = run_agent_core(
                store=store,
                data=AgentCoreRunInput(
                    msg=msg,
                    lang=lang,
                    system_prompt=system_prompt,
                    model=executor.model,
                    tools=executor.tools,
                    trace_id=trace_id or None,
                    parent_span_id=None,
                    run_id=run_id,
                    max_messages=max(10, min(max_messages, 400)),
                    max_tool_rounds=max(1, min(max_tool_rounds, 30)),
                    max_tool_workers=max(1, min(max_tool_workers, 32)),
                    max_attempts=2,
                    memory_context=memory_ctx,
                    oclaw_task_id=str(task.id),
                    oclaw_worker_id=worker_id,
                ),
            )
            base_result = {
                "run_id": str(run_out.run_id or ""),
                "reply_text": run_out.outcome.final_text,
                "tool_trace_count": len(run_out.outcome.tool_traces),
                "relay_pointer_count": int(payload.get("relay_pointer_count") or 0),
                "relay_envelope_present": bool(isinstance(relay_share_envelope, dict) and bool(relay_share_envelope)),
            }
            if acp_parent_run_id or acp_child_run_id:
                base_result.update(
                    build_acp_relay_result(
                        parent_run_id=acp_parent_run_id,
                        child_run_id=acp_child_run_id,
                        relay_envelope=relay_share_envelope,
                    )
                )
            store.oclaw_task_finish(task_id=task.id, result=base_result)
            if trace_id:
                trace_payload = {
                    "task_id": task.id,
                    "ok": True,
                    "tool_trace_count": len(run_out.outcome.tool_traces),
                    "relay_pointer_count": int(payload.get("relay_pointer_count") or 0),
                    "relay_envelope_present": bool(isinstance(relay_share_envelope, dict) and bool(relay_share_envelope)),
                }
                if acp_parent_run_id or acp_child_run_id:
                    trace_payload.update(
                        {
                            "acp_parent_run_id": acp_parent_run_id,
                            "acp_child_run_id": acp_child_run_id,
                        }
                    )
                store.add_trace_event(
                    session_id=session_id,
                    trace_id=trace_id,
                    span_id=str(uuid.uuid4()),
                    parent_span_id=None,
                    event_type="task_finished",
                    payload=trace_payload,
                )
        except Exception as exc:
            store.oclaw_task_fail(task_id=task.id, error=str(exc), result={"ok": False})
            try:
                if trace_id:
                    store.add_trace_event(
                        session_id=session_id,
                        trace_id=trace_id,
                        span_id=str(uuid.uuid4()),
                        parent_span_id=None,
                        event_type="task_failed",
                        payload={"task_id": task.id, "ok": False, "error": str(exc)[:500]},
                    )
            except Exception:
                pass


__all__ = ["ensure_worker_started"]

