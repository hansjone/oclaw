from __future__ import annotations

import json
import os
import uuid
from typing import Any, Optional
from collections.abc import Callable

from oclaw.platform.llm.transports.base import ChatModel, LLMResponse, LLMToolCall


class GoogleGeminiChatModel(ChatModel):
    """Native Google Gemini streaming transport (SSE), modeled after OpenClaw's google transport."""

    def __init__(self, *, model: str, api_key: str, base_url: str | None = None):
        self.model = (model or "").strip() or "gemini-2.5-pro"
        self.api_key = (api_key or "").strip()
        self.base_url = (base_url or "").strip() or "https://generativelanguage.googleapis.com/v1beta"
        if not self.api_key:
            raise RuntimeError("未设置 GOOGLE_API_KEY，无法使用 Gemini 原生接口")

    def _tool_decls_from_openai_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        decls: list[dict[str, Any]] = []
        for t in tools or []:
            if not isinstance(t, dict) or str(t.get("type") or "") != "function":
                continue
            fn = t.get("function")
            if not isinstance(fn, dict):
                continue
            name = str(fn.get("name") or "").strip()
            if not name:
                continue
            decls.append(
                {
                    "name": name,
                    "description": str(fn.get("description") or ""),
                    # OpenClaw uses `parametersJsonSchema`
                    "parametersJsonSchema": fn.get("parameters") if isinstance(fn.get("parameters"), dict) else {"type": "object"},
                }
            )
        return decls

    @staticmethod
    def _thinking_config_from_env() -> dict[str, Any] | None:
        enabled = str(os.getenv("AIA_GEMINI_THINKING") or "").strip().lower()
        if enabled in ("0", "false", "no", "off"):
            return {"includeThoughts": False}
        if enabled in ("1", "true", "yes", "on"):
            cfg: dict[str, Any] = {"includeThoughts": True}
            lvl = str(os.getenv("AIA_GEMINI_THINKING_LEVEL") or "").strip()
            if lvl:
                cfg["thinkingLevel"] = lvl
            bud = str(os.getenv("AIA_GEMINI_THINKING_BUDGET") or "").strip()
            if bud.isdigit():
                cfg["thinkingBudget"] = int(bud)
            return cfg
        return None

    @staticmethod
    def _parse_tool_result_payload(raw: Any) -> Any:
        if raw is None:
            return {}
        if isinstance(raw, (dict, list)):
            return raw
        s = str(raw or "").strip()
        if not s:
            return {}
        try:
            return json.loads(s)
        except Exception:
            return {"raw": s}

    @staticmethod
    def _openai_messages_to_gemini_contents(messages: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        system_parts: list[dict[str, Any]] = []
        contents: list[dict[str, Any]] = []

        def _append(role: str, parts: list[dict[str, Any]]) -> None:
            if not parts:
                return
            contents.append({"role": role, "parts": parts})

        for m in messages or []:
            if not isinstance(m, dict):
                continue
            role = str(m.get("role") or "")
            content = m.get("content")
            if role == "system":
                if isinstance(content, str) and content.strip():
                    system_parts.append({"text": content})
                continue
            if role == "user":
                parts: list[dict[str, Any]] = []
                if isinstance(content, str):
                    if content.strip():
                        parts.append({"text": content})
                elif isinstance(content, list):
                    for item in content:
                        if not isinstance(item, dict):
                            continue
                        if item.get("type") == "text" and str(item.get("text") or "").strip():
                            parts.append({"text": str(item.get("text") or "")})
                _append("user", parts)
                continue
            if role == "assistant":
                parts: list[dict[str, Any]] = []
                if isinstance(content, str) and content.strip():
                    parts.append({"text": content})
                _append("model", parts)
                continue
            if role == "tool":
                name = str(m.get("name") or "").strip() or str(m.get("tool_name") or m.get("toolName") or "").strip()
                payload = GoogleGeminiChatModel._parse_tool_result_payload(content)
                _append("user", [{"functionResponse": {"name": name or "tool", "response": payload}}])
                continue

        system_instruction = {"parts": system_parts} if system_parts else None
        return system_instruction, contents

    def _build_url(self) -> str:
        base = self._normalize_base_url_for_native_sse(self.base_url).rstrip("/")
        model_path = self.model
        if not model_path.startswith("models/") and not model_path.startswith("tunedModels/"):
            model_path = f"models/{model_path}"
        # Prefer header auth (OpenClaw-style); avoid forcing key into query string.
        return f"{base}/{model_path}:streamGenerateContent?alt=sse"

    @staticmethod
    def _normalize_base_url_for_native_sse(base_url: str) -> str:
        """Normalize unified gateway base_url for Gemini native SSE.

        Many unified gateways expose OpenAI-compat under `/v1/*`, but Gemini native endpoints
        are usually implemented under `/v1beta/*` semantics.
        """
        raw = str(base_url or "").strip()
        if not raw:
            return raw
        # Strip trailing slashes first.
        while raw.endswith("/"):
            raw = raw[:-1]
        # Common unified gateway layout: https://host/v1  -> https://host/v1beta
        if raw.lower().endswith("/v1"):
            return raw[:-3] + "/v1beta"
        # Some gateways keep an `/openai` suffix for compat endpoints.
        if raw.lower().endswith("/openai"):
            raw = raw[:-7]
            if raw.lower().endswith("/v1"):
                return raw[:-3] + "/v1beta"
            return raw
        return raw

    def _auth_headers(self) -> dict[str, str]:
        k = str(self.api_key or "").strip()
        if not k:
            return {}
        # If user stored a bearer token in the profile secret.
        if k.lower().startswith("bearer "):
            return {"authorization": k}
        # Gemini API supports x-goog-api-key; unified gateways often accept this too.
        return {"x-goog-api-key": k}

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> LLMResponse:
        system_instruction, contents = self._openai_messages_to_gemini_contents(messages)
        decls = self._tool_decls_from_openai_tools(tools)
        req: dict[str, Any] = {"contents": contents}
        if system_instruction is not None:
            req["systemInstruction"] = system_instruction
        if decls:
            req["tools"] = [{"functionDeclarations": decls}]
        thinking_cfg = self._thinking_config_from_env()
        if thinking_cfg is not None:
            req["generationConfig"] = {"thinkingConfig": thinking_cfg}

        url = self._build_url()
        try:
            import httpx
        except Exception as exc:
            raise RuntimeError("missing dependency: httpx") from exc

        thinking_parts: list[str] = []
        thinking_signature: str | None = None
        out_text: list[str] = []
        tool_calls: list[LLMToolCall] = []

        def _stream_once(stream_url: str) -> None:
            with httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
                with client.stream(
                    "POST",
                    stream_url,
                    json=req,
                    headers={
                        "Content-Type": "application/json",
                        "accept": "text/event-stream",
                        **self._auth_headers(),
                    },
                ) as r:
                    r.raise_for_status()
                    for line in r.iter_lines():
                        if not line or not str(line).startswith("data:"):
                            continue
                        data = str(line)[len("data:") :].strip()
                        if not data or data == "[DONE]":
                            continue
                        try:
                            chunk = json.loads(data)
                        except Exception:
                            continue
                        cands = chunk.get("candidates") if isinstance(chunk, dict) else None
                        if not isinstance(cands, list) or not cands:
                            continue
                        c0 = cands[0] if isinstance(cands[0], dict) else {}
                        content0 = c0.get("content") if isinstance(c0.get("content"), dict) else {}
                        parts = content0.get("parts") if isinstance(content0.get("parts"), list) else []
                        for p in parts:
                            if not isinstance(p, dict):
                                continue
                            if p.get("thought") is True:
                                txt = str(p.get("text") or "")
                                if txt:
                                    thinking_parts.append(txt)
                                sig = p.get("thoughtSignature")
                                if isinstance(sig, str) and sig:
                                    thinking_signature = sig
                                continue
                            fc = p.get("functionCall") if isinstance(p.get("functionCall"), dict) else None
                            if fc is not None:
                                name = str(fc.get("name") or "").strip()
                                args = fc.get("args") if isinstance(fc.get("args"), dict) else {}
                                tid = str(fc.get("id") or "") or f"call_{uuid.uuid4().hex}"
                                tool_calls.append(
                                    LLMToolCall(id=tid, name=name, arguments=args, thought_signature=thinking_signature)
                                )
                                continue
                            txt = str(p.get("text") or "")
                            if txt:
                                out_text.append(txt)
                                if on_token:
                                    on_token(txt)

        try:
            _stream_once(url)
        except Exception as exc:
            # If gateway returns 500 on /v1* SSE path, try /v1beta* fallback once.
            msg = str(exc or "").lower()
            if "500" in msg and "/v1/" in str(url).lower():
                alt = str(url).replace("/v1/", "/v1beta/")
                _stream_once(alt)
            else:
                raise

        return LLMResponse(
            content="".join(out_text),
            tool_calls=tool_calls,
            reasoning_content="".join(thinking_parts).strip(),
        )


__all__ = ["GoogleGeminiChatModel"]

