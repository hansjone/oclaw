from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any, Optional
from collections.abc import Callable, Iterable

from oclaw.platform.llm.transports.base import ChatModel, LLMResponse, LLMToolCall, normalize_image_b64_payload

logger = logging.getLogger(__name__)


def _as_dict(obj: Any) -> dict[str, Any] | None:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        try:
            d = obj.model_dump(mode="python")
            return d if isinstance(d, dict) else None
        except Exception:
            return None
    return None


def _collect_tool_calls_from_response_dict(resp: dict[str, Any]) -> list[LLMToolCall]:
    out: list[LLMToolCall] = []
    items = resp.get("output")
    if not isinstance(items, list):
        return out
    for it in items:
        d = _as_dict(it)
        if not d:
            continue
        if str(d.get("type") or "") in ("function_call", "tool_call"):
            call_id = str(d.get("call_id") or d.get("id") or "") or f"call_{uuid.uuid4().hex}"
            name = str(d.get("name") or "") or str((d.get("function") or {}).get("name") or "")
            args = d.get("arguments") or d.get("input") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {"_raw": args}
            if not isinstance(args, dict):
                args = {"_raw": args}
            out.append(LLMToolCall(id=call_id, name=name, arguments=args, thought_signature=None))
    return out


def parse_openai_responses_stream_events(
    events: Iterable[Any],
    *,
    on_token: Optional[Callable[[str], None]] = None,
) -> tuple[str, list[LLMToolCall], dict[str, Any] | None]:
    """Pure stream parser (offline-testable).

    Returns: (assembled_text, tool_calls, final_response_dict?)
    """
    parts: list[str] = []
    final_resp: dict[str, Any] | None = None
    for ev in events:
        d = _as_dict(ev) or {}
        typ = str(d.get("type") or "")
        # Text deltas
        if typ in ("response.output_text.delta", "response.output_text"):
            delta = d.get("delta")
            if delta is None:
                delta = d.get("text")
            s = str(delta or "")
            if s:
                parts.append(s)
                if on_token:
                    on_token(s)
            continue
        # Sometimes the SDK emits generic `response.delta` with nested segments.
        if typ == "response.delta":
            delta = d.get("delta")
            if isinstance(delta, dict):
                txt = delta.get("output_text")
                if isinstance(txt, str) and txt:
                    parts.append(txt)
                    if on_token:
                        on_token(txt)
            continue
        # Terminal response object
        if typ in ("response.completed", "response.complete", "response.done"):
            resp = d.get("response") or d.get("data") or d.get("result")
            final_resp = _as_dict(resp) or final_resp
            continue
        if typ == "response.created":
            continue
        # Some SDK versions yield the response object directly (no explicit event type).
        if d.get("output") is not None and d.get("id") is not None:
            final_resp = d

    text = "".join(parts)
    tool_calls = _collect_tool_calls_from_response_dict(final_resp) if final_resp else []
    return text, tool_calls, final_resp


