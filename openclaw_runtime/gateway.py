from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from oclaw.agents.factory import build_ephemeral_executor
from oclaw.infrastructure.agent_context import build_role_system_context
from oclaw.openclaw_runtime.hooks_runtime import (
    get_active_hooks_config,
    initialize_hooks_runtime,
    trigger_hook_event,
)
from oclaw.openclaw_runtime.relay_pointer import summarize_relay_ttl
from oclaw.openclaw_runtime.skills import build_skill_manifest
from oclaw.openclaw_runtime.types import (
    OpenClawSessionContext,
    StandardMessage,
    normalize_interaction_mode,
    normalize_requested_specialist,
)
from oclaw.platform.config.paths import PROJECT_ROOT
from oclaw.prompts import render_prompt
from oclaw.prompts.loader import render_openclaw_prompt

from oclaw.openclaw_runtime.agent_core_run import AgentCoreRunInput, run_agent_core
from oclaw.openclaw_runtime.command_parser import parse_internal_command
from oclaw.openclaw_runtime.memory_stage import build_memory_context
from oclaw.openclaw_runtime.router import decide_route
from oclaw.openclaw_runtime.worker import ensure_worker_started
from oclaw.orchestration.trace import new_span_id, new_trace_id

_OC_STAGE_BY_EVENT: dict[str, str] = {
    "gateway_received": "ingress",
    "gateway_normalized": "normalize",
    "skill_manifest": "skills_manifest",
    "memory_retrieval_started": "memory_start",
    "memory_retrieval_finished": "memory_done",
    "router_decision": "route",
    "task_enqueued": "async_enqueue",
    "runtime_config": "runtime_config",
    "response_sent": "response",
}
_SPECIALIST_FLAGS_SETTING_KEY = "AIA_CHAT_SPECIALIST_FLAGS_JSON"
_DEFAULT_TABULAR_PREVIEW_ROWS = 20
_DEFAULT_TABULAR_ROWS_READ = 5000


@dataclass(frozen=True)
class OpenClawGatewayResult:
    run_id: str
    reply_text: str
    trace_id: str
    elapsed_ms: int
    mode: str = "sync_direct"
    task_id: str | None = None
    selected_specialist: str = "generalist"
    interaction_mode: str = "comprehensive"
    dispatch_reason: str = ""
    manager_selected_specialist: str = "generalist"
    requested_specialist: str = "generalist"
    dynamic_agent_used: bool = False
    dynamic_agent_name: str = ""
    relay_pointer_count: int = 0
    relay_envelope_present: bool = False
    relay_envelope_pointer_count: int = 0
    relay_ttl_turn_count: int = 0
    relay_ttl_session_count: int = 0
    relay_ttl_keep_count: int = 0


