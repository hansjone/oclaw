from __future__ import annotations

import json
import os
import re
import time
import uuid
import copy
import threading
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Optional

from oclaw.runtime.chat.agent_messages import build_llm_messages, get_last_build_llm_messages_stats
from oclaw.runtime.chat.media_redact import redact_embedded_image_blobs
from oclaw.runtime.chat.tool_runtime import ToolExecutionConfig
from oclaw.runtime.chat.turn_types import TurnRunOutcome
from oclaw.runtime.skill_executor import SkillExecutionContext, SkillExecutor
from oclaw.runtime.skills import build_skill_manifest
from oclaw.platform.llm.chat_models import ChatModel
from oclaw.runtime.system_prompt import build_oclaw_executor_system_prompt
from oclaw.runtime.types import OclawMemoryContext
from oclaw.runtime.orchestration.trace import new_span_id
from oclaw.runtime.tools.base import ToolRegistry
from oclaw.runtime.hooks_runtime import trigger_hook_event
from oclaw.runtime.tools.experts.network_ops.netx_tools import ops_netx_system_context_extension

_OCLAW_TOOL_RESULT_HARD_CAP_CHARS = 24_000
_OCLAW_ATTACHMENT_TEXT_REPLAY_CAP_CHARS = 4_000
_OCLAW_IMAGE_TOOL_RESULT_REPLAY_CAP_CHARS = 4_000

_DIRECT_LOOP_OC_STAGE: dict[str, str] = {
    "tool_wire_filter": "wire_filter",
    "tool_result_context_guard": "tool_context_guard",
    "tool_pairing_guard": "tool_pairing_guard",
}
_THINK_BLOCK_RE = re.compile(r"<(think|redacted_thinking)>\s*(.*?)\s*</\1>\s*", flags=re.IGNORECASE | re.DOTALL)
_DSML_INVOKE_NAME_RE = re.compile(r"invoke\s+name\s*=\s*['\"]([^'\"\s>]+)['\"]", flags=re.IGNORECASE)
_JSON_TOOL_NAME_RE = re.compile(r"['\"]name['\"]\s*:\s*['\"]([^'\"\s]{1,120})['\"]", flags=re.IGNORECASE)
_TOOL_WIRE_CACHE_LOCK = threading.Lock()
_TOOL_WIRE_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_TOOL_WIRE_CACHE_TTL_SEC = 300.0
_TOOL_WIRE_FROZEN_SIGNATURE: str | None = None
_TOOL_WIRE_LAST_WARM_TS_MS: int = 0
_TOOL_WIRE_LAST_WARM_ROLES: tuple[str, ...] = ()
_TOOL_WIRE_LAST_WARM_COUNT: int = 0


def _safe_int(raw: Any, default: int, *, min_value: int = 1, max_value: int = 2_000_000) -> int:
    try:
        value = int(raw)
    except Exception:
        return default
    if value < min_value:
        return default
    return min(value, max_value)


def _safe_nonneg_int(raw: Any, default: int, *, max_value: int = 2_000_000) -> int:
    try:
        value = int(raw)
    except Exception:
        return max(0, int(default))
    if value < 0:
        return max(0, int(default))
    return min(value, max_value)


def _oclaw_config_path() -> Path:
    raw = str(os.getenv("AIA_OCLAW_CONFIG_PATH") or "").strip()
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else p.resolve()
    return Path(__file__).resolve().parents[1] / "oclaw.json"


def _image_tool_result_replay_cap_chars(store: Any) -> int:
    default = _OCLAW_IMAGE_TOOL_RESULT_REPLAY_CAP_CHARS
    raw_setting = ""
    try:
        raw_setting = str(store.get_setting("AIA_IMAGE_TOOL_RESULT_REPLAY_CAP_CHARS") or "").strip()
    except Exception:
        raw_setting = ""
    if raw_setting:
        return _safe_int(raw_setting, default, min_value=600, max_value=30_000)
    raw_env = str(os.getenv("AIA_IMAGE_TOOL_RESULT_REPLAY_CAP_CHARS") or "").strip()
    if raw_env:
        return _safe_int(raw_env, default, min_value=600, max_value=30_000)
    try:
        cfg_path = _oclaw_config_path()
        if cfg_path.exists() and cfg_path.is_file():
            obj = json.loads(cfg_path.read_text(encoding="utf-8"))
            tab = (
                (((obj.get("plugins") or {}).get("entries") or {}).get("memory-wiki") or {})
                .get("auto", {})
                .get("attachments", {})
                .get("tabular", {})
            )
            if isinstance(tab, dict):
                return _safe_int(tab.get("image_result_replay_cap_chars"), default, min_value=600, max_value=30_000)
    except Exception:
        pass
    return default


