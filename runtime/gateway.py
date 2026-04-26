from __future__ import annotations

import json
import os
import time
import uuid
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from oclaw.runtime.agents.factory import build_ephemeral_executor
from oclaw.runtime.hooks.eligibility_from_metadata import hook_eligibility_from_message_metadata
from oclaw.runtime.hooks_runtime import (
    get_active_hooks_config,
    initialize_hooks_runtime,
    trigger_hook_event,
)
from oclaw.runtime.relay_pointer import summarize_relay_ttl
from oclaw.runtime.skills import build_skill_manifest
from oclaw.runtime.prompt_prebuild import get_manager_prompt_prebuild
from oclaw.runtime.types import (
    OclawSessionContext,
    StandardMessage,
    normalize_interaction_mode,
    normalize_requested_specialist,
)
from oclaw.platform.config.paths import PROJECT_ROOT
from oclaw.prompts import render_prompt

from oclaw.runtime.command_parser import parse_internal_command
from oclaw.runtime.core.agent_execution import AgentCoreRunInput, build_memory_context, run_agent_core
from oclaw.runtime.memory_stage import after_turn_memory
from oclaw.runtime.router import decide_route
from oclaw.runtime.worker import ensure_worker_started
from oclaw.runtime.orchestration.trace import new_span_id, new_trace_id
from oclaw.runtime.chat.tool_runtime import compact_turn_tool_messages_for_storage

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


