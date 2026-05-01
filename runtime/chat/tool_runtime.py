from __future__ import annotations

"""Agent 工具执行模块。

本模块把“工具执行（校验/并发/落库/回写）”从 `Agent.run_turn` 中下沉出来，
以便被单 Agent 与编排器（manager/specialist）复用。
"""

import json
import logging
import time
import os
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from typing import Any, Callable, Optional

from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.runtime.tools.base import ToolRegistry
from oclaw.platform.llm.chat_models import LLMToolCall
from oclaw.runtime.tools.tool_validation import validate_tool_arguments
from oclaw.runtime.chat.media_redact import ingest_embedded_image_blobs_as_refs
from oclaw.runtime.tools.path_guard import (
    workspace_path_access_scope,
    workspace_write_namespace_scope,
)
from oclaw.runtime.chat.tool_invocation_context import tool_workspace_lane_scope

logger = logging.getLogger(__name__)
_tool_exec_log = logging.getLogger("oclaw.tool_exec")

_TOOL_ERROR_MAP = {
    "tool_timeout_or_failed": "tool_timeout_or_failed",
}
_SQL_REPLAY_COMPACT_TOOL_NAMES = {
    "query_tabular_attachment",
    "run_tabular_sql",
    "analyze_tabular_attachment_full_scan",
}
_TABULAR_QUERY_TOOL_NAMES = {
    "query_tabular_attachment",
    "analyze_tabular_attachment_full_scan",
}
_TEXT_QUERY_TOOL_NAMES = {
    "query_text_attachment",
}
_IMAGE_QUERY_TOOL_NAMES = {
    "query_image_attachment",
}
_VIDEO_QUERY_TOOL_NAMES = {
    "query_video_attachment",
}


def _attachments_from_tool_result(result: Any) -> list[dict[str, Any]]:
    """Extract renderable attachments from tool results for durable chat history."""
    if not isinstance(result, dict):
        return []
    out: list[dict[str, Any]] = []
    aid = str(result.get("attachment_id") or "").strip()
    root_mime = str(result.get("mime") or "").strip()
    if aid:
        ref_type = _ref_type_for_mime(root_mime)
        out.append(
            {
                "type": ref_type,
                "attachment_id": aid,
                "name": str(result.get("name") or "generated-image"),
                "mime": root_mime or "application/octet-stream",
                "bytes": result.get("bytes"),
                "width": result.get("width"),
                "height": result.get("height"),
            }
        )
    refs = result.get("attachments")
    if isinstance(refs, list):
        for r in refs:
            if not isinstance(r, dict):
                continue
            p_uri = str(r.get("pointer_uri") or "").strip()
            if p_uri:
                out.append(
                    {
                        "type": "relay_pointer",
                        "pointer_uri": p_uri,
                        "rel_path": str(r.get("rel_path") or ""),
                        "mime": str(r.get("mime_type") or r.get("mime") or ""),
                        "bytes": r.get("bytes"),
                        "sha256": str(r.get("sha256") or ""),
                        "name": str(r.get("name") or ""),
                    }
                )
                continue
            r_aid = str(r.get("attachment_id") or "").strip()
            if r_aid:
                r_typ = str(r.get("type") or "").strip().lower()
                r_mime = str(r.get("mime_type") or r.get("mime") or "").strip()
                if r_typ not in {"image_ref", "video_ref", "text_ref", "binary_ref"}:
                    r_typ = _ref_type_for_mime(r_mime)
                out.append(
                    {
                        "type": r_typ,
                        "attachment_id": r_aid,
                        "name": str(r.get("name") or "generated-image"),
                        "mime": r_mime or "application/octet-stream",
                        "bytes": r.get("bytes"),
                        "width": r.get("width"),
                        "height": r.get("height"),
                    }
                )
    inner = result.get("result")
    if isinstance(inner, dict):
        content = inner.get("content")
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                typ = str(item.get("type") or "").strip().lower()
                if typ in {"image_ref", "video_ref", "text_ref", "binary_ref"}:
                    a_id = str(item.get("attachment_id") or "").strip()
                    if a_id:
                        out.append(
                            {
                                "type": typ,
                                "attachment_id": a_id,
                                "mime": str(item.get("mime_type") or item.get("mime") or "application/octet-stream"),
                                "name": str(item.get("name") or "tool-attachment"),
                                "bytes": item.get("bytes"),
                                "width": item.get("width"),
                                "height": item.get("height"),
                            }
                        )
                elif typ == "image_url":
                    src = str(item.get("url") or item.get("image_url") or "").strip()
                    if src:
                        out.append({"type": "image_url", "url": src, "name": str(item.get("name") or "tool-image")})
    uniq: list[dict[str, Any]] = []
    seen: set[str] = set()
    for a in out:
        k = str(
            a.get("attachment_id")
            or a.get("pointer_uri")
            or a.get("url")
            or ""
        ).strip()
        if not k or k in seen:
            continue
        seen.add(k)
        uniq.append(a)
    return uniq