def _video_tool_result_replay_cap_chars(store: Any) -> int:
    default = 4_000
    raw_setting = ""
    try:
        raw_setting = str(store.get_setting("AIA_VIDEO_TOOL_RESULT_REPLAY_CAP_CHARS") or "").strip()
    except Exception:
        raw_setting = ""
    if raw_setting:
        return _safe_int(raw_setting, default, min_value=600, max_value=30_000)
    raw_env = str(os.getenv("AIA_VIDEO_TOOL_RESULT_REPLAY_CAP_CHARS") or "").strip()
    if raw_env:
        return _safe_int(raw_env, default, min_value=600, max_value=30_000)
    try:
        cfg_path = _oclaw_config_path()
        if cfg_path.exists() and cfg_path.is_file():
            obj = json.loads(cfg_path.read_text(encoding="utf-8"))
            tab = (
                (((obj.get("plugins") or {}).get("entries") or {}).get("memory-wiki") or {})
                .get("auto", {})
                .get("attachments", {})
                .get("tabular", {})
            )
            if isinstance(tab, dict):
                return _safe_int(tab.get("video_result_replay_cap_chars"), default, min_value=600, max_value=30_000)
    except Exception:
        pass
    return default


def _tool_wire_freeze_enabled(store: Any) -> bool:
    raw = ""
    try:
        raw = str(store.get_setting("AIA_TOOL_WIRE_FROZEN_ON_STARTUP") or "").strip().lower()
    except Exception:
        raw = ""
    if not raw:
        raw = str(os.getenv("AIA_TOOL_WIRE_FROZEN_ON_STARTUP") or "").strip().lower()
    if not raw:
        return True
    return raw in {"1", "true", "yes", "on"}


def _tool_wire_settings_signature(store: Any) -> tuple[bool, str]:
    runtime_enabled = True
    try:
        raw_flag = str(store.get_setting("AIA_SKILL_RUNTIME_ENABLED") or "").strip().lower()
        if raw_flag:
            runtime_enabled = raw_flag in {"1", "true", "yes", "on"}
    except Exception:
        runtime_enabled = True
    sig = "|".join(
        [
            f"rt={int(bool(runtime_enabled))}",
            f"mcp={str(store.get_setting('AIA_ENABLE_MCP_TOOLS') or '')}",
            f"plugin={str(store.get_setting('AIA_ENABLE_PLUGIN_TOOLS') or '')}",
            f"skill_rt={str(store.get_setting('AIA_SKILL_RUNTIME_ENABLED') or '')}",
            f"skill_disabled={str(store.get_setting('AIA_SKILL_DISABLED_NAMES') or '')}",
            f"bind_en={str(store.get_setting('AIA_SKILL_ROLE_BINDING_ENABLED') or '')}",
            f"bind_inherit={str(store.get_setting('AIA_SKILL_ROLE_BINDING_MANAGER_INHERIT') or '')}",
        ]
    )
    return runtime_enabled, sig


def _tool_wire_cache_key(
    *,
    store: Any,
    base_url: str,
    wire_policy_role: str | None,
    runtime_enabled: bool,
    settings_sig: str | None = None,
) -> str:
    _, sig = _tool_wire_settings_signature(store)
    effective_sig = str(settings_sig or sig)
    return (
        f"base={base_url}|role={str(wire_policy_role or '').strip().lower()}|"
        f"rt={int(bool(runtime_enabled))}|{effective_sig}"
    )


def warm_tool_wire_cache(
    *,
    store: Any,
    tools: ToolRegistry,
    base_url: str,
    roles: list[str] | tuple[str, ...],
) -> dict[str, int]:
    global _TOOL_WIRE_FROZEN_SIGNATURE, _TOOL_WIRE_LAST_WARM_TS_MS, _TOOL_WIRE_LAST_WARM_ROLES, _TOOL_WIRE_LAST_WARM_COUNT
    freeze_enabled = _tool_wire_freeze_enabled(store)
    runtime_enabled, sig = _tool_wire_settings_signature(store)
    warmed = 0
    for role in roles or []:
        _ = _prepare_llm_tools(
            store=store,
            tools=tools,
            base_url=base_url,
            session_id="startup-prewarm",
            trace_id=None,
            parent_span_id=None,
            run_id="startup-prewarm",
            attempt_no=0,
            lang="",
            wire_policy_role=str(role or "").strip().lower() or None,
        )
        warmed += 1
    with _TOOL_WIRE_CACHE_LOCK:
        _TOOL_WIRE_FROZEN_SIGNATURE = f"rt={int(bool(runtime_enabled))}|{sig}" if freeze_enabled else None
        _TOOL_WIRE_LAST_WARM_TS_MS = int(time.time() * 1000)
        _TOOL_WIRE_LAST_WARM_ROLES = tuple(str(x or "").strip().lower() for x in roles or [])
        _TOOL_WIRE_LAST_WARM_COUNT = int(warmed)
    return {"roles_warmed": int(warmed), "frozen": int(bool(freeze_enabled))}


