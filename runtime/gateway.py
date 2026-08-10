from __future__ import annotations

import json
import os
import time
import uuid
import threading
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from runtime.hooks.eligibility_from_metadata import hook_eligibility_from_message_metadata
from runtime.hooks_runtime import (
    get_active_hooks_config,
    initialize_hooks_runtime,
    trigger_hook_event,
)
from runtime.relay_pointer import summarize_relay_ttl
from runtime.skills import build_skill_manifest
from runtime.types import (
    OclawSessionContext,
    StandardMessage,
    normalize_interaction_mode,
    normalize_requested_specialist,
)
from svc.config.paths import PROJECT_ROOT
from runtime.prompt_templates import render_prompt

from runtime.command_parser import parse_internal_command
from runtime.core.agent_execution import AgentCoreRunInput, build_memory_context, run_agent_core
from runtime.router import decide_route
from runtime.worker import ensure_worker_started
from runtime.orchestration.trace import new_span_id, new_trace_id
from runtime.chat.tool_runtime import compact_turn_tool_messages_for_storage
from runtime.chat.model_path_audit import ensure_no_tool_or_embedded_image_payload
from runtime.session_auto_title import (
    AUTO_TITLE_SYSTEM_PROMPT_EN,
    AUTO_TITLE_SYSTEM_PROMPT_ZH,
    finalize_auto_title,
)
from runtime.tools.base import ToolRegistry
from runtime.tools.public.local_sdk import local_adapter_startup_self_check

logger = logging.getLogger(__name__)

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
_SESSION_TITLE_MAX_LEN = 120
_TITLE_TRIGGER_ROUND = 3
_TITLE_BODIES_MAX_CHARS = 4000
_AUTO_TITLE_STAGE_KEY_PREFIX = "AIA_SESSION_AUTO_TITLE_STAGE:"
_SKILL_MANIFEST_CACHE_LOCK = threading.Lock()
_SKILL_MANIFEST_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_SKILL_MANIFEST_CACHE_TTL_SEC = 5.0


@dataclass(frozen=True)
class OclawGatewayResult:
    run_id: str
    reply_text: str
    trace_id: str
    elapsed_ms: int
    mode: str = "sync_direct"
    task_id: str | None = None
    selected_specialist: str = "generalist"
    interaction_mode: str = "expert"
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
    # agent-core 本轮 ``chat_message.turn_uuid``；供 WS 收尾与落库兜底对齐
    turn_uuid: str = ""


@dataclass(frozen=True)
class GatewayDispatchPlan:
    interaction_mode: str
    requested_specialist: str
    manager_specialist: str
    dispatch_reason: str
    selected_executor: Any
    dynamic_agent: dict[str, Any] | None
    specialist_input_msg: StandardMessage | None
    manager_exec_msg: StandardMessage | None
    manager_instruction_text: str


