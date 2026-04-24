from __future__ import annotations

"""Agent 错误处理模块。

把 `Agent` 内的错误格式化逻辑下沉到此处，方便 manager/specialist 复用。
"""

from typing import Any
from oclaw.prompts import render_prompt


def format_ollama_failure_banner(*, lang: str, exc: BaseException) -> str:
    prompt_id = "fallback/ollama_failure.en.md" if (lang or "zh").startswith("en") else "fallback/ollama_failure.zh.md"
    return render_prompt(
        prompt_id,
        variables={"error_type": type(exc).__name__, "error_message": str(exc)},
        strict=True,
    )


def format_openai_transport_error(*, lang: str, exc: BaseException) -> str:
    blob = str(exc).lower()
    oversized_tool = ("30000" in blob or "input length" in blob) and ("range" in blob or "length" in blob)
    gemini_sig = "thought_signature" in blob
    if (lang or "zh").startswith("en"):
        if oversized_tool:
            return render_prompt(
                "fallback/openai_transport_oversized.en.md",
                variables={"error_type": type(exc).__name__, "error_message": str(exc)},
                strict=True,
            )
        tail = (
            "\n\n_Gemini 3 with tools: the API requires echoing `thought_signature` from each tool use in chat history. "
            "If this persists, update the app or use a model/SDK path that preserves provider-specific tool fields._"
            if gemini_sig
            else ""
        )
        return render_prompt(
            "fallback/openai_transport_error.en.md",
            variables={"error_type": type(exc).__name__, "error_message": str(exc), "extra_tail": tail},
            strict=True,
        )
    if oversized_tool:
        return render_prompt(
            "fallback/openai_transport_oversized.zh.md",
            variables={"error_type": type(exc).__name__, "error_message": str(exc)},
            strict=True,
        )
    tail = (
        "\n\n（**Gemini 3 + 工具调用**：接口要求把模型返回的 **thought_signature** 随该次 `tool_calls` 一并写回对话历史；"
        "首轮能跑工具、第二轮 400 多为丢失该字段。若已更新本应用仍报错，请确认代理/OpenAI 兼容层是否透传该字段。）"
        if gemini_sig
        else ""
    )
    return render_prompt(
        "fallback/openai_transport_error.zh.md",
        variables={"error_type": type(exc).__name__, "error_message": str(exc), "extra_tail": tail},
        strict=True,
    )


def safe_str(e: Any) -> str:
    try:
        return str(e)
    except Exception:
        return repr(e)


__all__ = ["format_ollama_failure_banner", "format_openai_transport_error", "safe_str"]