def tool_wire_freeze_status(*, store: Any | None = None) -> dict[str, Any]:
    enabled = True
    if store is not None:
        enabled = _tool_wire_freeze_enabled(store)
    with _TOOL_WIRE_CACHE_LOCK:
        return {
            "enabled": bool(enabled),
            "frozen": bool(isinstance(_TOOL_WIRE_FROZEN_SIGNATURE, str) and _TOOL_WIRE_FROZEN_SIGNATURE.strip()),
            "frozen_signature": str(_TOOL_WIRE_FROZEN_SIGNATURE or ""),
            "last_warm_ts_ms": int(_TOOL_WIRE_LAST_WARM_TS_MS),
            "last_warm_roles": list(_TOOL_WIRE_LAST_WARM_ROLES),
            "last_warm_count": int(_TOOL_WIRE_LAST_WARM_COUNT),
            "cache_entries": int(len(_TOOL_WIRE_CACHE)),
        }


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


def _tool_message_with_content(m: Any, content: str, *, sid: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        id=getattr(m, "id", 0),
        session_id=str(getattr(m, "session_id", None) or sid or ""),
        role="tool",
        content=content,
        tool_calls=getattr(m, "tool_calls", None),
        timestamp=getattr(m, "timestamp", ""),
        attachments=getattr(m, "attachments", None),
        turn_uuid=getattr(m, "turn_uuid", None),
        event_type=getattr(m, "event_type", None),
        event_payload=getattr(m, "event_payload", None),
    )


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
    active_turn_uuid: str | None = None,
) -> list[Any]:
    """Hard-guard overlarge `role=tool` message contents before sending to model.

    This does NOT rewrite DB history (tool_log / chat_message). It only guards the
    in-flight LLM context to prevent provider context overflow spirals.
    """
    cap = max(4096, min(int(hard_cap_chars or _OCLAW_TOOL_RESULT_HARD_CAP_CHARS), 500_000))
    image_cap = _image_tool_result_replay_cap_chars(store)
    video_cap = _video_tool_result_replay_cap_chars(store)
    out: list[Any] = []
    for m in store_messages or []:
        role = str(getattr(m, "role", "") or "")
        if role != "tool":
            out.append(m)
            continue
        if str(getattr(m, "turn_uuid", "") or "") == str(active_turn_uuid or "") and str(active_turn_uuid or "").strip():
            out.append(m)
            continue
        raw = str(getattr(m, "content", "") or "")
        try:
            _parsed0 = json.loads(raw)
            _parsed1 = redact_embedded_image_blobs(_parsed0)
            raw = _json_dumps_safe(_parsed1)
        except Exception:
            pass
        # Best-effort parse tool JSON for image-query specific guard and overflow metadata.
        ok = None
        error_code = ""
        error = ""
        obj: dict[str, Any] | None = None
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                obj = parsed
                ok = obj.get("ok")
                error_code = str(obj.get("error_code") or "").strip()
                error = str(obj.get("error") or "").strip()
        except Exception:
            obj = None
        if isinstance(obj, dict):
            task = str(obj.get("task") or "").strip().lower()
            text = str(obj.get("text") or "")
            has_attachment_id = bool(str(obj.get("attachment_id") or "").strip())
            # Guard image describe/OCR result replay aggressively to avoid long visual transcripts
            # occupying context across future rounds.
            if task in {"describe", "ocr"} and has_attachment_id and len(text) > image_cap:
                preview = text[:image_cap] + "\n...<image_tool_result_truncated_for_context_replay>"
                guarded_obj = dict(obj)
                guarded_obj["text"] = preview
                guarded_obj["_image_tool_result_guarded"] = True
                guarded_obj["image_result_original_chars"] = len(text)
                guarded_obj["image_result_replay_cap_chars"] = image_cap
                guarded_obj["image_result_hint"] = (
                    "Image analysis result was truncated for context replay. "
                    "Refine query_image_attachment(question=...) for narrower evidence. / "
                    "图片分析结果在上下文回放中已截断，请缩小 query_image_attachment 的问题范围。"
                )
                guarded = _json_dumps_safe(guarded_obj)
                out.append(_tool_message_with_content(m, guarded, sid=session_id))
                continue
            # Guard video transcript replay similarly (usually long).
            if str(obj.get("task") or "").strip().lower() == "transcript" and has_attachment_id and len(text) > video_cap:
                preview = text[:video_cap] + "\n...<video_tool_result_truncated_for_context_replay>"
                guarded_obj = dict(obj)
                guarded_obj["text"] = preview
                guarded_obj["_video_tool_result_guarded"] = True
                guarded_obj["video_result_original_chars"] = len(text)
                guarded_obj["video_result_replay_cap_chars"] = video_cap
                guarded = _json_dumps_safe(guarded_obj)
                out.append(_tool_message_with_content(m, guarded, sid=session_id))
                continue
        if len(raw) <= cap:
            out.append(_tool_message_with_content(m, raw, sid=session_id))
            continue
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
        out.append(_tool_message_with_content(m, guarded, sid=session_id))
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