def _message_has_tabular_ref(raw_attachments: Any) -> bool:
    if raw_attachments is None:
        return False
    obj = raw_attachments
    if isinstance(raw_attachments, str):
        s = str(raw_attachments or "").strip()
        if not s:
            return False
        try:
            obj = json.loads(s)
        except Exception:
            return False
    if isinstance(obj, dict):
        items = [obj]
    elif isinstance(obj, list):
        items = obj
    else:
        return False
    for it in items:
        if not isinstance(it, dict):
            continue
        if str(it.get("type") or "").strip().lower() == "tabular_ref":
            return True
    return False


def _message_has_text_ref(raw_attachments: Any) -> bool:
    if raw_attachments is None:
        return False
    obj = raw_attachments
    if isinstance(raw_attachments, str):
        s = str(raw_attachments or "").strip()
        if not s:
            return False
        try:
            obj = json.loads(s)
        except Exception:
            return False
    if isinstance(obj, dict):
        items = [obj]
    elif isinstance(obj, list):
        items = obj
    else:
        return False
    for it in items:
        if not isinstance(it, dict):
            continue
        if str(it.get("type") or "").strip().lower() == "text_ref":
            return True
    return False


def _message_has_image_ref(raw_attachments: Any) -> bool:
    if raw_attachments is None:
        return False
    obj = raw_attachments
    if isinstance(raw_attachments, str):
        s = str(raw_attachments or "").strip()
        if not s:
            return False
        try:
            obj = json.loads(s)
        except Exception:
            return False
    if isinstance(obj, dict):
        items = [obj]
    elif isinstance(obj, list):
        items = obj
    else:
        return False
    for it in items:
        if not isinstance(it, dict):
            continue
        t = str(it.get("type") or "").strip().lower()
        if t in {"image_ref", "image", "input_image"}:
            return True
    return False


def _message_has_video_ref(raw_attachments: Any) -> bool:
    if raw_attachments is None:
        return False
    obj = raw_attachments
    if isinstance(raw_attachments, str):
        s = str(raw_attachments or "").strip()
        if not s:
            return False
        try:
            obj = json.loads(s)
        except Exception:
            return False
    if isinstance(obj, dict):
        items = [obj]
    elif isinstance(obj, list):
        items = obj
    else:
        return False
    for it in items:
        if not isinstance(it, dict):
            continue
        t = str(it.get("type") or "").strip().lower()
        if t == "video_ref":
            return True
    return False


def _session_has_tabular_ref(store: Any, session_id: str, *, limit: int = 300) -> bool:
    try:
        rows = store.get_messages(session_id=session_id, limit=max(1, int(limit)))
    except Exception:
        return False
    for m in rows or []:
        if _message_has_tabular_ref(getattr(m, "attachments", None)):
            return True
    return False


def _session_has_text_ref(store: Any, session_id: str, *, limit: int = 300) -> bool:
    try:
        rows = store.get_messages(session_id=session_id, limit=max(1, int(limit)))
    except Exception:
        return False
    for m in rows or []:
        if _message_has_text_ref(getattr(m, "attachments", None)):
            return True
    return False


def _session_has_image_ref(store: Any, session_id: str, *, limit: int = 300) -> bool:
    try:
        rows = store.get_messages(session_id=session_id, limit=max(1, int(limit)))
    except Exception:
        return False
    for m in rows or []:
        if _message_has_image_ref(getattr(m, "attachments", None)):
            return True
    return False


def _session_has_video_ref(store: Any, session_id: str, *, limit: int = 300) -> bool:
    try:
        rows = store.get_messages(session_id=session_id, limit=max(1, int(limit)))
    except Exception:
        return False
    for m in rows or []:
        if _message_has_video_ref(getattr(m, "attachments", None)):
            return True
    return False