class OpenAIResponsesModel(ChatModel):
    """OpenAI Responses API transport (OpenAI-compatible gateways may implement this surface)."""

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        thinking_mode_enabled: bool = False,
        reasoning_effort: str | None = None,
    ):
        self.model = (model or os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()
        self.api_key = (api_key or os.getenv("OPENAI_API_KEY") or "").strip()
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL") or "").strip() or None
        self.thinking_mode_enabled = bool(thinking_mode_enabled)
        eff = str(reasoning_effort or "").strip().lower()
        self.reasoning_effort = eff if eff in ("low", "medium", "high") else ""
        if not self.api_key:
            raise RuntimeError("未设置 OPENAI_API_KEY，无法使用 OpenAI Responses")
        try:
            from openai import OpenAI
        except Exception as e:
            raise RuntimeError("未安装 openai 依赖，请先 pip install -r requirements.txt") from e
        kw: dict[str, Any] = {"api_key": self.api_key}
        if self.base_url:
            kw["base_url"] = self.base_url
        self._client = OpenAI(**kw)

    @staticmethod
    def _normalize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Normalize to the strictest OpenAI-compatible `responses` shape:
        - input.messages[*].role MUST be "user"
        - input.messages[*].content MUST be a list (content blocks)
        - text blocks use {"type":"text","text":...}
        - image blocks use {"type":"image_url","image_url":{"url":"..."}} or {"type":"input_image","image_url":"..."} depending on gateway;
          we prefer the common "image_url" block here.
        """
        out: list[dict[str, Any]] = []
        for m in messages or []:
            if not isinstance(m, dict):
                continue
            role = str(m.get("role") or "user").strip().lower() or "user"
            content = m.get("content")
            norm_content: list[dict[str, Any]] = []
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "input_image":
                        mime = str(item.get("mime") or "image/jpeg").strip() or "image/jpeg"
                        b64 = normalize_image_b64_payload(item.get("image_base64") or item.get("data"))
                        if not b64:
                            continue
                        norm_content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
                        continue
                    if isinstance(item, dict) and item.get("type") in ("input_text", "text"):
                        t = str(item.get("text") or "").strip()
                        if t:
                            norm_content.append({"type": "text", "text": t})
                        continue
                    if isinstance(item, dict):
                        # Best-effort coerce unknown blocks into valid text blocks.
                        s = str(item.get("text") or "").strip()
                        if s:
                            norm_content.append({"type": "text", "text": s})
                        continue
                    s = str(item or "").strip()
                    if s:
                        norm_content.append({"type": "text", "text": s})
            elif isinstance(content, str):
                txt = content.strip()
                if txt:
                    norm_content.append({"type": "text", "text": txt})
            elif content is not None:
                s = str(content).strip()
                if s:
                    norm_content.append({"type": "text", "text": s})
            if not norm_content:
                # Keep shape valid even for empty messages.
                continue

            # Enforce role=user and preserve other roles via prefix tag.
            if role != "user":
                prefix = "assistant" if role == "assistant" else ("system" if role == "system" else role)
                norm_content.insert(0, {"type": "text", "text": f"[{prefix}]"})
            out.append({"role": "user", "content": norm_content})
        return out

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> LLMResponse:
        norm = self._normalize_messages(messages)
        # OpenAI-compatible gateways differ: some require input={"messages":[...]} with role=user only.
        stream_errors: list[str] = []
        b = str(self.base_url or "").strip().lower()
        force_disable = str(os.getenv("AIA_LLM_THINKING_FORCE_DISABLED") or "").strip().lower() in ("1", "true", "yes", "on")
        force_enable = str(os.getenv("AIA_LLM_THINKING_FORCE_ENABLED") or "").strip().lower() in ("1", "true", "yes", "on")
        mode_enabled = bool(getattr(self, "thinking_mode_enabled", False))
        extra_body: dict[str, Any] = {}
        if b and ("api.openai.com" not in b):
            if force_disable:
                extra_body["thinking"] = {"type": "disabled"}
            elif force_enable or mode_enabled:
                extra_body["thinking"] = {"type": "enabled"}
            else:
                # Default: disable thinking for non-official gateways unless explicitly enabled.
                if str(os.getenv("AIA_LLM_THINKING_DISABLED") or "1").strip().lower() in ("1", "true", "yes", "on"):
                    extra_body["thinking"] = {"type": "disabled"}
        thinking = {"extra_body": extra_body} if extra_body else {}
        reasoning_effort = str(getattr(self, "reasoning_effort", "") or "").strip().lower()
        if reasoning_effort not in ("low", "medium", "high"):
            reasoning_effort = ""
        stream_variants: list[dict[str, Any]] = [
            {
                **thinking,
                **({"reasoning_effort": reasoning_effort} if reasoning_effort else {}),
                "model": self.model,
                "input": {"messages": norm},
                "tools": tools or None,
                "stream": True,
            },
            {
                **thinking,
                **({"reasoning_effort": reasoning_effort} if reasoning_effort else {}),
                "model": self.model,
                "input": norm,
                "tools": tools or None,
                "stream": True,
            },
        ]
        try:
            for payload in stream_variants:
                try:
                    stream = self._client.responses.create(**payload)
                    text, tool_calls, final_resp = parse_openai_responses_stream_events(stream, on_token=on_token)
                    if (not text.strip()) and final_resp:
                        ot = final_resp.get("output_text")
                        if isinstance(ot, str) and ot.strip():
                            text = ot
                            if on_token:
                                on_token(text)
                    return LLMResponse(content=text, tool_calls=tool_calls)
                except Exception as exc:
                    emsg = str(exc)
                    # Fallback: provider thinking-mode replay contract.
                    if "reasoning_content" in emsg and "thinking mode" in emsg and "must be passed back" in emsg:
                        try:
                            forced = dict(payload)
                            eb = forced.get("extra_body") if isinstance(forced.get("extra_body"), dict) else {}
                            eb = dict(eb)
                            eb["thinking"] = {"type": "disabled"}
                            forced["extra_body"] = eb
                            forced.pop("reasoning_effort", None)
                            stream = self._client.responses.create(**forced)
                            text, tool_calls, final_resp = parse_openai_responses_stream_events(stream, on_token=on_token)
                            if (not text.strip()) and final_resp:
                                ot = final_resp.get("output_text")
                                if isinstance(ot, str) and ot.strip():
                                    text = ot
                                    if on_token:
                                        on_token(text)
                            return LLMResponse(content=text, tool_calls=tool_calls)
                        except Exception:
                            pass
                    stream_errors.append(emsg)
                    continue
            raise RuntimeError("; ".join(stream_errors) or "responses_stream_all_variants_failed")
        except Exception as exc:
            logger.info("responses stream failed; fallback to non-stream (%s)", exc)
            nonstream_errors: list[str] = []
            for payload in (
                {
                    **thinking,
                    **({"reasoning_effort": reasoning_effort} if reasoning_effort else {}),
                    "model": self.model,
                    "input": {"messages": norm},
                    "tools": tools or None,
                },
                {
                    **thinking,
                    **({"reasoning_effort": reasoning_effort} if reasoning_effort else {}),
                    "model": self.model,
                    "input": norm,
                    "tools": tools or None,
                },
            ):
                try:
                    resp = self._client.responses.create(**payload)
                    d = _as_dict(resp) or {}
                    text = str(d.get("output_text") or "")
                    tool_calls = _collect_tool_calls_from_response_dict(d)
                    if on_token and text:
                        on_token(text)
                    return LLMResponse(content=text, tool_calls=tool_calls)
                except Exception as e2:
                    emsg2 = str(e2)
                    if "reasoning_content" in emsg2 and "thinking mode" in emsg2 and "must be passed back" in emsg2:
                        try:
                            forced = dict(payload)
                            eb = forced.get("extra_body") if isinstance(forced.get("extra_body"), dict) else {}
                            eb = dict(eb)
                            eb["thinking"] = {"type": "disabled"}
                            forced["extra_body"] = eb
                            forced.pop("reasoning_effort", None)
                            resp = self._client.responses.create(**forced)
                            d = _as_dict(resp) or {}
                            text = str(d.get("output_text") or "")
                            tool_calls = _collect_tool_calls_from_response_dict(d)
                            if on_token and text:
                                on_token(text)
                            return LLMResponse(content=text, tool_calls=tool_calls)
                        except Exception:
                            pass
                    nonstream_errors.append(emsg2)
                    continue
            raise RuntimeError(
                "openai_responses_request_failed: "
                + " | ".join([str(exc)] + nonstream_errors[-2:])
            ) from exc


__all__ = ["OpenAIResponsesModel", "parse_openai_responses_stream_events"]