def _guard_text_attachments_for_llm_context(
    *,
    store_messages: list[Any],
    cap_chars: int,
    active_turn_uuid: str | None = None,
) -> list[Any]:
    """Guard overlarge user text attachments for model context replay.

    This does NOT rewrite DB history. It only guards the in-flight LLM context to
    prevent large attachments from overwhelming context windows.
    """
    cap = max(800, min(int(cap_chars or _OCLAW_ATTACHMENT_TEXT_REPLAY_CAP_CHARS), 80_000))
    out: list[Any] = []
    for m in store_messages or []:
        role = str(getattr(m, "role", "") or "")
        if role != "user":
            out.append(m)
            continue
        # Never guard the active user turn.
        if str(getattr(m, "turn_uuid", "") or "") == str(active_turn_uuid or "") and str(active_turn_uuid or "").strip():
            out.append(m)
            continue
        raw_att = getattr(m, "attachments", None)
        if not raw_att:
            out.append(m)
            continue
        try:
            att_obj = json.loads(raw_att) if isinstance(raw_att, str) else raw_att
        except Exception:
            out.append(m)
            continue
        if isinstance(att_obj, dict):
            atts = [att_obj]
        elif isinstance(att_obj, list):
            atts = att_obj
        else:
            out.append(m)
            continue
        has_text_ref = any(
            isinstance(a, dict) and str(a.get("type") or "").strip().lower() == "text_ref" for a in atts
        )
        changed = False
        next_atts: list[dict[str, Any]] = []
        for a in atts:
            if not isinstance(a, dict):
                continue
            if str(a.get("type") or "").strip().lower() != "text":
                next_atts.append(a)
                continue
            content = str(a.get("content") or "")
            # If this user message already has a text_ref, keep inline text very small in replay context.
            # The model can retrieve evidence via query_text_attachment(text_id=...).
            if has_text_ref and content:
                changed = True
                name = str(a.get("name") or "attachment")
                next_atts.append(
                    {
                        **a,
                        "content": (
                            "# Attachment (collapsed; text_ref available)\n"
                            f"- name: {name}\n"
                            "- note: use `query_text_attachment` with `text_id` from `text_ref` for details.\n"
                            "...<attachment_collapsed_for_context_replay>"
                        ),
                        "_attachment_context_guarded": True,
                        "_attachment_context_collapsed": True,
                    }
                )
                continue
            if len(content) <= cap:
                next_atts.append(a)
                continue
            changed = True
            name = str(a.get("name") or "attachment")
            hint_lines = [
                "# Attachment (summarized for context replay)",
                f"- name: {name}",
                f"- original_chars: {len(content)}",
                f"- replay_cap_chars: {cap}",
            ]
            if has_text_ref:
                hint_lines.append("- note: use `query_text_attachment` with `text_id` from `text_ref` for details.")
            else:
                hint_lines.append("- note: attachment was large; re-upload or provide a smaller excerpt if needed.")
            preview = content[: min(1200, cap)]
            next_atts.append(
                {
                    **a,
                    "content": "\n".join(hint_lines) + "\n\n## Preview\n" + preview + "\n\n...<attachment_truncated_for_context_replay>",
                    "_attachment_context_guarded": True,
                }
            )
        if not changed:
            out.append(m)
            continue
        out.append(
            SimpleNamespace(
                id=getattr(m, "id", 0),
                session_id=getattr(m, "session_id", ""),
                role="user",
                content=getattr(m, "content", ""),
                tool_calls=getattr(m, "tool_calls", None),
                timestamp=getattr(m, "timestamp", ""),
                attachments=next_atts,
                turn_uuid=getattr(m, "turn_uuid", ""),
                event_type=getattr(m, "event_type", ""),
                event_payload=getattr(m, "event_payload", None),
            )
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
    workspace_owner_session_id: str | None = None,
    user_text: str = "",
    prompt_build_context: dict[str, Any] | None = None,
    active_turn_uuid: str | None = None,
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
        active_turn_uuid=active_turn_uuid,
    )
    rows = _guard_text_attachments_for_llm_context(
        store_messages=rows,
        cap_chars=_OCLAW_ATTACHMENT_TEXT_REPLAY_CAP_CHARS,
        active_turn_uuid=active_turn_uuid,
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
        workspace_owner_session_id=workspace_owner_session_id,
        session_id=session_id,
    )
    # Hook integration: wiki-auto-inject can prepend retrieval snippets
    # before prompt build when query/topic hints indicate supplemental lookup.
    try:
        pb_ctx = prompt_build_context if isinstance(prompt_build_context, dict) else {}
        user_text_final = str(user_text or "").strip()
        wiki_query = str(pb_ctx.get("wiki_query") or "").strip()
        hook_ctx = {
            "userText": (wiki_query or user_text_final),
            "prepend_system_context": "",
            "need_wiki_inject": pb_ctx.get("need_wiki_inject"),
            "memory_mode": str(pb_ctx.get("memory_mode") or ""),
            "wiki_query": wiki_query,
        }
        hook_out = trigger_hook_event(
            event_type="llm",
            action="before_prompt_build",
            session_key=str(session_id or "system"),
            context=hook_ctx,
        )
        prepend = str((hook_out or {}).get("prepend_system_context") or "").strip()
        if prepend:
            final_system = f"{prepend}\n\n{final_system}".strip()
    except Exception:
        pass
    try:
        if str(skill_binding_role or "").strip().lower() == "ops":
            ext = ops_netx_system_context_extension(lang=lang or "zh")
            if str(ext or "").strip():
                final_system = f"{final_system}\n\n{ext.strip()}".strip()
    except Exception:
        pass
    trunc_raw = str(store.get_setting("AIA_TOOL_CONTEXT_TRUNCATE_ENABLED") or "").strip().lower()
    tool_context_truncate_enabled = trunc_raw not in ("0", "false", "no", "off")
    llm_messages = build_llm_messages(
        store_messages=rows,
        system_prompt=final_system,
        model=model,
        lang=lang,
        tool_context_truncate_enabled=tool_context_truncate_enabled,
        active_turn_uuid=active_turn_uuid,
    )
    try:
        stats = get_last_build_llm_messages_stats()
        dropped_unpaired = int(stats.get("dropped_unpaired_tool_rows") or 0)
        dropped_no_id = int(stats.get("dropped_no_id_tool_rows") or 0)
        dropped_total = dropped_unpaired + dropped_no_id
        if dropped_total > 0 and trace_id:
            _emit_direct_loop_trace(
                store=store,
                session_id=session_id,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                event_type="tool_pairing_guard",
                payload={
                    "dropped_total": int(dropped_total),
                    "dropped_unpaired_tool_rows": int(dropped_unpaired),
                    "dropped_no_id_tool_rows": int(dropped_no_id),
                },
                run_id=run_id,
                attempt_no=attempt_no,
                lang=lang,
            )
    except Exception:
        pass
    return llm_messages


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
    global _TOOL_WIRE_FROZEN_SIGNATURE
    now = time.time()
    runtime_enabled, sig = _tool_wire_settings_signature(store)
    freeze_enabled = _tool_wire_freeze_enabled(store)
    frozen_sig = _TOOL_WIRE_FROZEN_SIGNATURE if freeze_enabled else None
    if isinstance(frozen_sig, str) and frozen_sig.strip():
        # Startup-prewarmed frozen mode: execution path reuses precomputed tool wiring
        # and does not perform per-turn policy revalidation.
        sig = frozen_sig
        try:
            rt_head = str(frozen_sig).split("|", 1)[0].strip().lower()
            runtime_enabled = rt_head == "rt=1"
        except Exception:
            pass
    cache_key = _tool_wire_cache_key(
        store=store,
        base_url=base_url,
        wire_policy_role=wire_policy_role,
        runtime_enabled=runtime_enabled,
        settings_sig=sig,
    )
    with _TOOL_WIRE_CACHE_LOCK:
        cached = _TOOL_WIRE_CACHE.get(cache_key)
        if cached and (
            (isinstance(frozen_sig, str) and frozen_sig.strip())
            or (now - float(cached[0])) <= _TOOL_WIRE_CACHE_TTL_SEC
        ):
            return copy.deepcopy(cached[1])

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
    with _TOOL_WIRE_CACHE_LOCK:
        _TOOL_WIRE_CACHE[cache_key] = (now, copy.deepcopy(llm_tools))
        if len(_TOOL_WIRE_CACHE) > 256:
            oldest_key = sorted(_TOOL_WIRE_CACHE.items(), key=lambda kv: kv[1][0])[0][0]
            _TOOL_WIRE_CACHE.pop(oldest_key, None)
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


