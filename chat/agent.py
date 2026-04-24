from __future__ import annotations

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

from oclaw.tools.base import ToolRegistry
from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.platform.llm.chat_models import (
    ChatModel,
    LLMResponse,
    LLMToolCall,
    OpenAIChatModel,
    RuleBasedChatModel,
    StaticTextChatModel,
    _normalize_image_b64_payload,
    build_default_model,
    gemini_openai_compat_client,
)
from oclaw.prompts.loader import render_prompt_for_lang
from oclaw.tools.tool_validation import validate_tool_arguments

logger = logging.getLogger(__name__)

SESSION_TITLE_MAX_LEN = 120
AGENT_CONTEXT_MESSAGES = 80

DEFAULT_SYSTEM_PROMPTS: dict[str, str] = {
    "zh": render_prompt_for_lang("runtime/default_system", "zh", strict=True),
    "en": render_prompt_for_lang("runtime/default_system", "en", strict=True),
}


class GenerationInterrupted(Exception):
    """用户请求中止当前生成过程。"""

@dataclass(frozen=True)
class AgentConfig:
    max_messages: int = AGENT_CONTEXT_MESSAGES
    max_tool_rounds: int = 8
    max_tool_workers: int = 8


class Agent:
    def __init__(
        self,
        store: SqliteStore,
        tools: ToolRegistry,
        model: Optional[ChatModel] = None,
        config: Optional[AgentConfig] = None,
        system_prompt: str | None = None,
        lang: str = "zh",
        llm_profile_mode: str | None = None,
    ):
        self.store = store
        self.tools = tools
        self.model = model or build_default_model()
        self.config = config or AgentConfig()
        self.lang = (lang or "zh").strip().lower()
        self._system_prompt_base = (system_prompt or DEFAULT_SYSTEM_PROMPTS.get(self.lang, DEFAULT_SYSTEM_PROMPTS["zh"])).strip()
        self.llm_profile_mode = ((llm_profile_mode or "").strip().lower() or None)
        self._last_turn_outcome: Any | None = None

    def _native_tools_sent_by_api(self) -> bool:
        """当前模型这一侧是否会把 tools 放进请求（与 ``llm.OpenAIChatModel._skip_tools`` 对齐）。"""
        m = self.model
        if isinstance(m, (RuleBasedChatModel, StaticTextChatModel)):
            return False
        if isinstance(m, OpenAIChatModel):
            return not bool(m._skip_tools)
        return False

    def _compose_system_prompt(self) -> str:
        """系统正文。工具 schema 始终通过原生 tools 字段下发，不再拼接到 prompt。"""
        return self._system_prompt_base

    def _format_ollama_failure_banner(self, exc: BaseException) -> str:
        # Backward compat wrapper; implementation lives in `src.chat.agent_errors`.
        from oclaw.chat.agent_errors import format_ollama_failure_banner

        return format_ollama_failure_banner(lang=self.lang, exc=exc)

    def _format_openai_transport_error(self, exc: BaseException) -> str:
        # Backward compat wrapper; implementation lives in `src.chat.agent_errors`.
        from oclaw.chat.agent_errors import format_openai_transport_error

        return format_openai_transport_error(lang=self.lang, exc=exc)

    def _invoke_tool(self, tc: LLMToolCall) -> tuple[dict[str, Any], int]:
        t0 = time.perf_counter()
        tool = self.tools.get(tc.name)
        if not tool:
            msg = f"Unregistered tool: {tc.name}" if self.lang.startswith("en") else f"未注册的工具: {tc.name}"
            return {"ok": False, "error": msg}, int((time.perf_counter() - t0) * 1000)

        ok, v_err = validate_tool_arguments(tool.parameters, tc.arguments)
        if not ok:
            msg = f"Invalid arguments: {v_err}" if self.lang.startswith("en") else f"参数不合法: {v_err}"
            return {"ok": False, "error": msg}, int((time.perf_counter() - t0) * 1000)

        try:
            result = tool.handler(tc.arguments)
            return result, int((time.perf_counter() - t0) * 1000)
        except Exception as e:
            if self.lang.startswith("en"):
                err = {"ok": False, "error": f"Tool execution error: {type(e).__name__}: {e}"}
            else:
                err = {"ok": False, "error": f"工具执行异常: {type(e).__name__}: {e}"}
            return err, int((time.perf_counter() - t0) * 1000)

    def _emit_progress(self, on_progress: Optional[Callable[[str], None]], en: str, zh: str) -> None:
        if on_progress:
            on_progress(en if self.lang.startswith("en") else zh)

    @staticmethod
    def _attachments_from_tool_result(result: Any) -> list[dict[str, Any]]:
        """Extract image/relay references from tool results for rendering."""
        if not isinstance(result, dict):
            return []
        out: list[dict[str, Any]] = []
        aid = str(result.get("attachment_id") or "").strip()
        if aid:
            out.append(
                {
                    "type": "image_ref",
                    "attachment_id": aid,
                    "name": str(result.get("name") or "generated-image"),
                    "mime": str(result.get("mime") or "image/png"),
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
                # Relay pointer payload (new protocol).
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
                if not r_aid:
                    continue
                out.append(
                    {
                        "type": "image_ref",
                        "attachment_id": r_aid,
                        "name": str(r.get("name") or "generated-image"),
                        "mime": str(r.get("mime") or "image/png"),
                        "bytes": r.get("bytes"),
                        "width": r.get("width"),
                        "height": r.get("height"),
                    }
                )
        # de-dup by attachment_id
        uniq: list[dict[str, Any]] = []
        seen: set[str] = set()
        for a in out:
            k = str(a.get("attachment_id") or a.get("pointer_uri") or "")
            if not k or k in seen:
                continue
            seen.add(k)
            uniq.append(a)
        return uniq

    def run_turn(
        self,
        session_id: str,
        user_text: str,
        attachments: list[dict[str, Any]] | None = None,
        on_progress: Optional[Callable[[str], None]] = None,
        on_token: Optional[Callable[[str], None]] = None,
        on_tool_ui: Optional[Callable[[str, dict[str, Any]], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
        *,
        workspace_owner_session_id: str | None = None,
        path_policy_tenant_id: str | None = None,
        path_policy_user_id: str | None = None,
        interaction_mode: str | None = None,
        selected_specialist: str | None = None,
    ) -> str:
        from oclaw.openclaw_runtime.gateway import OpenClawGateway
        from oclaw.openclaw_runtime.types import StandardMessage

        tenant_id = str(path_policy_tenant_id or "").strip()
        user_id = str(path_policy_user_id or "").strip()
        if not tenant_id or not user_id:
            try:
                owner = self.store.get_ui_session_owner(session_id=session_id)
            except Exception:
                owner = None
            if isinstance(owner, dict):
                tenant_id = tenant_id or str(owner.get("tenant_id") or "")
                user_id = user_id or str(owner.get("user_id") or "")

        session = self.store.get_session(session_id)
        if session and session.title in ("新会话", "New Chat"):
            title = user_text.strip().replace("\n", " ")
            if not title and attachments:
                title = str(attachments[0].get("name") or "New Chat")
            if title:
                self.store.rename_session(session_id, title[:SESSION_TITLE_MAX_LEN])

        self._emit_progress(
            on_progress,
            "Received. Working on your request…",
            "已收到，正在处理…",
        )

        meta: dict[str, Any] = {"tenant_id": tenant_id, "user_id": user_id}
        if workspace_owner_session_id:
            meta["workspace_owner_session_id"] = str(workspace_owner_session_id).strip()
        if str(interaction_mode or "").strip():
            meta["interaction_mode"] = str(interaction_mode).strip().lower()
        if str(selected_specialist or "").strip():
            meta["selected_specialist"] = str(selected_specialist).strip().lower()

        msg = StandardMessage(
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            role="member",
            channel="agent_turn",
            text=str(user_text or ""),
            attachments=list(attachments or []),
            metadata=meta,
        )
        gw = OpenClawGateway(store=self.store)
        try:
            res = gw.handle_turn(
                msg=msg,
                lang=self.lang,
                executor=self,
                on_token=on_token,
                on_progress=on_progress,
                on_tool_ui=on_tool_ui,
                should_stop=should_stop,
            )
        except RuntimeError as e:
            low = str(e).lower()
            if "interrupted" in low and "user" in low:
                raise GenerationInterrupted(str(e)) from e
            raise

        self._last_turn_outcome = getattr(self, "_last_turn_outcome", None)
        return str(res.reply_text or "")

    def _build_llm_messages(self, session_id: str) -> list[dict[str, Any]]:
        from oclaw.chat.agent_messages import build_llm_messages

        msgs = self.store.get_messages(session_id=session_id, limit=self.config.max_messages)
        return build_llm_messages(
            store_messages=msgs,
            system_prompt=self._compose_system_prompt(),
            model=self.model,
            lang=self.lang,
        )


__all__ = ["AgentConfig", "DEFAULT_SYSTEM_PROMPTS", "GenerationInterrupted", "Agent"]