class OclawGateway:
    def __init__(self, *, store: Any):
        self.store = store

    @staticmethod
    def _parse_json_object(text: str) -> dict[str, Any] | None:
        t = str(text or "").strip()
        start = t.find("{")
        if start < 0:
            return None
        executed_turn_uuid = ""
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
        system_prompt = OclawGateway._sanitize_dynamic_system_prompt(raw.get("system_prompt"))
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

    def _maybe_generate_title_on_third_round(self, *, msg: StandardMessage, model: Any | None) -> None:
        """Generate title once on round-3 using user text only (no tools/reasoning context)."""
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

    def _manager_select_specialist(
        self,
        *,
        msg: StandardMessage,
        lang: str,
        executor: Any,
        memory_enabled: bool,
    ) -> tuple[str, str, dict[str, Any] | None, str, bool, bool | None, str, str, str]:
        model = getattr(executor, "model", None)
        if model is None or not callable(getattr(model, "chat", None)):
            return ("generalist", "manager_model_missing", None, "", False, None, "", "", "")
        try:
            registry = getattr(executor, "tools", None)
            base_url = str(getattr(model, "base_url", "") or "")
            if registry is None:
                return ("generalist", "manager_tools_missing", None, "", False, None, "", "", "")
            pack = get_manager_prompt_prebuild(
                store=self.store,
                registry=registry,
                base_url=base_url,
                memory_enabled=memory_enabled,
            )
            manager_context = str(pack.get("manager_context") or "")
            allowed_fixed = [str(x).strip().lower() for x in (pack.get("allowed_fixed") or []) if str(x).strip()]
            allowed_fixed_quoted = str(pack.get("allowed_fixed_quoted") or "")
            messages = [
                {
                    "role": "system",
                    "content": (
                        f"{manager_context}\n\n"
                        "Return exactly one compact JSON object with route.specialist, route.reason, and "
                        "dispatch.instruction_text. "
                        f"Allowed fixed specialists: {allowed_fixed_quoted}. "
                        "If route.specialist is NOT a fixed specialist, you MUST include dynamic_agent with "
                        "name/system_prompt/tool_policy(allow_tags/allow_tools)/reason."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"User request:\n{str(msg.text or '').strip()}\n\n"
                        "Return JSON only."
                    ),
                },
            ]
            resp = model.chat(messages, [], on_token=None)
            obj = self._parse_json_object(str(getattr(resp, "content", "") or ""))
            if not isinstance(obj, dict):
                return ("generalist", "manager_json_missing", None, "", False, None, "", "", "")
            route = obj.get("route") if isinstance(obj, dict) else None
            if not isinstance(route, dict):
                return ("generalist", "manager_route_missing", None, "", False, None, "", "", "")
            route_kind = str(route.get("kind") or "").strip().lower()
            raw_specialist = str(route.get("specialist") or "").strip().lower()
            fixed_set = set([str(x).strip().lower() for x in allowed_fixed if str(x).strip()])
            fixed = raw_specialist in fixed_set
            specialist = normalize_requested_specialist(raw_specialist) if fixed else raw_specialist
            reason = str(route.get("reason") or "").strip() or "manager_selected"
            dispatch = obj.get("dispatch") if isinstance(obj, dict) else None
            instruction_text = ""
            if isinstance(dispatch, dict):
                instruction_text = str(dispatch.get("instruction_text") or "").strip()
            if not instruction_text:
                return ("generalist", "manager_instruction_missing", None, "", False, None, "", "")
            need_wiki_inject: bool | None = None
            wiki_query = ""
            memory_write_text = ""
            post_reply_memory_write_text = ""
            route_need = route.get("need_wiki_inject") if isinstance(route, dict) else None
            if isinstance(route_need, bool):
                need_wiki_inject = bool(route_need)
            elif isinstance(dispatch, dict) and isinstance(dispatch.get("need_wiki_inject"), bool):
                need_wiki_inject = bool(dispatch.get("need_wiki_inject"))
            route_wq = route.get("wiki_query") if isinstance(route, dict) else None
            if isinstance(route_wq, str):
                wiki_query = str(route_wq).strip()
            elif isinstance(dispatch, dict) and isinstance(dispatch.get("wiki_query"), str):
                wiki_query = str(dispatch.get("wiki_query") or "").strip()
            wiki_query = wiki_query[:300]
            if isinstance(dispatch, dict) and isinstance(dispatch.get("memory_write_text"), str):
                memory_write_text = str(dispatch.get("memory_write_text") or "").strip()[:4000]
            if isinstance(dispatch, dict) and isinstance(dispatch.get("post_reply_memory_write_text"), str):
                post_reply_memory_write_text = str(dispatch.get("post_reply_memory_write_text") or "").strip()[:4000]
            if bool(need_wiki_inject) and not str(wiki_query or "").strip():
                return ("generalist", "manager_wiki_query_missing", None, instruction_text, False, False, "", "", "")
            # Allow manager to directly execute wiki/memory tasks.
            if route_kind == "manager_memory":
                if not memory_write_text:
                    return ("generalist", "manager_memory_write_missing", None, instruction_text, False, need_wiki_inject, wiki_query, "", post_reply_memory_write_text)
                return ("manager", reason or "manager_memory", None, instruction_text, True, need_wiki_inject, wiki_query, memory_write_text, post_reply_memory_write_text)
            dynamic_agent = self._parse_dynamic_agent(obj.get("dynamic_agent") if isinstance(obj, dict) else None)
            if specialist == "memory" and not memory_enabled:
                return ("generalist", "memory_disabled_fallback", None, instruction_text, False, need_wiki_inject, wiki_query, memory_write_text, post_reply_memory_write_text)
            if not fixed and dynamic_agent is None:
                return ("generalist", "dynamic_agent_invalid_fallback", None, instruction_text, False, need_wiki_inject, wiki_query, memory_write_text, post_reply_memory_write_text)
            return (specialist, reason, dynamic_agent, instruction_text, False, need_wiki_inject, wiki_query, memory_write_text, post_reply_memory_write_text)
        except Exception:
            return ("generalist", "manager_select_failed", None, "", False, None, "", "", "")

    def _manager_finalize_output(
        self,
        *,
        msg: StandardMessage,
        lang: str,
        executor: Any,
        specialist: str,
        specialist_reply: str,
        memory_enabled: bool,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> str:
        model = getattr(executor, "model", None)
        if model is None or not callable(getattr(model, "chat", None)):
            return str(specialist_reply or "")
        try:
            registry = getattr(executor, "tools", None)
            base_url = str(getattr(model, "base_url", "") or "")
            if registry is None:
                return str(specialist_reply or "")
            pack = get_manager_prompt_prebuild(
                store=self.store,
                registry=registry,
                base_url=base_url,
                memory_enabled=memory_enabled,
            )
            manager_context = str(pack.get("manager_context") or "")
            user_text = (
                "请基于以下信息输出最终答复。\n\n"
                f"原始用户问题:\n{str(msg.text or '').strip()}\n\n"
                f"已调用专家: {str(specialist or '').strip()}\n\n"
                f"专家结果:\n{str(specialist_reply or '').strip()}\n\n"
                "要求：保持简洁、准确，不要暴露内部流程。"
            )
            resp = model.chat(
                [{"role": "system", "content": manager_context}, {"role": "user", "content": user_text}],
                [],
                on_token=on_token,
            )
            final_text = str(getattr(resp, "content", "") or "").strip()
            return final_text or str(specialist_reply or "")
        except Exception:
            return str(specialist_reply or "")

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
                _trace_local(event_type="skill_manifest", payload={"base_url": base_url, **skill_stats}, started_at=t0)
        except Exception:
            pass

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
        requested_specialist = normalize_requested_specialist(base_metadata.get("selected_specialist"))
        if requested_specialist == "memory" and not memory_enabled:
            requested_specialist = "generalist"
        manager_specialist = requested_specialist
        dispatch_reason = "expert_direct"
        selected_executor = executor
        dynamic_agent: dict[str, Any] | None = None
        specialist_input_msg: StandardMessage | None = None
        manager_exec_msg: StandardMessage | None = None
        manager_instruction_text = ""
        manager_memory_mode = False
        manager_need_wiki_inject: bool | None = None
        manager_wiki_query = ""
        manager_memory_write_text = ""
        manager_post_reply_memory_write_text = ""

        if interaction_mode == "expert" and callable(specialist_executor_factory):
            try:
                selected_executor = specialist_executor_factory(requested_specialist)
            except Exception:
                selected_executor = executor
                dispatch_reason = "expert_factory_failed"

        if interaction_mode == "comprehensive":
            (
                manager_specialist,
                dispatch_reason,
                dynamic_agent,
                instruction_text,
                manager_memory_mode,
                manager_need_wiki_inject,
                manager_wiki_query,
                manager_memory_write_text,
                manager_post_reply_memory_write_text,
            ) = self._manager_select_specialist(
                msg=msg,
                lang=lang,
                executor=executor,
                memory_enabled=memory_enabled,
            )
            manager_instruction_text = str(instruction_text or "").strip()
            _trace_local(
                event_type="manager_decision",
                payload={
                    "interaction_mode": interaction_mode,
                    "manager_selected_specialist": str(manager_specialist or ""),
                    "manager_memory_mode": bool(manager_memory_mode),
                    "dispatch_reason": str(dispatch_reason or ""),
                    "instruction_chars": int(len(manager_instruction_text or "")),
                    "dynamic_agent_used": bool(dynamic_agent is not None),
                    "dynamic_agent_name": str((dynamic_agent or {}).get("name") or "") if isinstance(dynamic_agent, dict) else "",
                    "memory_write_chars": int(len(manager_memory_write_text or "")),
                    "post_reply_memory_write_chars": int(len(manager_post_reply_memory_write_text or "")),
                },
                started_at=t0,
            )
            if str(manager_instruction_text or "").strip() and not bool(manager_memory_mode):
                try:
                    assignment_title = "Task assignment" if str(lang or "").startswith("en") else "任务分配"
                    assignment_text = (
                        f"{assignment_title}\n"
                        f"specialist={str(manager_specialist or '')}\n"
                        f"instruction:\n{str(manager_instruction_text or '').strip()}"
                    )
                    self.store.add_message(
                        session_id=msg.session_id,
                        tenant_id=msg.tenant_id,
                        user_id=msg.user_id,
                        role="assistant",
                        content=assignment_text,
                        tool_calls=None,
                        event_type="reasoning",
                    )
                except Exception:
                    pass
            # Build specialist/dynamic executor and dispatch only manager instruction to it.
            specialist_input_msg = StandardMessage(
                session_id=msg.session_id,
                tenant_id=msg.tenant_id,
                user_id=msg.user_id,
                role=msg.role,
                channel=msg.channel,
                text=str(instruction_text or "").strip(),
                attachments=list(msg.attachments or []),
                metadata=(
                    {
                        **dict(base_metadata),
                        **(
                            {"need_wiki_inject": bool(manager_need_wiki_inject)}
                            if isinstance(manager_need_wiki_inject, bool)
                            else {}
                        ),
                        **(
                            {"wiki_query": str(manager_wiki_query or "")}
                            if str(manager_wiki_query or "").strip()
                            else {}
                        ),
                    }
                ),
            )
            manager_exec_msg = StandardMessage(
                session_id=msg.session_id,
                tenant_id=msg.tenant_id,
                user_id=msg.user_id,
                role=msg.role,
                channel=msg.channel,
                text=msg.text,
                attachments=list(msg.attachments or []),
                metadata=(
                    {
                        **dict(base_metadata),
                        **(
                            {"need_wiki_inject": bool(manager_need_wiki_inject)}
                            if isinstance(manager_need_wiki_inject, bool)
                            else {}
                        ),
                        **(
                            {"wiki_query": str(manager_wiki_query or "")}
                            if str(manager_wiki_query or "").strip()
                            else {}
                        ),
                    }
                ),
            )
            if manager_memory_mode:
                manager_specialist = "manager"
                selected_executor = executor
                dispatch_reason = dispatch_reason or "manager_memory"
            elif manager_specialist in {"ops", "generalist", "image", "memory"}:
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
                    if callable(specialist_executor_factory):
                        try:
                            selected_executor = specialist_executor_factory("generalist")
                        except Exception:
                            selected_executor = executor

        route_mode = "sync_direct"
        if manager_memory_mode:
            _trace_local(
                event_type="router_decision",
                payload={
                    "mode": route_mode,
                    "reason": "manager_memory_direct",
                    "interaction_mode": interaction_mode,
                    "requested_specialist": requested_specialist,
                    "manager_selected_specialist": manager_specialist,
                    "dispatch_reason": dispatch_reason,
                },
                started_at=t0,
            )
        else:
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
            )
        try:
            model = getattr(selected_executor, "model", None)
            tools = getattr(selected_executor, "tools", None)
            if model is None or tools is None:
                raise RuntimeError("executor missing model/tools")
            sys_prompt = str(getattr(selected_executor, "system_prompt", "") or "")
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
                (
                    StandardMessage(
                        session_id=msg.session_id,
                        tenant_id=msg.tenant_id,
                        user_id=msg.user_id,
                        role=msg.role,
                        channel=msg.channel,
                        text=str(manager_memory_write_text or manager_instruction_text or msg.text or ""),
                        attachments=list(msg.attachments or []),
                        metadata=(manager_exec_msg.metadata if manager_exec_msg is not None else dict(base_metadata)),
                    )
                    if manager_memory_mode
                    else (manager_exec_msg if manager_exec_msg is not None else msg)
                )
                if manager_memory_mode
                else (specialist_input_msg if (interaction_mode == "comprehensive" and specialist_input_msg is not None) else msg)
            )
            core_out = run_agent_core(
                store=self.store,
                data=AgentCoreRunInput(
                    msg=exec_msg,
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
                    max_attempts=_get_int_setting("AIA_OCLAW_MAX_ATTEMPTS", 2, 1, 5),
                    memory_context=memory_context,
                    # manager_memory writes to wiki/memory store; do not stream body to frontend.
                    on_token=(None if manager_memory_mode else (None if interaction_mode == "comprehensive" else on_token)),
                    on_progress=on_progress,
                    on_tool_ui=on_tool_ui,
                    should_stop=should_stop,
                    skill_binding_role=str(manager_specialist or "generalist"),
                    wire_policy_role="manager" if interaction_mode == "comprehensive" else str(requested_specialist),
                ),
            )
            executed_turn_uuid = str(getattr(core_out.outcome, "turn_uuid", "") or "")
            specialist_reply = str(core_out.outcome.final_text or "")
            if manager_memory_mode:
                # manager_memory: write memory silently, but keep dialog output independent.
                # User-facing reply comes from manager dispatch instruction_text.
                reply = str(manager_instruction_text or "").strip()
                if not reply:
                    reply = (
                        "已执行记忆写入。"
                        if not str(lang or "").startswith("en")
                        else "Memory write executed."
                    )
            elif interaction_mode == "comprehensive":
                reply = self._manager_finalize_output(
                    msg=msg,
                    lang=lang,
                    executor=executor,
                    specialist=manager_specialist,
                    specialist_reply=specialist_reply,
                    memory_enabled=memory_enabled,
                    on_token=on_token,
                )
            else:
                reply = specialist_reply
        except Exception as exc:
            base = render_prompt(
                "fallback/runtime_error.en.md" if str(lang or "").startswith("en") else "fallback/runtime_error.zh.md",
                strict=True,
            )
            detail = f"{type(exc).__name__}: {str(exc or '')}".strip().replace("\n", " ")[:400]
            reply = f"{base}\n(detail: {detail})" if detail else base

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        if interaction_mode == "comprehensive" and str(manager_post_reply_memory_write_text or "").strip():
            try:
                after_turn_memory(
                    store=self.store,
                    session_id=msg.session_id,
                    tenant_id=msg.tenant_id,
                    user_id=msg.user_id,
                    user_text=str(msg.text or ""),
                    assistant_text=str(manager_post_reply_memory_write_text or ""),
                    turn_uuid="",
                )
                _trace_local(
                    event_type="after_turn_memory",
                    payload={
                        "source": "manager_post_reply",
                        "post_reply_memory_write_chars": int(len(manager_post_reply_memory_write_text or "")),
                    },
                    started_at=t0,
                )
            except Exception:
                pass
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
        )


__all__ = ["OclawGateway", "OclawGatewayResult"]