def normalize_tool_result(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        out = dict(result)
        if "ok" in out:
            out["ok"] = bool(out.get("ok"))
        else:
            # Backward compatibility: many lightweight tools return payload-only dicts.
            # Treat those as success unless they explicitly carry error semantics.
            has_error = bool(str(out.get("error_code") or "").strip() or str(out.get("error") or "").strip())
            out["ok"] = not has_error
    else:
        out = {"ok": False, "error": "tool_result_not_dict", "data": result}
    if not out["ok"]:
        raw_ec = str(out.get("error_code") or "").strip()
        raw_err = str(out.get("error") or "").strip()
        if not raw_ec:
            out["error_code"] = _TOOL_ERROR_MAP.get(raw_err, "tool_failed")
    return out


def tool_llm_message_max_chars() -> int:
    raw = str(os.getenv("AIA_TOOL_LLM_MESSAGE_MAX_CHARS") or "").strip()
    if raw.isdigit():
        n = int(raw)
        if n == 0:
            return 0
        return max(4096, min(n, 500_000))
    return 0


def tool_history_summary_after_calls() -> int:
    raw = str(os.getenv("AIA_TOOL_HISTORY_SUMMARY_AFTER_CALLS") or "").strip()
    if raw.isdigit():
        return max(0, min(int(raw), 200))
    # Default: when the same tool is called >= 3 times in one turn, keep history compact.
    return 3


def _json_blob_size(obj: Any) -> int:
    try:
        return len(json.dumps(obj, ensure_ascii=False, default=str))
    except Exception:
        return len(repr(obj))


def _estimate_observed_rows(result: dict[str, Any]) -> int:
    if not isinstance(result, dict):
        return 0
    try:
        rr = result.get("rows_returned")
        if isinstance(rr, (int, float)):
            return max(0, int(rr))
    except Exception:
        pass
    rows = result.get("rows")
    if isinstance(rows, list):
        return max(0, len(rows))
    nested = result.get("result")
    if isinstance(nested, dict):
        nrows = nested.get("rows")
        if isinstance(nrows, list):
            return max(0, len(nrows))
    return 0


def _deep_truncate_for_llm(obj: Any, *, max_str: int, max_list: int) -> Any:
    if isinstance(obj, dict):
        return {str(k): _deep_truncate_for_llm(v, max_str=max_str, max_list=max_list) for k, v in obj.items()}
    if isinstance(obj, list):
        items = obj
        omitted = 0
        if len(items) > max_list:
            omitted = len(items) - max_list
            items = items[:max_list]
        out: list[Any] = [_deep_truncate_for_llm(x, max_str=max_str, max_list=max_list) for x in items]
        if omitted:
            out.append(f"…({omitted} more list items omitted)")
        return out
    if isinstance(obj, str) and len(obj) > max_str:
        return obj[:max_str] + "\n...<truncated>"
    return obj


def partition_tool_use_batches(
    tool_uses: list[LLMToolCall],
    registry: ToolRegistry,
) -> list[list[LLMToolCall]]:
    """Split tool uses into ordered batches (cc-mini ``Engine.submit`` scheduling).

    Consecutive tools whose ``ToolSpec.is_read_only()`` is true are merged into one batch
    and may run in parallel when the batch length is greater than one. Any other tool
    starts a new batch (typically length 1), which runs sequentially relative to other
    batches and uses a single worker within the batch.
    """
    batches: list[tuple[bool, list[LLMToolCall]]] = []
    for tc in tool_uses:
        spec = registry.get(tc.name)
        is_concurrent = bool(spec and spec.is_read_only())
        if batches and batches[-1][0] == is_concurrent and is_concurrent:
            batches[-1][1].append(tc)
        else:
            batches.append((is_concurrent, [tc]))
    return [chunk for _, chunk in batches]


def truncate_tool_result_for_llm_messages(result: dict[str, Any], *, max_chars: int | None = None) -> dict[str, Any]:
    """Return a copy safe to put in ``role=tool`` ``content`` so the next LLM request stays under provider limits."""
    cap = tool_llm_message_max_chars() if max_chars is None else max(0, min(int(max_chars), 500_000))
    if cap == 0:
        return result if isinstance(result, dict) else {"ok": False, "error": "tool_result_not_dict", "data": result}
    if not isinstance(result, dict):
        return {"ok": False, "error": "tool_result_not_dict", "payload_type": type(result).__name__}
    if _json_blob_size(result) <= cap:
        return result
    orig_files_n = len(result["files"]) if isinstance(result.get("files"), list) else 0
    pairs = (
        (12_000, 800),
        (8000, 500),
        (4000, 300),
        (2000, 200),
        (1200, 120),
        (800, 80),
        (500, 50),
        (400, 40),
    )
    for max_str, max_list in pairs:
        slim = _deep_truncate_for_llm(result, max_str=max_str, max_list=max_list)
        if not isinstance(slim, dict):
            slim = {"ok": bool(result.get("ok")), "payload": slim}
        if _json_blob_size(slim) <= cap:
            slim = dict(slim)
            slim["_truncated_for_llm"] = True
            if orig_files_n and isinstance(slim.get("files"), list):
                kept = sum(1 for x in slim["files"] if isinstance(x, str))
                if kept < orig_files_n:
                    slim["files_total"] = orig_files_n
                    slim["files_omitted"] = orig_files_n - kept
            return slim
    return {
        "ok": bool(result.get("ok")),
        "_truncated_for_llm": True,
        "hint": (
            "Tool output exceeded model message size limits. "
            "Narrow the glob, lower max_results, or list a subdirectory. / "
            "工具输出超过模型单条消息限制，请缩小列举范围或降低 max_results。"
        ),
    }


@dataclass(frozen=True)
class ToolExecutionConfig:
    max_workers: int = 8


@dataclass(frozen=True)
class ToolExecutionContext:
    store: SqliteStore
    tools: ToolRegistry
    session_id: str
    lang: str = "zh"
    user_text: str = ""
    specialist: str = ""
    task_kind: str = ""
    policy_engine: Any | None = None
    trace_id: str | None = None
    parent_span_id: str | None = None
    #: When ``session_id`` is a specialist temp chat row (no ``ui_session_owner``), use the user's UI session for ``extra_roots`` / allowlist.
    workspace_owner_session_id: str | None = None
    #: If ``get_ui_session_owner`` fails, load allowlist for this (tenant, user) from the HTTP/gateway request (``metadata``).
    path_policy_tenant_id: str | None = None
    path_policy_user_id: str | None = None
    workspace_dir: str | None = None
    turn_uuid: str | None = None
    #: Binding role for private ``skill_auto_install`` paths (``_workspace/<role>/``, sibling of ``public/``).
    workspace_lane_role: str | None = None


class ToolExecutor:
    """执行一组 tool uses，并把结果写回 store。"""

    def __init__(self, *, config: ToolExecutionConfig | None = None):
        self.config = config or ToolExecutionConfig()

    def _execute_tool(self, ctx: ToolExecutionContext, tc: LLMToolCall) -> tuple[dict[str, Any], int]:
        t0 = time.perf_counter()

        tool = ctx.tools.get(tc.name)
        if not tool:
            msg = f"Unregistered tool: {tc.name}" if ctx.lang.startswith("en") else f"未注册的工具: {tc.name}"
            return {"ok": False, "error_code": "tool_not_registered", "error": msg}, int((time.perf_counter() - t0) * 1000)

        ok, v_err = validate_tool_arguments(tool.parameters, tc.arguments)
        if not ok:
            msg = f"Invalid arguments: {v_err}" if ctx.lang.startswith("en") else f"参数不合法: {v_err}"
            return {"ok": False, "error_code": "tool_invalid_arguments", "error": msg}, int((time.perf_counter() - t0) * 1000)

        try:
            timeout_s = getattr(tool, "timeout_s", None)
            # Default timeout for plugin tools if not specified.
            if timeout_s is None and "plugin" in getattr(tool, "tags", frozenset()):
                timeout_s = 30.0

            def _call() -> Any:
                ws_ns = ""
                raw_ws = str(ctx.workspace_dir or "").strip()
                if raw_ws:
                    try:
                        wp = Path(raw_ws)
                        ws_ns = str(wp.name or wp.stem or "").strip()
                    except Exception:
                        ws_ns = ""
                with workspace_path_access_scope(
                    ctx.store,
                    ctx.session_id,
                    owner_fallback_session_id=ctx.workspace_owner_session_id,
                    allowlist_tenant_id=ctx.path_policy_tenant_id,
                    allowlist_user_id=ctx.path_policy_user_id,
                ), workspace_write_namespace_scope(ws_ns), tool_workspace_lane_scope(
                    workspace_owner_session_id=ctx.workspace_owner_session_id,
                    session_id=ctx.session_id,
                    workspace_lane_role=ctx.workspace_lane_role,
                ):
                    return tool.handler(tc.arguments)

            if isinstance(timeout_s, (int, float)) and float(timeout_s) > 0:
                ex = ThreadPoolExecutor(max_workers=1)
                fut = ex.submit(_call)
                try:
                    result = fut.result(timeout=float(timeout_s))
                except FuturesTimeoutError as e:
                    try:
                        fut.cancel()
                    except Exception:
                        pass
                    try:
                        ex.shutdown(wait=False, cancel_futures=True)
                    except Exception:
                        ex.shutdown(wait=False)
                    return {"ok": False, "error_code": "tool_timeout_or_failed", "error": "tool_timeout_or_failed", "detail": f"{type(e).__name__}: {e}"}, int(
                        (time.perf_counter() - t0) * 1000
                    )
                except Exception as e:
                    try:
                        ex.shutdown(wait=False, cancel_futures=True)
                    except Exception:
                        ex.shutdown(wait=False)
                    return {"ok": False, "error_code": "tool_timeout_or_failed", "error": "tool_timeout_or_failed", "detail": f"{type(e).__name__}: {e}"}, int(
                        (time.perf_counter() - t0) * 1000
                    )
                else:
                    try:
                        ex.shutdown(wait=False, cancel_futures=True)
                    except Exception:
                        ex.shutdown(wait=False)
            else:
                result = _call()
            out = normalize_tool_result(result)
            dur_ms = int((time.perf_counter() - t0) * 1000)
            try:
                _tool_exec_log.info(
                    "tool_exec name=%s ok=%s dur_ms=%s session=%s specialist=%s tool_call_id=%s error_code=%s",
                    str(tc.name or ""),
                    str(bool(out.get("ok"))),
                    str(dur_ms),
                    str(ctx.session_id or ""),
                    str(ctx.specialist or ""),
                    str(getattr(tc, "id", "") or ""),
                    str(out.get("error_code") or ""),
                )
            except Exception:
                pass
            return out, dur_ms
        except Exception as e:
            if ctx.lang.startswith("en"):
                err = {"ok": False, "error_code": "tool_execution_error", "error": f"Tool execution error: {type(e).__name__}: {e}"}
            else:
                err = {"ok": False, "error_code": "tool_execution_error", "error": f"工具执行异常: {type(e).__name__}: {e}"}
            out = normalize_tool_result(err)
            dur_ms = int((time.perf_counter() - t0) * 1000)
            try:
                _tool_exec_log.info(
                    "tool_exec name=%s ok=%s dur_ms=%s session=%s specialist=%s tool_call_id=%s error_code=%s",
                    str(tc.name or ""),
                    str(bool(out.get("ok"))),
                    str(dur_ms),
                    str(ctx.session_id or ""),
                    str(ctx.specialist or ""),
                    str(getattr(tc, "id", "") or ""),
                    str(out.get("error_code") or ""),
                )
            except Exception:
                pass
            return out, dur_ms

    @staticmethod
    def _json_dumps_safe(obj: Any) -> str:
        try:
            return json.dumps(obj, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            return json.dumps({"ok": False, "error": "tool result is not JSON-serializable"}, ensure_ascii=False)

    def execute_tool_uses(
        self,
        *,
        ctx: ToolExecutionContext,
        assistant_msg_id: int,
        tool_uses: list[LLMToolCall],
        on_tool_ui: Optional[Callable[[str, dict[str, Any]], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
        signature_budget: int = 2,
    ) -> tuple[list[dict[str, Any]], dict[str, tuple[dict[str, Any], int]]]:
        """执行并回写 tool messages。

        Returns:
          - tool_messages: 用于写入对话 history 的 `role=tool` 消息 payload 列表（与 tool_uses 顺序一致）
          - results_by_id: tool_call_id -> (result_dict, duration_ms)
        """

        def _check_stop() -> None:
            if should_stop and should_stop():
                raise RuntimeError("generation interrupted by user")

        def _trace(event_type: str, payload: dict[str, Any]) -> None:
            if not ctx.trace_id:
                return
            try:
                from oclaw.runtime.orchestration.trace import new_span_id

                ctx.store.add_trace_event(
                    session_id=ctx.session_id,
                    trace_id=str(ctx.trace_id),
                    span_id=new_span_id(),
                    parent_span_id=ctx.parent_span_id,
                    event_type=str(event_type),
                    payload=dict(payload or {}),
                )
            except Exception:
                pass

        def _load_turn_tool_stats() -> tuple[dict[str, int], dict[str, int]]:
            counts: dict[str, int] = {}
            observed_rows: dict[str, int] = {}
            if not str(ctx.turn_uuid or "").strip():
                return counts, observed_rows
            try:
                rows = ctx.store.get_messages(session_id=ctx.session_id, limit=500)
            except Exception:
                return counts, observed_rows
            for m in rows or []:
                if str(getattr(m, "role", "") or "") != "tool":
                    continue
                if str(getattr(m, "turn_uuid", "") or "") != str(ctx.turn_uuid or ""):
                    continue
                raw_tc = getattr(m, "tool_calls", None)
                name = ""
                if isinstance(raw_tc, str):
                    try:
                        parsed = json.loads(raw_tc)
                    except Exception:
                        parsed = None
                else:
                    parsed = raw_tc
                if isinstance(parsed, dict):
                    name = str(parsed.get("name") or "").strip()
                if not name:
                    continue
                counts[name] = int(counts.get(name, 0)) + 1
                try:
                    raw_content = str(getattr(m, "content", "") or "")
                    payload = json.loads(raw_content) if raw_content else {}
                except Exception:
                    payload = {}
                if isinstance(payload, dict):
                    observed_rows[name] = int(observed_rows.get(name, 0)) + int(
                        _estimate_observed_rows(payload)
                        or payload.get("_tool_observed_rows_this_call")
                        or 0
                    )
            return counts, observed_rows

        _check_stop()
        if not tool_uses:
            return [], {}
        turn_tool_name_counts, turn_tool_observed_rows = _load_turn_tool_stats()
        local_turn_tool_name_counts: dict[str, int] = {}
        local_turn_tool_observed_rows: dict[str, int] = {}
        planned_sql_name_counts: dict[str, int] = {}
        for tc in tool_uses:
            name = str(tc.name or "")
            if name in _SQL_REPLAY_COMPACT_TOOL_NAMES:
                planned_sql_name_counts[name] = int(planned_sql_name_counts.get(name, 0)) + 1
        compact_sql_names = {
            name for name, cnt in planned_sql_name_counts.items() if int(cnt) >= int(tool_history_summary_after_calls())
        }
        has_tabular_ref_in_session = _session_has_tabular_ref(ctx.store, ctx.session_id)
        has_text_ref_in_session = _session_has_text_ref(ctx.store, ctx.session_id)
        has_image_ref_in_session = _session_has_image_ref(ctx.store, ctx.session_id)
        has_video_ref_in_session = _session_has_video_ref(ctx.store, ctx.session_id)

        results_by_id: dict[str, tuple[dict[str, Any], int]] = {}
        runnable_tool_uses: list[LLMToolCall] = []
        dedupe_alias_to_source: dict[str, str] = {}
        first_tool_call_id_by_signature: dict[str, str] = {}
        sig_seen: dict[str, int] = {}
        budget = max(1, min(int(signature_budget or 2), 8))
        for tc in tool_uses:
            if tc.name in _TABULAR_QUERY_TOOL_NAMES and not has_tabular_ref_in_session:
                results_by_id[tc.id] = (
                    {
                        "ok": False,
                        "error_code": "tabular_ref_missing",
                        "error": "tabular_ref_missing",
                        "hint": "No tabular_ref attachment found in this session. Query tools require table_id from tabular_ref.",
                    },
                    0,
                )
                _trace(
                    "tabular_query_guard",
                    {
                        "tool_name": tc.name,
                        "blocked": True,
                        "reason": "tabular_ref_missing",
                    },
                )
                continue
            if tc.name in _TEXT_QUERY_TOOL_NAMES and not has_text_ref_in_session:
                results_by_id[tc.id] = (
                    {
                        "ok": False,
                        "error_code": "text_ref_missing",
                        "error": "text_ref_missing",
                        "hint": "No text_ref attachment found in this session. Query tools require text_id from text_ref.",
                    },
                    0,
                )
                _trace(
                    "text_query_guard",
                    {
                        "tool_name": tc.name,
                        "blocked": True,
                        "reason": "text_ref_missing",
                    },
                )
                continue
            if tc.name in _IMAGE_QUERY_TOOL_NAMES and not has_image_ref_in_session:
                results_by_id[tc.id] = (
                    {
                        "ok": False,
                        "error_code": "image_ref_missing",
                        "error": "image_ref_missing",
                        "hint": "No image_ref attachment found in this session. Query tools require attachment_id from image_ref.",
                    },
                    0,
                )
                _trace(
                    "image_query_guard",
                    {
                        "tool_name": tc.name,
                        "blocked": True,
                        "reason": "image_ref_missing",
                    },
                )
                continue
            if tc.name in _VIDEO_QUERY_TOOL_NAMES and not has_video_ref_in_session:
                results_by_id[tc.id] = (
                    {
                        "ok": False,
                        "error_code": "video_ref_missing",
                        "error": "video_ref_missing",
                        "hint": "No video_ref attachment found in this session. Query tools require attachment_id from video_ref.",
                    },
                    0,
                )
                _trace(
                    "video_query_guard",
                    {
                        "tool_name": tc.name,
                        "blocked": True,
                        "reason": "video_ref_missing",
                    },
                )
                continue
            sig = f"{tc.name}:{self._json_dumps_safe(dict(tc.arguments or {}))}"
            count = int(sig_seen.get(sig, 0))
            if count >= budget:
                results_by_id[tc.id] = (
                    {
                        "ok": False,
                        "error_code": "tool_loop_guard",
                        "error": f"tool loop guard triggered for signature: {tc.name}",
                    },
                    0,
                )
                _trace(
                    "tool_loop_guard",
                    {
                        "tool_name": tc.name,
                        "signature": sig[:300],
                        "budget": budget,
                    },
                )
                continue
            sig_seen[sig] = count + 1
            source_tool_call_id = str(first_tool_call_id_by_signature.get(sig) or "").strip()
            if source_tool_call_id:
                dedupe_alias_to_source[str(tc.id or "")] = source_tool_call_id
                _trace(
                    "tool_cache_hit_same_round",
                    {
                        "tool_name": tc.name,
                        "tool_call_id": str(tc.id or ""),
                        "source_tool_call_id": source_tool_call_id,
                    },
                )
                continue
            first_tool_call_id_by_signature[sig] = str(tc.id or "")
            runnable_tool_uses.append(tc)

        for batch in partition_tool_use_batches(runnable_tool_uses, ctx.tools):
            _check_stop()
            _trace(
                "tool_batch_started",
                {
                    "batch_size": len(batch),
                    "tool_names": [str(getattr(x, "name", "") or "") for x in batch],
                },
            )
            if len(batch) > 1:
                workers = min(int(self.config.max_workers), len(batch))
                with ThreadPoolExecutor(max_workers=workers) as ex:
                    fut_to_tc = {ex.submit(self._execute_tool, ctx, tc): tc for tc in batch}
                    for fut in as_completed(fut_to_tc):
                        tc = fut_to_tc[fut]
                        results_by_id[tc.id] = fut.result()
            else:
                for tc in batch:
                    results_by_id[tc.id] = self._execute_tool(ctx, tc)
            _trace(
                "tool_batch_finished",
                {
                    "batch_size": len(batch),
                    "tool_names": [str(getattr(x, "name", "") or "") for x in batch],
                },
            )

        for tool_call_id, source_tool_call_id in dedupe_alias_to_source.items():
            if source_tool_call_id in results_by_id:
                results_by_id[tool_call_id] = results_by_id[source_tool_call_id]

        tool_messages: list[dict[str, Any]] = []
        for tc in tool_uses:
            _check_stop()
            _trace(
                "tool_called",
                {
                    "tool_name": tc.name,
                    "arguments": tc.arguments,
                    "arguments_bytes": _json_blob_size(tc.arguments),
                },
            )
            result, duration_ms = results_by_id[tc.id]
            result = normalize_tool_result(result)
            persisted_result, ingested_refs = ingest_embedded_image_blobs_as_refs(
                result,
                filename_prefix=f"{str(tc.name or 'tool')}-{str(tc.id or '')}",
            )
            logger.info(
                "tool_runtime tool session=%s name=%s duration_ms=%d ok=%s",
                ctx.session_id[:12],
                tc.name,
                duration_ms,
                result.get("ok") if isinstance(result, dict) else None,
            )
            t_db1 = time.perf_counter()
            ctx.store.add_tool_log(
                session_id=ctx.session_id,
                tool_name=tc.name,
                args=tc.arguments,
                result=persisted_result,
                specialist=ctx.specialist,
                duration_ms=duration_ms,
            )
            tool_log_write_ms = int((time.perf_counter() - t_db1) * 1000)
            # Keep full payload during the active turn. History compaction is deferred
            # until the turn finishes, so current-round model context remains lossless.
            t_trunc = time.perf_counter()
            observed_rows_this_call = int(_estimate_observed_rows(result))
            result_for_llm = dict(persisted_result or {})
            if tc.name in _SQL_REPLAY_COMPACT_TOOL_NAMES:
                current = int(local_turn_tool_name_counts.get(tc.name, 0))
                current_rows = int(local_turn_tool_observed_rows.get(tc.name, 0))
                local_turn_tool_name_counts[tc.name] = current + 1
                local_turn_tool_observed_rows[tc.name] = current_rows + observed_rows_this_call
                if tc.name in compact_sql_names:
                    cumulative_rows = int(turn_tool_observed_rows.get(tc.name, 0)) + int(local_turn_tool_observed_rows.get(tc.name, 0))
                    result_for_llm["_history_compacted"] = True
                    result_for_llm["_history_compact_reason"] = "repeated_tool_calls_in_turn"
                    result_for_llm["_tool_observed_rows_this_call"] = int(observed_rows_this_call)
                    result_for_llm["_tool_observed_rows_cumulative_in_turn"] = int(cumulative_rows)
                    result_for_llm["audit_note"] = "Result compacted for history replay safety."
            trunc_ms = int((time.perf_counter() - t_trunc) * 1000)
            tool_content = self._json_dumps_safe(result_for_llm)
            t_db2 = time.perf_counter()
            msg_row = ctx.store.add_message(
                session_id=ctx.session_id,
                role="tool",
                content=tool_content,
                tool_calls={"tool_call_id": tc.id, "name": tc.name, "assistant_message_id": assistant_msg_id},
                attachments=(_merge_attachments(_attachments_from_tool_result(persisted_result), ingested_refs) or None),
                turn_uuid=ctx.turn_uuid,
                event_type="tool_result",
                event_payload={"tool_name": tc.name, "observed_rows": int(observed_rows_this_call)},
            )
            try:
                owner = ctx.store.get_ui_session_owner(session_id=ctx.session_id) or {}
                tid = str(owner.get("tenant_id") or "").strip()
                uid = str(owner.get("user_id") or "").strip()
                atts = msg_row.attachments
                if tid and uid and atts:
                    raw = json.loads(atts) if isinstance(atts, str) else atts
                    items = raw if isinstance(raw, list) else ([raw] if isinstance(raw, dict) else [])
                    for a in items:
                        if not isinstance(a, dict):
                            continue
                        aid = str(a.get("attachment_id") or "").strip().lower()
                        if aid:
                            ctx.store.link_attachment_acl(
                                tenant_id=tid,
                                user_id=uid,
                                session_id=ctx.session_id,
                                attachment_id=aid,
                                source=f"tool:{str(tc.name or '')}",
                            )
            except Exception:
                pass
            tool_msg_write_ms = int((time.perf_counter() - t_db2) * 1000)
            tool_messages.append({"role": "tool", "tool_call_id": tc.id, "content": tool_content, "name": tc.name})
            _trace(
                "tool_result",
                {
                    "tool_name": tc.name,
                    "duration_ms": duration_ms,
                    "ok": bool(result.get("ok")) if isinstance(result, dict) else None,
                    "error_code": str(result.get("error_code") or "") if isinstance(result, dict) else "",
                    "result_bytes": _json_blob_size(result),
                    "result_for_llm_bytes": len(tool_content or ""),
                    "tool_log_write_ms": tool_log_write_ms,
                    "tool_message_write_ms": tool_msg_write_ms,
                    "truncate_ms": trunc_ms,
                    "active_threads": int(threading.active_count()),
                },
            )
            if on_tool_ui:
                truncated_for_llm = bool(
                    isinstance(result_for_llm, dict) and result_for_llm.get("_truncated_for_llm")
                )
                payload = {
                    "name": tc.name,
                    "result": result,
                    "llm_wire": {
                        "truncated_for_llm": truncated_for_llm,
                        "max_chars": int(tool_llm_message_max_chars()),
                        "result_bytes": int(_json_blob_size(result)),
                        "result_for_llm_bytes": int(len(tool_content or "")),
                        "truncate_ms": int(trunc_ms),
                    },
                }
                on_tool_ui("tool_use_result", payload)
        return tool_messages, results_by_id


def compact_turn_tool_messages_for_storage(
    *,
    store: Any,
    session_id: str,
    turn_uuid: str | None,
) -> dict[str, int]:
    """Compact persisted tool messages after turn completion.

    This intentionally runs *after* the active turn so current-round model
    context is not affected by truncation/compaction.
    """
    tid = str(turn_uuid or "").strip()
    if not tid:
        return {"scanned": 0, "updated": 0}
    try:
        rows = store.get_messages(session_id=session_id, limit=800)
    except Exception:
        return {"scanned": 0, "updated": 0}
    scanned = 0
    updated = 0
    for m in rows or []:
        if str(getattr(m, "role", "") or "") != "tool":
            continue
        if str(getattr(m, "turn_uuid", "") or "") != tid:
            continue
        scanned += 1
        raw = str(getattr(m, "content", "") or "")
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        compacted = truncate_tool_result_for_llm_messages(obj)
        if compacted == obj:
            continue
        try:
            store.update_message_content(
                session_id=session_id,
                message_id=int(getattr(m, "id", 0) or 0),
                content=json.dumps(compacted, ensure_ascii=False, default=str),
                event_payload=getattr(m, "event_payload", None),
            )
            updated += 1
        except Exception:
            continue
    return {"scanned": int(scanned), "updated": int(updated)}

__all__ = [
    "ToolExecutionConfig",
    "ToolExecutionContext",
    "ToolExecutor",
    "normalize_tool_result",
    "partition_tool_use_batches",
    "tool_llm_message_max_chars",
    "truncate_tool_result_for_llm_messages",
    "compact_turn_tool_messages_for_storage",
]


def _merge_attachments(*parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for part in parts:
        for a in part or []:
            if not isinstance(a, dict):
                continue
            k = str(a.get("attachment_id") or a.get("pointer_uri") or a.get("url") or "").strip()
            if not k or k in seen:
                continue
            seen.add(k)
            out.append(a)
    return out


def _ref_type_for_mime(mime: str) -> str:
    m = str(mime or "").strip().lower()
    if m.startswith("image/"):
        return "image_ref"
    if m.startswith("video/"):
        return "video_ref"
    if m.startswith("text/"):
        return "text_ref"
    return "binary_ref"
