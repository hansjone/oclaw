from __future__ import annotations

"""Compatibility re-export layer.

The codebase imports `ChatModel/OpenAIChatModel/...` from this module.
Implementations live under `src.platform.llm.transports.*`.
"""

import os

from oclaw.platform.llm.tool_schema import shrink_openai_tools_payload_for_api
from oclaw.platform.llm.tool_schema import openai_tools_json_byte_length as _openai_tools_json_byte_length
from oclaw.platform.llm.transports.base import ChatModel, LLMResponse, LLMToolCall, normalize_image_b64_payload
from oclaw.platform.llm.transports.google_gemini_sse import GoogleGeminiChatModel
from oclaw.platform.llm.transports.openai_chat_completions import (
    OpenAIChatModel,
    _likely_gemini_openai_compat_base_url,
    _model_id_suggests_gemini,
)
from oclaw.platform.llm.transports.simple import RuleBasedChatModel, StaticTextChatModel

# Backward-compat alias used by `src/chat/agent.py`.
_normalize_image_b64_payload = normalize_image_b64_payload


def gemini_openai_compat_client(model: ChatModel) -> bool:
    if not isinstance(model, OpenAIChatModel):
        return False
    return _likely_gemini_openai_compat_base_url(getattr(model, "base_url", None)) or _model_id_suggests_gemini(
        getattr(model, "model", None)
    )


def build_default_model() -> ChatModel:
    mode = (os.getenv("AIA_ASSISTANT_MODE") or "").strip().lower()
    if mode == "rule":
        return RuleBasedChatModel()
    if mode == "ollama":
        try:
            from oclaw.runtime.agents.factory import DEFAULT_OLLAMA_BASE_URL, DEFAULT_OLLAMA_MODEL

            return OpenAIChatModel(model=DEFAULT_OLLAMA_MODEL, api_key="ollama", base_url=DEFAULT_OLLAMA_BASE_URL)
        except Exception:
            return RuleBasedChatModel()
    if mode == "openai" or mode == "":
        try:
            return OpenAIChatModel()
        except Exception:
            return RuleBasedChatModel()
    # Provider selection is normally handled via LLM profiles in `src/agents/factory.py`.
    return RuleBasedChatModel()


__all__ = [
    "ChatModel",
    "LLMResponse",
    "LLMToolCall",
    "OpenAIChatModel",
    "GoogleGeminiChatModel",
    "RuleBasedChatModel",
    "StaticTextChatModel",
    "build_default_model",
    "gemini_openai_compat_client",
    "normalize_image_b64_payload",
    "_normalize_image_b64_payload",
    "shrink_openai_tools_payload_for_api",
    "_openai_tools_json_byte_length",
]