class OclawGateway:
    def __init__(self, *, store: Any):
        self.store = store
        try:
            check = local_adapter_startup_self_check()
            if not bool(check.get("ok")):
                logger.warning(
                    "Local adapter startup self-check failed: %s (%s)",
                    str(check.get("error_code") or ""),
                    str(check.get("error") or ""),
                )
        except Exception:
            pass

    def _maybe_generate_title_on_third_round(self, *, msg: StandardMessage, model: Any | None) -> None:
        """Generate title once on round-3: one plain model.chat (system+user, no tools)."""
        if model is None or not callable(getattr(model, "chat", None)):
            return
        sid = str(msg.session_id or "").strip()
        if not sid:
            return
        try:
            stage_raw = str(self.store.get_setting(f"{_AUTO_TITLE_STAGE_KEY_PREFIX}{sid}") or "").strip()
        except Exception:
            stage_raw = ""
        try:
            sess = self.store.get_session(sid)
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
            rows = self.store.get_messages(session_id=sid, limit=200)
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
            sys = AUTO_TITLE_SYSTEM_PROMPT_EN if lang_is_en else AUTO_TITLE_SYSTEM_PROMPT_ZH
            messages = [{"role": "system", "content": sys}, {"role": "user", "content": body}]
            ensure_no_tool_or_embedded_image_payload(messages=messages, path="gateway.auto_title")
            resp = model.chat(messages, [], on_token=None)
            raw_title = str(getattr(resp, "content", "") or "").strip().strip("\"'` ")
            title = finalize_auto_title(raw=raw_title, fallback=str(bodies[0] or "").strip())
            if not title:
                return
            self.store.rename_session(sid, title[:_SESSION_TITLE_MAX_LEN])
            try:
                self.store.set_setting(f"{_AUTO_TITLE_STAGE_KEY_PREFIX}{sid}", "3")
            except Exception:
                pass
        except Exception:
            return

    def _maybe_rename_from_first_user_message(
        self,
        *,
        session_id: str,
        user_text: str,
        attachments: list[dict[str, Any]] | None,
    ) -> None:
        sid = str(session_id or "").strip()
        if not sid:
            return
        try:
            stage_raw = str(self.store.get_setting(f"{_AUTO_TITLE_STAGE_KEY_PREFIX}{sid}") or "").strip()
        except Exception:
            stage_raw = ""
        if stage_raw in ("1", "3"):
            return
        try:
            sess = self.store.get_session(sid)
        except Exception:
            sess = None
        if not sess:
            return
        cur_title = str(getattr(sess, "title", "") or "").strip()
        if cur_title not in ("新会话", "New Chat"):
            return
        try:
            rows = self.store.get_messages(session_id=sid, limit=20)
        except Exception:
            rows = []
        user_count = 0
        for r in rows or []:
            if str(getattr(r, "role", "") or "").strip().lower() == "user":
                user_count += 1
        # First user turn only.
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
            self.store.rename_session(sid, title[:_SESSION_TITLE_MAX_LEN])
            try:
                self.store.set_setting(f"{_AUTO_TITLE_STAGE_KEY_PREFIX}{sid}", "1")
            except Exception:
                pass
        except Exception:
            pass

    def _memory_enabled(self) -> bool:
        raw = str(self.store.get_setting(_SPECIALIST_FLAGS_SETTING_KEY) or "").strip()
        if not raw:
            return True
        try:
            obj = json.loads(raw)
        except Exception:
            return True
        if not isinstance(obj, dict):
            return True
        return bool(obj.get("memory", True))

    @staticmethod
    def _has_tabular_ref_attachments(msg: StandardMessage) -> bool:
        atts = msg.attachments if isinstance(msg.attachments, list) else []
        for a in atts:
            if isinstance(a, dict) and str(a.get("type") or "").strip().lower() == "tabular_ref":
                return True
        return False

    @staticmethod
    def _has_text_ref_attachments(msg: StandardMessage) -> bool:
        atts = msg.attachments if isinstance(msg.attachments, list) else []
        for a in atts:
            if isinstance(a, dict) and str(a.get("type") or "").strip().lower() == "text_ref":
                return True
        return False

    @staticmethod
    def _has_image_ref_attachments(msg: StandardMessage) -> bool:
        atts = msg.attachments if isinstance(msg.attachments, list) else []
        for a in atts:
            if not isinstance(a, dict):
                continue
            t = str(a.get("type") or "").strip().lower()
            if t in {"image_ref", "image", "input_image"}:
                return True
        return False

    @staticmethod
    def _has_video_ref_attachments(msg: StandardMessage) -> bool:
        atts = msg.attachments if isinstance(msg.attachments, list) else []
        for a in atts:
            if not isinstance(a, dict):
                continue
            t = str(a.get("type") or "").strip().lower()
            if t == "video_ref":
                return True
        return False

    @staticmethod
    def _is_channel_delivery_channel(msg: StandardMessage) -> bool:
        ch = str(getattr(msg, "channel", "") or "").strip().lower()
        return ch in {"whatsapp", "wechat", "weixin"}

    @staticmethod
    def _channel_file_delivery_system_hint(lang: str) -> str:
        from runtime.orchestration.group_ingest import build_channel_file_delivery_instruction

        return str(build_channel_file_delivery_instruction(lang=lang) or "").strip()

    @staticmethod
    def _ops_short_intent_system_hint(msg: StandardMessage, lang: str) -> str:
        from runtime.application.gateway.ops_short_intent import maybe_ops_short_intent_system_hint

        return str(maybe_ops_short_intent_system_hint(text=str(msg.text or ""), lang=lang) or "").strip()

    def _resolve_max_tool_rounds(self, msg: StandardMessage, *, base: int) -> int:
        """Optionally cap short-intent rounds when explicitly configured.

        Field ops often raise AIA_TURN_MAX_TOOL_ROUNDS (e.g. 200). Absolute caps hurt
        legitimate multi-NE work; identical-arg / retry_forbidden guards handle loops.
        Set AIA_OPS_SHORT_INTENT_MAX_TOOL_ROUNDS only if you want an explicit short-intent ceiling.
        """
        rounds = max(1, min(int(base), 300))
        if not self._is_channel_delivery_channel(msg):
            return rounds
        try:
            raw = str(self.store.get_setting("AIA_OPS_SHORT_INTENT_MAX_TOOL_ROUNDS") or "").strip()
        except Exception:
            raw = ""
        if not raw.isdigit():
            return rounds
        md = msg.metadata if isinstance(msg.metadata, dict) else {}
        from runtime.application.gateway.ops_short_intent import detect_ops_short_intent

        intent = detect_ops_short_intent(str(msg.text or md.get("raw_inbound_text") or ""))
        if not intent:
            return rounds
        cap = max(3, min(int(raw), 300))
        return min(rounds, cap)

    @staticmethod
    def _group_focus_system_hint(msg: StandardMessage, lang: str) -> str:
        """Only for shared group transcripts (legacy session_scope=chat / __group__)."""
        md = msg.metadata if isinstance(msg.metadata, dict) else {}
        if not bool(md.get("is_group")):
            return ""
        from runtime.orchestration.group_ingest import (
            build_group_focus_instruction,
            normalize_group_session_scope,
        )

        scope = normalize_group_session_scope(md.get("group_session_scope"))
        if scope != "chat":
            return ""
        return str(build_group_focus_instruction(lang=lang) or "").strip()

    @staticmethod
    def _tabular_query_system_hint(lang: str) -> str:
        limits = OclawGateway._tabular_limits_from_config()
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
    def _text_query_system_hint(lang: str) -> str:
        if str(lang or "").startswith("en"):
            return (
                "For long text attachments: context may contain only summary/preview. "
                "For detailed evidence, use `query_text_attachment` with `text_id` from `text_ref` attachment."
            )
        return (
            "对于长文本附件：上下文可能只包含摘要/预览。"
            "如需细节证据，请使用 `text_ref` 提供的 text_id 调用 `query_text_attachment`。"
        )

    @staticmethod
    def _image_query_system_hint(lang: str) -> str:
        if str(lang or "").startswith("en"):
            return (
                "For image attachments: use `query_image_attachment` with attachment_id "
                "for OCR/description when visual evidence is required."
            )
        return (
            "对于图片附件：如需 OCR 或图像细节，请使用 attachment_id 调用 `query_image_attachment`。"
        )

    @staticmethod
    def _video_query_system_hint(lang: str) -> str:
        if str(lang or "").startswith("en"):
            return (
                "For video attachments: use `query_video_attachment` with attachment_id from `video_ref` "
                "to get metadata or transcript (if enabled)."
            )
        return "对于视频附件：请使用 `video_ref` 提供的 attachment_id 调用 `query_video_attachment` 获取元信息/转写。"

    @staticmethod
    def _tabular_limits_from_config() -> dict[str, int]:
        cfg_path_raw = str(os.getenv("AIA_OCLAW_CONFIG_PATH") or "").strip()
        cfg_path = Path(cfg_path_raw).expanduser() if cfg_path_raw else (Path(PROJECT_ROOT) / "oclaw.json")
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
        return str(os.getenv("OCLAW_WORKSPACE") or "").strip()

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
            "commandSource": OclawGateway._resolve_command_source(msg),
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
        ctx: OclawSessionContext,
        event_type: str,
        payload: dict[str, Any],
        started_at: float | None = None,
        trace_sink: list[dict[str, Any]] | None = None,
    ) -> None:
        merged: dict[str, Any] = dict(payload or {})
        merged.setdefault("pipeline", "oclaw_gateway")
        merged.setdefault("trace_id", ctx.trace_id)
        merged.setdefault("lang", str(ctx.lang or ""))
        merged["oc_stage"] = _OC_STAGE_BY_EVENT.get(event_type, event_type)
        if started_at is not None:
            merged["elapsed_ms_since_gateway_start"] = int((time.perf_counter() - started_at) * 1000)
        row = {
            "session_id": ctx.session_id,
            "trace_id": ctx.trace_id,
            "span_id": new_span_id(),
            "parent_span_id": ctx.parent_span_id,
            "event_type": event_type,
            "payload": merged,
        }
        if trace_sink is not None:
            trace_sink.append(row)
            return
        try:
            self.store.add_trace_event(**row)
        except Exception:
            pass

    def _build_skill_stats(self, *, executor: Any, started_at: float, trace_local: Callable[..., None]) -> dict[str, Any]:
        skill_stats: dict[str, Any] = {}
        try:
            reg = getattr(executor, "tools", None)
            base_url = str(getattr(getattr(executor, "model", None), "base_url", "") or "")
            if reg is not None:
                cache_key = (
                    f"base={base_url}|skill_rt={str(self.store.get_setting('AIA_SKILL_RUNTIME_ENABLED') or '')}|"
                    f"skill_disabled={str(self.store.get_setting('AIA_SKILL_DISABLED_NAMES') or '')}|"
                    f"bind_en={str(self.store.get_setting('AIA_SKILL_ROLE_BINDING_ENABLED') or '')}|"
                    f"bind_inherit={str(self.store.get_setting('AIA_SKILL_ROLE_BINDING_MANAGER_INHERIT') or '')}"
                )
                now = time.time()
                with _SKILL_MANIFEST_CACHE_LOCK:
                    cached = _SKILL_MANIFEST_CACHE.get(cache_key)
                    if cached and (now - float(cached[0])) <= _SKILL_MANIFEST_CACHE_TTL_SEC:
                        skill_stats = dict(cached[1] or {})
                    else:
                        _, stats = build_skill_manifest(registry=reg, store=self.store, base_url=base_url)
                        skill_stats = dict(stats or {})
                        _SKILL_MANIFEST_CACHE[cache_key] = (now, dict(skill_stats))
                        if len(_SKILL_MANIFEST_CACHE) > 128:
                            oldest_key = sorted(_SKILL_MANIFEST_CACHE.items(), key=lambda kv: kv[1][0])[0][0]
                            _SKILL_MANIFEST_CACHE.pop(oldest_key, None)
                trace_local(event_type="skill_manifest", payload={"base_url": base_url, **skill_stats}, started_at=started_at)
        except Exception:
            pass
        return skill_stats

    def _select_dispatch_plan(
        self,
        *,
        msg: StandardMessage,
        lang: str,
        executor: Any,
        interaction_mode: str,
        requested_specialist: str,
        memory_enabled: bool,
        specialist_executor_factory: Optional[Callable[[str], Any]],
        trace_local: Callable[..., None],
        started_at: float,
    ) -> GatewayDispatchPlan:
        del msg, lang, memory_enabled, trace_local, started_at
        # Expert-only product surface: never run Manager/comprehensive routing.
        interaction_mode = "expert"
        manager_specialist = requested_specialist
        dispatch_reason = "expert_direct"
        selected_executor = executor
        dynamic_agent: dict[str, Any] | None = None
        specialist_input_msg: StandardMessage | None = None
        manager_exec_msg: StandardMessage | None = None
        manager_instruction_text = ""
        if callable(specialist_executor_factory):
            try:
                selected_executor = specialist_executor_factory(requested_specialist)
            except Exception:
                selected_executor = executor
                dispatch_reason = "expert_factory_failed"
        return GatewayDispatchPlan(
            interaction_mode=interaction_mode,
            requested_specialist=requested_specialist,
            manager_specialist=manager_specialist,
            dispatch_reason=dispatch_reason,
            selected_executor=selected_executor,
            dynamic_agent=dynamic_agent,
            specialist_input_msg=specialist_input_msg,
            manager_exec_msg=manager_exec_msg,
            manager_instruction_text=manager_instruction_text,
        )

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
    ) -> OclawGatewayResult:
        t0 = time.perf_counter()
        ws_received_ms = None
        try:
            if isinstance(msg.metadata, dict):
                v = (
                    msg.metadata.get("ws_client_send_ms")
                    or msg.metadata.get("client_send_ms")
                    or msg.metadata.get("ws_accepted_ms")
                )
                if v is not None:
                    ws_received_ms = int(v)
        except Exception:
            ws_received_ms = None
        trace_id = new_trace_id()
        rid = str(run_id or "").strip() or str(uuid.uuid4())
        executed_turn_uuid = ""
        ctx = OclawSessionContext(
            session_id=msg.session_id,
            tenant_id=msg.tenant_id,
            user_id=msg.user_id,
            role=msg.role,
            channel=msg.channel,
            lang=lang,
            trace_id=trace_id,
            parent_span_id=None,
        )
        trace_rows: list[dict[str, Any]] = []

        def _trace_local(*, event_type: str, payload: dict[str, Any], started_at: float | None = None) -> None:
            self._trace(ctx=ctx, event_type=event_type, payload=payload, started_at=started_at, trace_sink=trace_rows)

        def _flush_trace_rows() -> None:
            if not trace_rows:
                return
            try:
                self.store.add_trace_events_batch(trace_rows)
                trace_rows.clear()
            except Exception:
                # Fallback: stores used by unit tests may not implement batch insert.
                try:
                    for row in list(trace_rows):
                        try:
                            self.store.add_trace_event(**row)
                        except Exception:
                            continue
                    trace_rows.clear()
                except Exception:
                    pass
        relay_stats = self._relay_pointer_stats(msg)
        ttl_stats = summarize_relay_ttl(msg.metadata.get("relay_share_envelope") if isinstance(msg.metadata, dict) else None)
        workspace_dir = self._resolve_workspace_dir(msg)
        if workspace_dir:
            elig = hook_eligibility_from_message_metadata(msg.metadata if isinstance(msg.metadata, dict) else None)
            initialize_hooks_runtime(cfg=None, workspace_dir=workspace_dir, eligibility=elig)
            try:
                if isinstance(msg.metadata, dict) and "workspaceDir" not in msg.metadata and "workspace_dir" not in msg.metadata:
                    msg.metadata["workspaceDir"] = workspace_dir
            except Exception:
                pass

        parsed_cmd = parse_internal_command(str(msg.text or ""))
        self._maybe_rename_from_first_user_message(
            session_id=str(msg.session_id or ""),
            user_text=str(msg.text or ""),
            attachments=list(msg.attachments or []),
        )
        self._maybe_generate_title_on_third_round(msg=msg, model=getattr(executor, "model", None))
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

        _trace_local(
            event_type="gateway_received",
            payload={
                "channel": msg.channel,
                "has_attachments": bool(msg.attachments),
                "run_id": rid,
                "ws_client_send_ms": ws_received_ms,
                **relay_stats,
                **ttl_stats,
            },
            started_at=t0,
        )
        _trace_local(
            event_type="gateway_normalized",
            payload={"text_chars": len(msg.text or ""), "metadata_keys": sorted(list(msg.metadata.keys()))[:20]},
            started_at=t0,
        )

        skill_stats = self._build_skill_stats(executor=executor, started_at=t0, trace_local=_trace_local)

        _trace_local(event_type="memory_retrieval_started", payload={"session_id": msg.session_id}, started_at=t0)
        memory_context = build_memory_context(
            store=self.store,
            session_id=msg.session_id,
            tenant_id=msg.tenant_id,
            user_id=msg.user_id,
            query_text=msg.text,
        )
        _trace_local(
            event_type="memory_retrieval_finished",
            payload={
                "short_term_count": len(memory_context.short_term),
                "semantic_hit_count": len(memory_context.semantic_hits),
                "enabled": bool(memory_context.enabled),
            },
            started_at=t0,
        )

        base_metadata = dict(msg.metadata or {})
        memory_enabled = self._memory_enabled()
        interaction_mode = normalize_interaction_mode(base_metadata.get("interaction_mode"))
        # Defensive: product surface is expert-only regardless of inbound metadata.
        interaction_mode = "expert"
        requested_specialist = normalize_requested_specialist(base_metadata.get("selected_specialist"))
        if requested_specialist == "memory" and not memory_enabled:
            requested_specialist = "generalist"
        plan = self._select_dispatch_plan(
            msg=msg,
            lang=lang,
            executor=executor,
            interaction_mode=interaction_mode,
            requested_specialist=requested_specialist,
            memory_enabled=memory_enabled,
            specialist_executor_factory=specialist_executor_factory,
            trace_local=_trace_local,
            started_at=t0,
        )
        manager_specialist = plan.manager_specialist
        dispatch_reason = plan.dispatch_reason
        selected_executor = plan.selected_executor
        dynamic_agent = plan.dynamic_agent
        specialist_input_msg = plan.specialist_input_msg
        manager_exec_msg = plan.manager_exec_msg
        manager_instruction_text = plan.manager_instruction_text
        system_prompt_override = ""
        tools_override = None

        route_mode = "sync_direct"
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
        route_mode = str(route.mode or "sync_direct")
        route_reason = str(route.reason or "")
        _trace_local(
            event_type="router_decision",
            payload={
                "mode": route_mode,
                "reason": route_reason,
                "interaction_mode": interaction_mode,
                "requested_specialist": requested_specialist,
                "manager_selected_specialist": manager_specialist,
                "dispatch_reason": dispatch_reason,
            },
            started_at=t0,
        )
        if on_progress:
            on_progress("oclaw: running…")
        if route_mode == "async_task":
            worker_id = ensure_worker_started(store=self.store)
            task = self.store.oclaw_task_create(
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
                trace_sink=trace_rows,
            )
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            reply = render_prompt(
                "fallback/task_queued.en.md" if str(lang or "").startswith("en") else "fallback/task_queued.zh.md",
                variables={"task_id": str(task.id)},
                strict=True,
            )
            _trace_local(
                event_type="response_sent",
                payload={"ok": True, "elapsed_ms": elapsed_ms, "mode": "async_task", "task_id": str(task.id)},
                started_at=t0,
            )
            _flush_trace_rows()
            return OclawGatewayResult(
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
                turn_uuid="",
            )
        executed_turn_uuid = ""
        try:
            model = getattr(selected_executor, "model", None)
            tools = tools_override if tools_override is not None else getattr(selected_executor, "tools", None)
            if model is None or tools is None:
                raise RuntimeError("executor missing model/tools")
            if self._is_channel_delivery_channel(msg) and isinstance(tools, ToolRegistry):
                from runtime.application.gateway.ops_short_intent import (
                    detect_ops_short_intent,
                    filter_tool_specs_for_ops_short_intent,
                    ops_short_intent_should_filter_tools,
                )

                md_intent = msg.metadata if isinstance(msg.metadata, dict) else {}
                short_intent = detect_ops_short_intent(
                    str(msg.text or md_intent.get("raw_inbound_text") or "")
                )
                if ops_short_intent_should_filter_tools(short_intent):
                    before_n = len(tools.list())
                    filtered_specs = filter_tool_specs_for_ops_short_intent(
                        tools.list(), intent=short_intent
                    )
                    if len(filtered_specs) < before_n:
                        tools_override = ToolRegistry(filtered_specs)
                        tools = tools_override
                        _trace_local(
                            event_type="ops_short_intent_tools_filtered",
                            payload={
                                "intent": short_intent,
                                "before_count": before_n,
                                "after_count": len(filtered_specs),
                            },
                            started_at=t0,
                        )
            sys_prompt = system_prompt_override or str(getattr(selected_executor, "system_prompt", "") or "")
            if self._is_channel_delivery_channel(msg):
                ch_hint = self._channel_file_delivery_system_hint(lang)
                if ch_hint:
                    sys_prompt = f"{sys_prompt}\n\n{ch_hint}".strip()
                focus_hint = self._group_focus_system_hint(msg, lang)
                if focus_hint:
                    sys_prompt = f"{sys_prompt}\n\n{focus_hint}".strip()
                # Always inject short-intent recipe on WA/weixin (not only when specialist==ops).
                intent_hint = self._ops_short_intent_system_hint(msg, lang)
                if intent_hint:
                    sys_prompt = f"{sys_prompt}\n\n{intent_hint}".strip()
            if self._has_tabular_ref_attachments(msg):
                sys_prompt = f"{sys_prompt}\n\n{self._tabular_query_system_hint(lang)}".strip()
            if self._has_text_ref_attachments(msg):
                sys_prompt = f"{sys_prompt}\n\n{self._text_query_system_hint(lang)}".strip()
            if self._has_image_ref_attachments(msg):
                sys_prompt = f"{sys_prompt}\n\n{self._image_query_system_hint(lang)}".strip()
            if self._has_video_ref_attachments(msg):
                sys_prompt = f"{sys_prompt}\n\n{self._video_query_system_hint(lang)}".strip()

            def _get_int_setting(key: str, default: int, lo: int, hi: int) -> int:
                try:
                    raw = str(self.store.get_setting(key) or "").strip()
                    if raw.isdigit():
                        return max(lo, min(int(raw), hi))
                except Exception:
                    pass
                return max(lo, min(int(default), hi))

            _trace_local(
                event_type="model_chat_start",
                payload={"run_id": rid, "trace_id": trace_id},
                started_at=t0,
            )
            exec_msg = (
                msg
            )
            core_out = run_agent_core(
                store=self.store,
                data=AgentCoreRunInput(
                    msg=exec_msg,
                    persisted_user_text=str(msg.text or ""),
                    lang=lang,
                    system_prompt=sys_prompt,
                    model=model,
                    tools=tools,
                    trace_id=trace_id,
                    parent_span_id=None,
                    run_id=rid,
                    max_messages=_get_int_setting("AIA_TURN_MAX_CONTEXT_MESSAGES", 80, 10, 400),
                    max_tool_rounds=self._resolve_max_tool_rounds(
                        msg,
                        base=_get_int_setting("AIA_TURN_MAX_TOOL_ROUNDS", 100, 1, 300),
                    ),
                    max_tool_workers=_get_int_setting("AIA_TURN_MAX_TOOL_WORKERS", 8, 1, 32),
                    max_attempts=_get_int_setting("AIA_OCLAW_MAX_ATTEMPTS", 2, 1, 5),
                    memory_context=memory_context,
                    # Always stream specialist tokens (incl. reasoning deltas) to WS clients.
                    # Comprehensive used to pass None here to hide raw specialist output before manager polish;
                    # that made admin webchat look like the stream died mid-"推理" until final/manager only.
                    on_token=on_token,
                    on_progress=on_progress,
                    on_tool_ui=on_tool_ui,
                    should_stop=should_stop,
                    skill_binding_role=str(manager_specialist or "generalist"),
                    wire_policy_role=str(requested_specialist),
                ),
            )
            executed_turn_uuid = str(getattr(core_out.outcome, "turn_uuid", "") or "")
            specialist_reply = str(core_out.outcome.final_text or "")
            reply = specialist_reply
            if not str(reply or "").strip():
                rs = getattr(core_out, "run_state", None)
                if rs is not None and str(getattr(rs, "status", "") or "") == "failed":
                    reason = ""
                    attempts = getattr(rs, "attempts", ()) or ()
                    if attempts:
                        reason = str(getattr(attempts[-1], "reason", "") or "")
                    if not reason:
                        reason = str(getattr(rs, "last_error_code", "") or "unknown_error")
                    base = render_prompt(
                        "fallback/runtime_error.en.md" if str(lang or "").startswith("en") else "fallback/runtime_error.zh.md",
                        strict=True,
                    )
                    detail = str(reason or "").strip().replace("\n", " ")[:400]
                    reply = f"{base}\n(detail: {detail})" if detail else base
        except Exception as exc:
            base = render_prompt(
                "fallback/runtime_error.en.md" if str(lang or "").startswith("en") else "fallback/runtime_error.zh.md",
                strict=True,
            )
            detail = f"{type(exc).__name__}: {str(exc or '')}".strip().replace("\n", " ")[:400]
            reply = f"{base}\n(detail: {detail})" if detail else base

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        if str(executed_turn_uuid or "").strip():
            try:
                compact_turn_tool_messages_for_storage(
                    store=self.store,
                    session_id=msg.session_id,
                    turn_uuid=executed_turn_uuid,
                )
            except Exception:
                pass
        _trace_local(
            event_type="response_sent",
            payload={"ok": bool(str(reply or "").strip()), "elapsed_ms": elapsed_ms, "mode": "sync_direct"},
            started_at=t0,
        )
        _flush_trace_rows()
        return OclawGatewayResult(
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
            turn_uuid=str(executed_turn_uuid or ""),
        )


__all__ = ["OclawGateway", "OclawGatewayResult"]