class OpenClawGateway:
    def __init__(self, *, store: Any):
        self.store = store

    @staticmethod
    def _parse_json_object(text: str) -> dict[str, Any] | None:
        t = str(text or "").strip()
        start = t.find("{")
        if start < 0:
            return None
        try:
            obj, _end = json.JSONDecoder().raw_decode(t[start:])
        except Exception:
            return None
        return obj if isinstance(obj, dict) else None

    @staticmethod
    def _sanitize_dynamic_system_prompt(raw: Any) -> str:
        s = str(raw or "").strip()
        if not s:
            return ""
        s = s[:3000]
        banned = ("<tool_call>", "</tool_call>", "assistant_response:", "function_call:")
        low = s.lower()
        if any(b in low for b in banned):
            return ""
        return s

    @staticmethod
    def _parse_dynamic_agent(raw: Any) -> dict[str, Any] | None:
        if not isinstance(raw, dict):
            return None
        name = str(raw.get("name") or "").strip()
        system_prompt = OpenClawGateway._sanitize_dynamic_system_prompt(raw.get("system_prompt"))
        reason = str(raw.get("reason") or "").strip()
        tp = raw.get("tool_policy")
        tool_policy = tp if isinstance(tp, dict) else {}
        allow_tags = [str(x).strip() for x in (tool_policy.get("allow_tags") or []) if str(x).strip()]
        allow_tools = [str(x).strip() for x in (tool_policy.get("allow_tools") or []) if str(x).strip()]
        if not system_prompt:
            return None
        return {
            "name": name or "dynamic_ephemeral",
            "system_prompt": system_prompt,
            "tool_policy": {"allow_tags": allow_tags, "allow_tools": allow_tools},
            "reason": reason or "dynamic_agent_selected",
        }

    def _manager_select_specialist(
        self,
        *,
        msg: StandardMessage,
        lang: str,
        executor: Any,
        memory_curator_enabled: bool,
        skill_names_preview: list[str] | None = None,
    ) -> tuple[str, str, dict[str, Any] | None]:
        model = getattr(executor, "model", None)
        if model is None or not callable(getattr(model, "chat", None)):
            return ("generalist", "manager_model_missing", None)
        try:
            manager_context = build_role_system_context("generalist")
            allowed_fixed = ["ops", "generalist", "image"]
            if memory_curator_enabled:
                allowed_fixed.append("memory_curator")
            allowed_fixed_csv = ",".join(allowed_fixed)
            allowed_fixed_quoted = ", ".join([f'"{x}"' for x in allowed_fixed])
            user_block = render_openclaw_prompt(
                "manager/decision.md",
                variables={"agent_registry": f"specialists: {allowed_fixed_csv}"},
                strict=True,
            )
            messages = [
                {
                    "role": "system",
                    "content": (
                        f"{manager_context}\n\n"
                        "Return exactly one compact JSON object with route.specialist and route.reason. "
                        f"Allowed fixed specialists: {allowed_fixed_quoted}. "
                        "If none fits, you may set route.specialist to a custom id and include dynamic_agent with "
                        "name/system_prompt/tool_policy(allow_tags/allow_tools)/reason."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"{user_block}\n\n"
                        f"Visible skills preview: {', '.join(skill_names_preview or [])}\n\n"
                        f"User request:\n{str(msg.text or '').strip()}"
                    ),
                },
            ]
            resp = model.chat(messages, [], on_token=None)
            obj = self._parse_json_object(str(getattr(resp, "content", "") or ""))
            route = obj.get("route") if isinstance(obj, dict) else None
            if not isinstance(route, dict):
                return ("generalist", "manager_route_missing", None)
            raw_specialist = str(route.get("specialist") or "").strip().lower()
            fixed_set = {"ops", "generalist", "image"}
            if memory_curator_enabled:
                fixed_set.add("memory_curator")
            fixed = raw_specialist in fixed_set
            specialist = normalize_requested_specialist(raw_specialist) if fixed else raw_specialist
            reason = str(route.get("reason") or "").strip() or "manager_selected"
            dynamic_agent = self._parse_dynamic_agent(obj.get("dynamic_agent") if isinstance(obj, dict) else None)
            if specialist == "memory_curator" and not memory_curator_enabled:
                return ("generalist", "memory_curator_disabled_fallback", None)
            if not fixed and dynamic_agent is None:
                return ("generalist", "dynamic_agent_invalid_fallback", None)
            return (specialist, reason, dynamic_agent)
        except Exception:
            return ("generalist", "manager_select_failed", None)

    def _memory_curator_enabled(self) -> bool:
        raw = str(self.store.get_setting(_SPECIALIST_FLAGS_SETTING_KEY) or "").strip()
        if not raw:
            return True
        try:
            obj = json.loads(raw)
        except Exception:
            return True
        if not isinstance(obj, dict):
            return True
        return bool(obj.get("memory_curator", True))

    @staticmethod
    def _has_tabular_ref_attachments(msg: StandardMessage) -> bool:
        atts = msg.attachments if isinstance(msg.attachments, list) else []
        for a in atts:
            if isinstance(a, dict) and str(a.get("type") or "").strip().lower() == "tabular_ref":
                return True
        return False

    @staticmethod
    def _tabular_query_system_hint(lang: str) -> str:
        limits = OpenClawGateway._tabular_limits_from_config()
        preview_rows = int(limits.get("large_table_preview_rows") or _DEFAULT_TABULAR_PREVIEW_ROWS)
        max_rows_read = int(limits.get("max_rows_read") or _DEFAULT_TABULAR_ROWS_READ)
        if str(lang or "").startswith("en"):
            return (
                f"For large table attachments: only the first {preview_rows} preview rows are included in context. "
                f"A single read is capped at {max_rows_read} rows. "
                "If you need more rows/details, use database tools (`query_tabular_attachment` / `run_tabular_sql`) with table_id."
            )
        return (
            f"对于大表附件：当前上下文只提供前{preview_rows}行预览。"
            f"单次读取上限为{max_rows_read}行。"
            "如果需要更多行或更细节，请通过数据库工具（`query_tabular_attachment` / `run_tabular_sql`）结合 table_id 查询。"
        )

    @staticmethod
    def _tabular_limits_from_config() -> dict[str, int]:
        cfg_path_raw = str(os.getenv("AIA_OCLAW_CONFIG_PATH") or "").strip()
        cfg_path = Path(cfg_path_raw).expanduser() if cfg_path_raw else (Path(PROJECT_ROOT) / "oclaw" / "oclaw.json")
        if not cfg_path.is_absolute():
            cfg_path = (Path(PROJECT_ROOT) / cfg_path).resolve()
        try:
            obj = json.loads(cfg_path.read_text(encoding="utf-8"))
            tabular = (
                (((obj or {}).get("plugins") or {}).get("entries") or {})
                .get("memory-wiki", {})
                .get("auto", {})
                .get("attachments", {})
                .get("tabular", {})
            )
            if not isinstance(tabular, dict):
                tabular = {}
            raw_preview = int(tabular.get("large_table_preview_rows") or _DEFAULT_TABULAR_PREVIEW_ROWS)
            raw_rows_read = int(tabular.get("max_rows_read") or _DEFAULT_TABULAR_ROWS_READ)
            preview = min(max(raw_preview, 1), 500)
            rows_read = min(max(raw_rows_read, 1), 2_000_000)
            return {
                "large_table_preview_rows": preview,
                "max_rows_read": rows_read,
            }
        except Exception:
            return {
                "large_table_preview_rows": _DEFAULT_TABULAR_PREVIEW_ROWS,
                "max_rows_read": _DEFAULT_TABULAR_ROWS_READ,
            }

    @staticmethod
    def _relay_pointer_stats(msg: StandardMessage) -> dict[str, Any]:
        atts = msg.attachments if isinstance(msg.attachments, list) else []
        att_ptr_count = 0
        for a in atts:
            if isinstance(a, dict) and str(a.get("pointer_uri") or "").strip():
                att_ptr_count += 1
        md = msg.metadata if isinstance(msg.metadata, dict) else {}
        env = md.get("relay_share_envelope")
        env_ptr_count = 0
        if isinstance(env, dict):
            ad = env.get("attachments")
            if isinstance(ad, dict):
                ps = ad.get("pointers")
                if isinstance(ps, list):
                    env_ptr_count = len([x for x in ps if isinstance(x, dict)])
        return {
            "relay_pointer_count": int(att_ptr_count),
            "relay_envelope_present": bool(isinstance(env, dict)),
            "relay_envelope_pointer_count": int(env_ptr_count),
        }

    @staticmethod
    def _resolve_workspace_dir(msg: StandardMessage) -> str:
        if isinstance(msg.metadata, dict):
            ws = str(msg.metadata.get("workspaceDir") or msg.metadata.get("workspace_dir") or "").strip()
            if ws:
                return ws
        return str(os.getenv("OPENCLAW_WORKSPACE") or "").strip()

    @staticmethod
    def _resolve_command_source(msg: StandardMessage) -> str:
        if isinstance(msg.metadata, dict):
            src = str(msg.metadata.get("commandSource") or msg.metadata.get("source") or "").strip()
            if src:
                return src
        return str(msg.channel or "unknown")

    @staticmethod
    def _build_command_hook_context(*, msg: StandardMessage, workspace_dir: str) -> dict[str, Any]:
        md = msg.metadata if isinstance(msg.metadata, dict) else {}
        cfg = get_active_hooks_config()
        return {
            "commandSource": OpenClawGateway._resolve_command_source(msg),
            "senderId": str(msg.user_id or "unknown"),
            "workspaceDir": str(workspace_dir or ""),
            "sessionEntry": {
                "sessionId": str(msg.session_id or ""),
                "tenantId": str(msg.tenant_id or ""),
                "userId": str(msg.user_id or ""),
                "channel": str(msg.channel or ""),
                "role": str(msg.role or ""),
            },
            "cfg": cfg,
            "metadata": dict(md),
        }

    def _trace(
        self,
        *,
        ctx: OpenClawSessionContext,
        event_type: str,
        payload: dict[str, Any],
        started_at: float | None = None,
    ) -> None:
        merged: dict[str, Any] = dict(payload or {})
        merged.setdefault("pipeline", "openclaw_gateway")
        merged.setdefault("trace_id", ctx.trace_id)
        merged.setdefault("lang", str(ctx.lang or ""))
        merged["oc_stage"] = _OC_STAGE_BY_EVENT.get(event_type, event_type)
        if started_at is not None:
            merged["elapsed_ms_since_gateway_start"] = int((time.perf_counter() - started_at) * 1000)
        try:
            self.store.add_trace_event(
                session_id=ctx.session_id,
                trace_id=ctx.trace_id,
                span_id=new_span_id(),
                parent_span_id=ctx.parent_span_id,
                event_type=event_type,
                payload=merged,
            )
        except Exception:
            pass

    def handle_turn(
        self,
        *,
        msg: StandardMessage,
        lang: str,
        executor: Any,
        run_id: str | None = None,
        on_token: Optional[Callable[[str], None]] = None,
        on_progress: Optional[Callable[[str], None]] = None,
        on_tool_ui: Optional[Callable[[str, dict[str, Any]], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
        specialist_executor_factory: Optional[Callable[[str], Any]] = None,
    ) -> OpenClawGatewayResult:
        t0 = time.perf_counter()
        trace_id = new_trace_id()
        rid = str(run_id or "").strip() or str(uuid.uuid4())
        ctx = OpenClawSessionContext(
            session_id=msg.session_id,
            tenant_id=msg.tenant_id,
            user_id=msg.user_id,
            role=msg.role,
            channel=msg.channel,
            lang=lang,
            trace_id=trace_id,
            parent_span_id=None,
        )
        relay_stats = self._relay_pointer_stats(msg)
        ttl_stats = summarize_relay_ttl(msg.metadata.get("relay_share_envelope") if isinstance(msg.metadata, dict) else None)
        workspace_dir = self._resolve_workspace_dir(msg)
        if workspace_dir:
            initialize_hooks_runtime(cfg=None, workspace_dir=workspace_dir)
            try:
                if isinstance(msg.metadata, dict) and "workspaceDir" not in msg.metadata and "workspace_dir" not in msg.metadata:
                    msg.metadata["workspaceDir"] = workspace_dir
            except Exception:
                pass

        parsed_cmd = parse_internal_command(str(msg.text or ""))
        if parsed_cmd and parsed_cmd.action == "new":
            trigger_hook_event(
                event_type="command",
                action="new",
                session_key=str(msg.session_id or "unknown"),
                context=self._build_command_hook_context(msg=msg, workspace_dir=workspace_dir),
            )
        elif parsed_cmd and parsed_cmd.action == "reset":
            trigger_hook_event(
                event_type="command",
                action="reset",
                session_key=str(msg.session_id or "unknown"),
                context=self._build_command_hook_context(msg=msg, workspace_dir=workspace_dir),
            )

        self._trace(
            ctx=ctx,
            event_type="gateway_received",
            payload={"channel": msg.channel, "has_attachments": bool(msg.attachments), **relay_stats, **ttl_stats},
            started_at=t0,
        )
        self._trace(
            ctx=ctx,
            event_type="gateway_normalized",
            payload={"text_chars": len(msg.text or ""), "metadata_keys": sorted(list(msg.metadata.keys()))[:20]},
            started_at=t0,
        )

        skill_stats: dict[str, Any] = {}
        try:
            reg = getattr(executor, "tools", None)
            base_url = str(getattr(getattr(executor, "model", None), "base_url", "") or "")
            if reg is not None:
                _, stats = build_skill_manifest(registry=reg, store=self.store, base_url=base_url)
                skill_stats = dict(stats or {})
                self._trace(ctx=ctx, event_type="skill_manifest", payload={"base_url": base_url, **skill_stats}, started_at=t0)
        except Exception:
            pass

        self._trace(ctx=ctx, event_type="memory_retrieval_started", payload={"session_id": msg.session_id}, started_at=t0)
        memory_context = build_memory_context(
            store=self.store,
            session_id=msg.session_id,
            tenant_id=msg.tenant_id,
            user_id=msg.user_id,
            query_text=msg.text,
        )
        self._trace(
            ctx=ctx,
            event_type="memory_retrieval_finished",
            payload={
                "short_term_count": len(memory_context.short_term),
                "semantic_hit_count": len(memory_context.semantic_hits),
                "enabled": bool(memory_context.enabled),
            },
            started_at=t0,
        )

        base_metadata = dict(msg.metadata or {})
        memory_curator_enabled = self._memory_curator_enabled()
        interaction_mode = normalize_interaction_mode(base_metadata.get("interaction_mode"))
        requested_specialist = normalize_requested_specialist(base_metadata.get("selected_specialist"))
        if requested_specialist == "memory_curator" and not memory_curator_enabled:
            requested_specialist = "generalist"
        manager_specialist = requested_specialist
        dispatch_reason = "expert_direct"
        selected_executor = executor
        dynamic_agent: dict[str, Any] | None = None

        if interaction_mode == "expert" and callable(specialist_executor_factory):
            try:
                selected_executor = specialist_executor_factory(requested_specialist)
            except Exception:
                selected_executor = executor
                dispatch_reason = "expert_factory_failed"

        if interaction_mode == "comprehensive":
            manager_specialist, dispatch_reason, dynamic_agent = self._manager_select_specialist(
                msg=msg,
                lang=lang,
                executor=executor,
                memory_curator_enabled=memory_curator_enabled,
                skill_names_preview=list(skill_stats.get("visible_names_preview") or []),
            )
            if manager_specialist in {"ops", "generalist", "image", "memory_curator"}:
                if callable(specialist_executor_factory):
                    try:
                        selected_executor = specialist_executor_factory(manager_specialist)
                    except Exception:
                        selected_executor = executor
                        dispatch_reason = "manager_factory_failed"
            elif dynamic_agent:
                try:
                    selected_executor = build_ephemeral_executor(
                        self.store,
                        lang=lang,
                        system_prompt=str(dynamic_agent.get("system_prompt") or ""),
                        tool_policy=dict(dynamic_agent.get("tool_policy") or {}),
                        viewer_user_id=msg.user_id,
                        viewer_tenant_id=msg.tenant_id,
                        policy_session_id=msg.session_id,
                        path_policy_tenant_id=msg.tenant_id,
                        path_policy_user_id=msg.user_id,
                    )
                    manager_specialist = str(dynamic_agent.get("name") or "dynamic_ephemeral")
                    dispatch_reason = str(dynamic_agent.get("reason") or "dynamic_agent_selected")
                except Exception:
                    manager_specialist = "generalist"
                    dispatch_reason = "dynamic_agent_build_failed"

        route_msg = StandardMessage(
            session_id=msg.session_id,
            tenant_id=msg.tenant_id,
            user_id=msg.user_id,
            role=msg.role,
            channel=msg.channel,
            text=msg.text,
            attachments=list(msg.attachments or []),
            metadata={
                **base_metadata,
                "skills_total": int(skill_stats.get("skills_total") or 0),
                "interaction_mode": interaction_mode,
                "requested_specialist": requested_specialist,
                "manager_selected_specialist": manager_specialist,
            },
        )
        route = decide_route(route_msg, store=self.store, model=getattr(selected_executor, "model", None))
        self._trace(
            ctx=ctx,
            event_type="router_decision",
            payload={
                "mode": route.mode,
                "reason": route.reason,
                "interaction_mode": interaction_mode,
                "requested_specialist": requested_specialist,
                "manager_selected_specialist": manager_specialist,
                "dispatch_reason": dispatch_reason,
            },
            started_at=t0,
        )
        if on_progress:
            on_progress("oclaw: running…")
        if route.mode == "async_task":
            worker_id = ensure_worker_started(store=self.store)
            task = self.store.openclaw_task_create(
                tenant_id=msg.tenant_id,
                session_id=msg.session_id,
                task_type="async_turn",
                payload={
                    "trace_id": trace_id,
                    "run_id": rid,
                    "session_id": msg.session_id,
                    "tenant_id": msg.tenant_id,
                    "user_id": msg.user_id,
                    "role": msg.role,
                    "channel": msg.channel,
                    "lang": lang,
                    "text": msg.text,
                    "attachments": msg.attachments,
                    "metadata": dict(msg.metadata or {}),
                    "relay_share_envelope": (dict(msg.metadata.get("relay_share_envelope")) if isinstance(msg.metadata, dict) and isinstance(msg.metadata.get("relay_share_envelope"), dict) else None),
                    "acp_parent_run_id": (str(msg.metadata.get("acp_parent_run_id") or "") if isinstance(msg.metadata, dict) else ""),
                    "acp_child_run_id": (str(msg.metadata.get("acp_child_run_id") or "") if isinstance(msg.metadata, dict) else ""),
                    "relay_pointer_count": int(relay_stats.get("relay_pointer_count") or 0),
                    "relay_envelope_present": bool(relay_stats.get("relay_envelope_present")),
                    "relay_envelope_pointer_count": int(relay_stats.get("relay_envelope_pointer_count") or 0),
                    "relay_ttl_turn_count": int(ttl_stats.get("turn") or 0),
                    "relay_ttl_session_count": int(ttl_stats.get("session") or 0),
                    "relay_ttl_keep_count": int(ttl_stats.get("keep") or 0),
                    "interaction_mode": interaction_mode,
                    "requested_specialist": requested_specialist,
                    "selected_specialist": manager_specialist,
                    "manager_selected_specialist": manager_specialist,
                    "dispatch_reason": dispatch_reason,
                    "memory_mode": str((msg.metadata or {}).get("memory_mode") or ""),
                    "dynamic_agent_used": bool(dynamic_agent is not None),
                    "dynamic_agent": dynamic_agent,
                },
            )
            self._trace(
                ctx=ctx,
                event_type="task_enqueued",
                payload={"task_id": task.id, "task_type": task.task_type, "worker_id": worker_id, "status": task.status},
                started_at=t0,
            )
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            reply = render_prompt(
                "fallback/task_queued.en.md" if str(lang or "").startswith("en") else "fallback/task_queued.zh.md",
                variables={"task_id": str(task.id)},
                strict=True,
            )
            self._trace(
                ctx=ctx,
                event_type="response_sent",
                payload={"ok": True, "elapsed_ms": elapsed_ms, "mode": "async_task", "task_id": str(task.id)},
                started_at=t0,
            )
            return OpenClawGatewayResult(
                run_id=rid,
                reply_text=reply,
                trace_id=trace_id,
                elapsed_ms=elapsed_ms,
                mode="async_task",
                task_id=task.id,
                selected_specialist=manager_specialist,
                interaction_mode=interaction_mode,
                dispatch_reason=dispatch_reason,
                manager_selected_specialist=manager_specialist,
                requested_specialist=requested_specialist,
                dynamic_agent_used=bool(dynamic_agent is not None),
                dynamic_agent_name=str((dynamic_agent or {}).get("name") or ""),
                relay_pointer_count=int(relay_stats.get("relay_pointer_count") or 0),
                relay_envelope_present=bool(relay_stats.get("relay_envelope_present")),
                relay_envelope_pointer_count=int(relay_stats.get("relay_envelope_pointer_count") or 0),
                relay_ttl_turn_count=int(ttl_stats.get("turn") or 0),
                relay_ttl_session_count=int(ttl_stats.get("session") or 0),
                relay_ttl_keep_count=int(ttl_stats.get("keep") or 0),
            )
        try:
            model = getattr(selected_executor, "model", None)
            tools = getattr(selected_executor, "tools", None)
            if model is None or tools is None:
                raise RuntimeError("executor missing model/tools")
            sys_prompt = str(getattr(selected_executor, "system_prompt", "") or "")
            if self._has_tabular_ref_attachments(msg):
                sys_prompt = f"{sys_prompt}\n\n{self._tabular_query_system_hint(lang)}".strip()

            def _get_int_setting(key: str, default: int, lo: int, hi: int) -> int:
                try:
                    raw = str(self.store.get_setting(key) or "").strip()
                    if raw.isdigit():
                        return max(lo, min(int(raw), hi))
                except Exception:
                    pass
                return max(lo, min(int(default), hi))

            core_out = run_agent_core(
                store=self.store,
                data=AgentCoreRunInput(
                    msg=msg,
                    lang=lang,
                    system_prompt=sys_prompt,
                    model=model,
                    tools=tools,
                    trace_id=trace_id,
                    parent_span_id=None,
                    run_id=rid,
                    max_messages=_get_int_setting("AIA_TURN_MAX_CONTEXT_MESSAGES", 80, 10, 400),
                    max_tool_rounds=_get_int_setting("AIA_TURN_MAX_TOOL_ROUNDS", 8, 1, 30),
                    max_tool_workers=_get_int_setting("AIA_TURN_MAX_TOOL_WORKERS", 8, 1, 32),
                    max_attempts=_get_int_setting("AIA_OPENCLAW_MAX_ATTEMPTS", 2, 1, 5),
                    memory_context=memory_context,
                    on_token=on_token,
                    on_progress=on_progress,
                    on_tool_ui=on_tool_ui,
                    should_stop=should_stop,
                    skill_binding_role=str(manager_specialist or "generalist"),
                    wire_policy_role="manager" if interaction_mode == "comprehensive" else str(requested_specialist),
                ),
            )
            reply = core_out.outcome.final_text
        except Exception as exc:
            base = render_prompt(
                "fallback/openclaw_runtime_error.en.md" if str(lang or "").startswith("en") else "fallback/openclaw_runtime_error.zh.md",
                strict=True,
            )
            detail = f"{type(exc).__name__}: {str(exc or '')}".strip().replace("\n", " ")[:400]
            reply = f"{base}\n(detail: {detail})" if detail else base

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        self._trace(
            ctx=ctx,
            event_type="response_sent",
            payload={"ok": bool(str(reply or "").strip()), "elapsed_ms": elapsed_ms, "mode": "sync_direct"},
            started_at=t0,
        )
        return OpenClawGatewayResult(
            run_id=rid,
            reply_text=str(reply or ""),
            trace_id=trace_id,
            elapsed_ms=elapsed_ms,
            mode="sync_direct",
            selected_specialist=manager_specialist,
            interaction_mode=interaction_mode,
            dispatch_reason=dispatch_reason,
            manager_selected_specialist=manager_specialist,
            requested_specialist=requested_specialist,
            dynamic_agent_used=bool(dynamic_agent is not None),
            dynamic_agent_name=str((dynamic_agent or {}).get("name") or ""),
            relay_pointer_count=int(relay_stats.get("relay_pointer_count") or 0),
            relay_envelope_present=bool(relay_stats.get("relay_envelope_present")),
            relay_envelope_pointer_count=int(relay_stats.get("relay_envelope_pointer_count") or 0),
            relay_ttl_turn_count=int(ttl_stats.get("turn") or 0),
            relay_ttl_session_count=int(ttl_stats.get("session") or 0),
            relay_ttl_keep_count=int(ttl_stats.get("keep") or 0),
        )


__all__ = ["OpenClawGateway", "OpenClawGatewayResult"]