def _chat_with_empty_body_retry(
    *,
    model: Any,
    msgs: list[dict[str, Any]],
    llm_tools: list[dict[str, Any]],
    on_token: Optional[Callable[[str], None]],
    on_progress: Optional[Callable[[str], None]],
    progress_label: str = "oclaw: think",
) -> Any:
    # Empty assistant body can occur transiently at upstream gateways.
    # Retry until non-empty (bounded by retry count and total timeout).
    retry_max = _safe_nonneg_int(os.getenv("AIA_EMPTY_ASSISTANT_RETRY_MAX"), 1, max_value=3)
    retry_delay_ms = _safe_nonneg_int(os.getenv("AIA_EMPTY_ASSISTANT_RETRY_DELAY_MS"), 1200, max_value=15_000)
    retry_total_timeout_ms = _safe_nonneg_int(os.getenv("AIA_EMPTY_ASSISTANT_RETRY_TOTAL_TIMEOUT_MS"), 30_000, max_value=300_000)
    started = time.perf_counter()
    retries_done = 0
    resp = model.chat(msgs, llm_tools, on_token=on_token)
    while True:
        content = str(getattr(resp, "content", "") or "")
        tool_calls = list(getattr(resp, "tool_calls", []) or [])
        textual_tool_intent = (not tool_calls) and bool(_extract_textual_tool_intent_names(content))
        if (content.strip() or tool_calls) and not textual_tool_intent:
            return resp
        elapsed_ms = int((time.perf_counter() - started) * 1000.0)
        if retries_done >= retry_max or elapsed_ms >= retry_total_timeout_ms:
            return resp
        if textual_tool_intent:
            if on_progress:
                on_progress(f"{progress_label} retry-native-tool-calls ({retries_done + 1}/{retry_max})…")
            repair_msgs = list(msgs) + [
                {
                    "role": "system",
                    "content": (
                        "Do not output textual tool intent/templates (DSML/XML/JSON). "
                        "If a tool is needed, return native tool_calls only."
                    ),
                }
            ]
            retries_done += 1
            resp = model.chat(repair_msgs, llm_tools, on_token=on_token)
            continue
        if on_progress:
            on_progress(f"{progress_label} retry-empty ({retries_done + 1}/{retry_max})…")
        if retry_delay_ms > 0:
            time.sleep(float(retry_delay_ms) / 1000.0)
        retries_done += 1
        resp = model.chat(msgs, llm_tools, on_token=on_token)


