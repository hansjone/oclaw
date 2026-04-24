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
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from typing import Any, Callable, Optional

from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.tools.base import ToolRegistry
from oclaw.platform.llm.chat_models import LLMToolCall
from oclaw.tools.tool_validation import validate_tool_arguments
from oclaw.tools.experts.workspace.workspace_base import workspace_path_access_scope

logger = logging.getLogger(__name__)

_TOOL_ERROR_MAP = {
    "tool_timeout_or_failed": "tool_timeout_or_failed",
}
_SQL_REPLAY_COMPACT_TOOL_NAMES = {
    "query_tabular_attachment",
    "run_tabular_sql",
    "analyze_tabular_attachment_full_scan",
}


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
    turn_uuid: str | None = None


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
                with workspace_path_access_scope(
                    ctx.store,
                    ctx.session_id,
                    owner_fallback_session_id=ctx.workspace_owner_session_id,
                    allowlist_tenant_id=ctx.path_policy_tenant_id,
                    allowlist_user_id=ctx.path_policy_user_id,
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
            return normalize_tool_result(result), int((time.perf_counter() - t0) * 1000)
        except Exception as e:
            if ctx.lang.startswith("en"):
                err = {"ok": False, "error_code": "tool_execution_error", "error": f"Tool execution error: {type(e).__name__}: {e}"}
            else:
                err = {"ok": False, "error_code": "tool_execution_error", "error": f"工具执行异常: {type(e).__name__}: {e}"}
            return normalize_tool_result(err), int((time.perf_counter() - t0) * 1000)

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
                from oclaw.orchestration.trace import new_span_id

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

        def _compact_tool_result_for_history(
            *,
            tool_name: str,
            result: dict[str, Any],
            call_index: int,
            threshold: int,
            observed_rows_this_call: int,
            observed_rows_cumulative_in_turn: int,
        ) -> dict[str, Any]:
            out: dict[str, Any] = {
                "ok": bool(result.get("ok")),
                "_history_compacted": True,
                "_history_compact_reason": "repeated_tool_calls_in_turn",
                "tool_name": str(tool_name or ""),
                "call_index_in_turn_for_tool": int(call_index),
                "compact_threshold": int(threshold),
                "_tool_observed_rows_this_call": int(observed_rows_this_call),
                "_tool_observed_rows_cumulative_in_turn": int(observed_rows_cumulative_in_turn),
                "result_keys": sorted(list(result.keys()))[:30],
                "result_bytes": int(_json_blob_size(result)),
                "hint": (
                    "Repeated tool calls in this turn were compacted in chat history to avoid context bloat. "
                    "Full payload remains in tool logs."
                ),
                "audit_note": (
                    "History is compacted by system optimization. If more detail is needed, continue querying "
                    "with the same SQL/tool parameters from this turn."
                ),
            }
            for key in ("error_code", "error", "rows_returned", "limit", "table_id", "engine"):
                if key in result:
                    out[key] = result.get(key)
            for key in ("input_sql", "executed_sql"):
                v = str(result.get(key) or "").strip()
                if v:
                    out[key] = v[:1200]
            guard = result.get("sql_guard")
            if isinstance(guard, dict):
                out["sql_guard"] = {
                    "readonly_enforced": bool(guard.get("readonly_enforced")),
                    "auto_limit_applied": bool(guard.get("auto_limit_applied")),
                    "result_row_cap": int(guard.get("result_row_cap") or 0),
                }
            return out

        _check_stop()
        if not tool_uses:
            return [], {}
        history_summary_threshold = int(tool_history_summary_after_calls())
        turn_tool_name_counts, turn_tool_observed_rows = _load_turn_tool_stats()
        local_turn_tool_name_counts: dict[str, int] = {}
        local_turn_tool_observed_rows: dict[str, int] = {}
        local_turn_written_tool_msgs: dict[str, list[dict[str, Any]]] = {}

        results_by_id: dict[str, tuple[dict[str, Any], int]] = {}
        runnable_tool_uses: list[LLMToolCall] = []
        sig_seen: dict[str, int] = {}
        budget = max(1, min(int(signature_budget or 2), 8))
        for tc in tool_uses:
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
                result=result,
                specialist=ctx.specialist,
                duration_ms=duration_ms,
            )
            tool_log_write_ms = int((time.perf_counter() - t_db1) * 1000)
            # Full payload stays in tool_log; chat history must stay under provider per-message limits.
            t_trunc = time.perf_counter()
            observed_rows_this_call = int(_estimate_observed_rows(result))
            result_for_llm = truncate_tool_result_for_llm_messages(result)
            should_compact_history = tc.name in _SQL_REPLAY_COMPACT_TOOL_NAMES
            if history_summary_threshold > 0 and should_compact_history:
                prior = int(turn_tool_name_counts.get(tc.name, 0))
                current = int(local_turn_tool_name_counts.get(tc.name, 0))
                call_index = prior + current + 1
                prior_rows = int(turn_tool_observed_rows.get(tc.name, 0))
                current_rows = int(local_turn_tool_observed_rows.get(tc.name, 0))
                observed_rows_cumulative_in_turn = prior_rows + current_rows + observed_rows_this_call
                if call_index >= history_summary_threshold:
                    result_for_llm = _compact_tool_result_for_history(
                        tool_name=tc.name,
                        result=result,
                        call_index=call_index,
                        threshold=history_summary_threshold,
                        observed_rows_this_call=observed_rows_this_call,
                        observed_rows_cumulative_in_turn=observed_rows_cumulative_in_turn,
                    )
                local_turn_tool_name_counts[tc.name] = current + 1
                local_turn_tool_observed_rows[tc.name] = current_rows + observed_rows_this_call
            trunc_ms = int((time.perf_counter() - t_trunc) * 1000)
            tool_content = self._json_dumps_safe(result_for_llm)
            t_db2 = time.perf_counter()
            msg_row = ctx.store.add_message(
                session_id=ctx.session_id,
                role="tool",
                content=tool_content,
                tool_calls={"tool_call_id": tc.id, "name": tc.name, "assistant_message_id": assistant_msg_id},
                turn_uuid=ctx.turn_uuid,
                event_type="tool_result",
                event_payload={"tool_name": tc.name, "observed_rows": int(observed_rows_this_call)},
            )
            tool_msg_write_ms = int((time.perf_counter() - t_db2) * 1000)
            tool_messages.append({"role": "tool", "tool_call_id": tc.id, "content": tool_content, "name": tc.name})
            tool_messages_idx = len(tool_messages) - 1
            call_index_for_tool = int(turn_tool_name_counts.get(tc.name, 0)) + int(local_turn_tool_name_counts.get(tc.name, 0))
            local_turn_written_tool_msgs.setdefault(tc.name, []).append(
                {
                    "message_id": int(getattr(msg_row, "id", 0) or 0),
                    "tool_messages_idx": int(tool_messages_idx),
                    "result": dict(result or {}),
                    "observed_rows": int(observed_rows_this_call),
                    "call_index": int(call_index_for_tool),
                    "compacted": bool(isinstance(result_for_llm, dict) and result_for_llm.get("_history_compacted")),
                }
            )
            # When threshold is reached for one SQL tool in the turn, retro-compact earlier same-tool tool messages too.
            if history_summary_threshold > 0 and should_compact_history and call_index_for_tool >= history_summary_threshold:
                running_rows = int(turn_tool_observed_rows.get(tc.name, 0))
                entries = list(local_turn_written_tool_msgs.get(tc.name) or [])
                for ent in entries:
                    running_rows += int(ent.get("observed_rows") or 0)
                    compacted_payload = _compact_tool_result_for_history(
                        tool_name=tc.name,
                        result=dict(ent.get("result") or {}),
                        call_index=int(ent.get("call_index") or 0),
                        threshold=history_summary_threshold,
                        observed_rows_this_call=int(ent.get("observed_rows") or 0),
                        observed_rows_cumulative_in_turn=int(running_rows),
                    )
                    compacted_content = self._json_dumps_safe(compacted_payload)
                    if not bool(ent.get("compacted")):
                        try:
                            ctx.store.update_message_content(
                                session_id=ctx.session_id,
                                message_id=int(ent.get("message_id") or 0),
                                content=compacted_content,
                                event_payload={"tool_name": tc.name, "observed_rows": int(ent.get("observed_rows") or 0)},
                            )
                        except Exception:
                            pass
                        ent["compacted"] = True
                    ti = int(ent.get("tool_messages_idx") or -1)
                    if 0 <= ti < len(tool_messages):
                        tool_messages[ti]["content"] = compacted_content
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

__all__ = [
    "ToolExecutionConfig",
    "ToolExecutionContext",
    "ToolExecutor",
    "normalize_tool_result",
    "partition_tool_use_batches",
    "tool_llm_message_max_chars",
    "truncate_tool_result_for_llm_messages",
]