def _extract_dsml_invoke_names(text: str) -> list[str]:
    raw = str(text or "")
    if not raw:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for m in _DSML_INVOKE_NAME_RE.finditer(raw):
        nm = str(m.group(1) or "").strip()
        if not nm or nm in seen:
            continue
        seen.add(nm)
        out.append(nm)
        if len(out) >= 8:
            break
    return out


def _extract_textual_tool_intent_names(text: str) -> list[str]:
    raw = str(text or "")
    if not raw:
        return []
    lower = raw.lower()
    marker_hit = ("tool_calls" in lower) or ("invoke name" in lower) or ("parameter name" in lower)
    if not marker_hit:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for nm in _extract_dsml_invoke_names(raw):
        key = str(nm or "").strip()
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    if len(out) < 8:
        for m in _JSON_TOOL_NAME_RE.finditer(raw):
            nm = str(m.group(1) or "").strip()
            if not nm or nm in seen:
                continue
            seen.add(nm)
            out.append(nm)
            if len(out) >= 8:
                break
    if out:
        return out
    return ["unknown_tool"]


def _persist_dsml_protocol_mismatch_step(
    *,
    store: Any,
    session_id: str,
    turn_uuid: str,
    assistant_text: str,
    invoke_names: list[str],
) -> _LoopStepResult:
    names = [str(x or "").strip() for x in (invoke_names or []) if str(x or "").strip()]
    if not names:
        names = ["unknown_tool"]
    stored_tool_calls: list[dict[str, Any]] = []
    for nm in names:
        stored_tool_calls.append(
            {
                "id": f"call_dsml_{uuid.uuid4().hex}",
                "name": nm,
                "arguments": {},
                "thought_signature": None,
            }
        )
    assistant_row = store.add_message(
        session_id=session_id,
        role="assistant",
        content="",
        tool_calls=stored_tool_calls,
        turn_uuid=turn_uuid,
        event_type="tool_call",
        event_payload={
            "protocol_mismatch": "textual_tool_intent",
            "raw_excerpt": str(assistant_text or "")[:2000],
        },
    )
    for tc in stored_tool_calls:
        tcid = str(tc.get("id") or "").strip()
        tname = str(tc.get("name") or "").strip() or "unknown_tool"
        tool_result = {
            "ok": False,
            "error_code": "model_protocol_mismatch_dsml",
            "error": "model_returned_textual_tool_intent_instead_of_native_tool_calls",
            "detail": {"tool_name": tname},
        }
        store.add_message(
            session_id=session_id,
            role="tool",
            content=_json_dumps_safe(tool_result),
            tool_calls={
                "tool_call_id": tcid,
                "name": tname,
                "assistant_message_id": int(getattr(assistant_row, "id", 0) or 0),
            },
            turn_uuid=turn_uuid,
            event_type="tool_result",
            event_payload={"tool_name": tname, "protocol_mismatch": "textual_tool_intent"},
        )
    return _LoopStepResult(
        assistant_text="",
        llm_tool_calls=[],
        assistant_msg_id=int(getattr(assistant_row, "id", 0) or 0),
    )


def _persist_assistant_step(
    *,
    store: Any,
    session_id: str,
    turn_uuid: str,
    assistant_text: str,
    reasoning_text: str,
    llm_tool_calls: list[Any],
    thinking_mode_enabled: bool = False,
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

    reasoning_chunks, assistant_body = _split_reasoning_and_body(assistant_text, explicit_reasoning=reasoning_text)
    reasoning_full = "\n".join([str(x or "").strip() for x in reasoning_chunks if str(x or "").strip()]).strip()
    # Keep empty body as-is when model returns nothing and there are no tool calls.
    # The UI should treat this as an invisible intermediate/final empty response.
    if not thinking_mode_enabled:
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
        event_payload=({"reasoning_content": reasoning_full} if (thinking_mode_enabled and reasoning_full) else None),
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
    workspace_dir: str | None,
    workspace_owner_session_id: str | None,
    path_policy_tenant_id: str | None,
    path_policy_user_id: str | None,
    assistant_msg_id: int,
    llm_tool_calls: list[Any],
    on_tool_ui: Optional[Callable[[str, dict[str, Any]], None]],
    should_stop: Optional[Callable[[], bool]],
    signature_budget: int,
    workspace_lane_role: str | None = None,
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
            workspace_dir=workspace_dir,
            workspace_owner_session_id=workspace_owner_session_id,
            path_policy_tenant_id=path_policy_tenant_id,
            path_policy_user_id=path_policy_user_id,
            run_id=run_id,
            attempt_no=attempt_no,
            turn_uuid=turn_uuid,
            workspace_lane_role=workspace_lane_role,
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
    persisted_user_text: str | None = None,
    tool_signature_budget: int = 2,
    skill_binding_role: str | None = None,
    wire_policy_role: str | None = None,
    prompt_build_context: dict[str, Any] | None = None,
    turn_uuid: str | None = None,
) -> TurnRunOutcome:
    """A minimal oclaw-style loop: model -> tool_uses -> execute -> tool_results -> continue."""
    _check_stop(should_stop)
    turn_uuid = str(turn_uuid or "").strip() or str(uuid.uuid4())
    persisted_text = str(user_text if persisted_user_text is None else persisted_user_text or "")
    if persist_user_message:
        store.add_message(
            session_id=session_id,
            role="user",
            content=persisted_text,
            attachments=attachments,
            turn_uuid=turn_uuid,
            event_type="user_text",
        )

    skill_exec = SkillExecutor(config=ToolExecutionConfig(max_workers=max(1, min(int(max_tool_workers or 8), 32))))
    tool_traces: list[dict[str, Any]] = []
    final_text = ""
    hit_tool_round_limit = False
    workspace_lane_role = str(skill_binding_role or wire_policy_role or "generalist").strip().lower() or "generalist"

    base_url = str(getattr(model, "base_url", "") or "")

    max_rounds = max(1, int(max_tool_rounds or 1))
    for round_idx in range(max_rounds):
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
            workspace_owner_session_id=workspace_owner_session_id,
            user_text=str(user_text or ""),
            prompt_build_context=prompt_build_context,
            active_turn_uuid=turn_uuid,
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
        resp = _chat_with_empty_body_retry(
            model=model,
            msgs=msgs,
            llm_tools=llm_tools,
            on_token=on_token,
            on_progress=on_progress,
            progress_label="oclaw: think",
        )
        assistant_text = str(getattr(resp, "content", "") or "")
        reasoning_text = str(getattr(resp, "reasoning_content", "") or "")
        llm_tool_calls = list(getattr(resp, "tool_calls", []) or [])
        textual_tool_intent_names = _extract_textual_tool_intent_names(assistant_text) if not llm_tool_calls else []

        if textual_tool_intent_names:
            step = _persist_dsml_protocol_mismatch_step(
                store=store,
                session_id=session_id,
                turn_uuid=turn_uuid,
                assistant_text=assistant_text,
                invoke_names=textual_tool_intent_names,
            )
        else:
            step = _persist_assistant_step(
                store=store,
                session_id=session_id,
                turn_uuid=turn_uuid,
                assistant_text=assistant_text,
                reasoning_text=reasoning_text,
                llm_tool_calls=llm_tool_calls,
                thinking_mode_enabled=bool(getattr(model, "thinking_mode_enabled", False)),
            )
        final_text = step.assistant_text
        if not step.llm_tool_calls:
            break
        if round_idx == (max_rounds - 1):
            # Reached tool-round cap with pending tool calls. Execute this batch, then
            # force one no-tool synthesis pass to guarantee a visible assistant body.
            hit_tool_round_limit = True

        elapsed_ms, results_by_id = _execute_tool_step(
            skill_exec=skill_exec,
            store=store,
            tools=tools,
            session_id=session_id,
            lang=lang,
            user_text=str(user_text or ""),
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            workspace_dir=workspace_dir,
            workspace_owner_session_id=workspace_owner_session_id,
            path_policy_tenant_id=path_policy_tenant_id,
            path_policy_user_id=path_policy_user_id,
            assistant_msg_id=step.assistant_msg_id,
            llm_tool_calls=step.llm_tool_calls,
            on_tool_ui=on_tool_ui,
            should_stop=should_stop,
            signature_budget=tool_signature_budget,
            workspace_lane_role=workspace_lane_role,
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

    if hit_tool_round_limit:
        _check_stop(should_stop)
        if on_progress:
            on_progress("oclaw: finalize…")
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
            workspace_owner_session_id=workspace_owner_session_id,
            user_text=str(user_text or ""),
            prompt_build_context=prompt_build_context,
            active_turn_uuid=turn_uuid,
        )
        # Final pass forbids extra tool calls; model must synthesize answer.
        resp = _chat_with_empty_body_retry(
            model=model,
            msgs=msgs,
            llm_tools=[],
            on_token=on_token,
            on_progress=on_progress,
            progress_label="oclaw: finalize",
        )
        step = _persist_assistant_step(
            store=store,
            session_id=session_id,
            turn_uuid=turn_uuid,
            assistant_text=str(getattr(resp, "content", "") or ""),
            reasoning_text=str(getattr(resp, "reasoning_content", "") or ""),
            llm_tool_calls=[],
            thinking_mode_enabled=bool(getattr(model, "thinking_mode_enabled", False)),
        )
        final_text = step.assistant_text

    return TurnRunOutcome(
        final_text=str(final_text or ""),
        tool_traces=tuple(tool_traces),
        handoff_note="",
        turn_uuid=turn_uuid,
    )


def run_direct_loop(**kwargs: Any) -> TurnRunOutcome:
    return run_oclaw_direct_loop(**kwargs)


__all__ = ["run_oclaw_direct_loop", "run_direct_loop", "warm_tool_wire_cache", "tool_wire_freeze_status"]

