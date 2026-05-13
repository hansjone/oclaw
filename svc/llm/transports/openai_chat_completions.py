from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Any, Optional
from collections.abc import Callable

from svc.llm.tool_schema import complete_openai_tools_wire_parameters
from svc.llm.transports.base import ChatModel, LLMResponse, LLMToolCall, normalize_image_b64_payload, coerce_thought_signature_for_storage

logger = logging.getLogger(__name__)


def _likely_gemini_openai_compat_base_url(url: str | None) -> bool:
    if not url:
        return False
    u = url.lower()
    return "generativelanguage.googleapis.com" in u or "aiplatform.googleapis.com" in u


def _model_id_suggests_gemini(model: str | None) -> bool:
    return "gemini" in (model or "").lower()


def _is_minimax_compat(model: str | None, base_url: str | None) -> bool:
    m = str(model or "").strip().lower()
    b = str(base_url or "").strip().lower()
    return ("minimax" in m) or ("minimax" in b)


def _truthy_env(name: str, default: str = "") -> bool:
    v = os.getenv(name)
    if v is None:
        v = default
    return str(v or "").strip().lower() in ("1", "true", "yes", "on")


def _should_disable_thinking(base_url: str | None) -> bool:
    # Some OpenAI-compatible gateways enable "thinking" mode and require replaying
    # reasoning_content in subsequent turns. When the client does not preserve it,
    # the gateway returns HTTP 400. Allow disabling thinking at request level.
    #
    # Safety: do NOT send unknown fields to official OpenAI endpoints by default.
    if _truthy_env("AIA_LLM_THINKING_FORCE_DISABLED", "0"):
        return True
    if _truthy_env("AIA_LLM_THINKING_FORCE_ENABLED", "0"):
        return False
    b = str(base_url or "").strip().lower()
    if not b:
        return False
    if "api.openai.com" in b:
        return False
    # Default-on for non-official OpenAI-compatible gateways.
    return _truthy_env("AIA_LLM_THINKING_DISABLED", "1")


def _should_enable_thinking(base_url: str | None, *, thinking_mode_enabled: bool = False) -> bool:
    if _truthy_env("AIA_LLM_THINKING_FORCE_ENABLED", "0"):
        return True
    if _truthy_env("AIA_LLM_THINKING_FORCE_DISABLED", "0"):
        return False
    if not bool(thinking_mode_enabled):
        return False
    b = str(base_url or "").strip().lower()
    if not b:
        return False
    if "api.openai.com" in b:
        return False
    return True


def _should_force_text_only_messages(base_url: str | None) -> bool:
    del base_url
    # Opt-in only. Avoid hard-coding vendor/domain specific heuristics.
    return _truthy_env("AIA_OPENAI_FORCE_TEXT_CONTENT", "0")


def _multimodal_proactive_downgrade_enabled() -> bool:
    raw = str(os.getenv("AIA_OPENAI_MULTIMODAL_PROACTIVE_DOWNGRADE") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _text_only_multimodal_substrings() -> tuple[str, ...]:
    raw = os.getenv("AIA_OPENAI_TEXT_ONLY_MULTIMODAL_SUBSTRINGS")
    if raw is None:
        return ("deepseek",)
    s = str(raw).strip().lower()
    if s in {"", "-", "none", "off"}:
        return ()
    return tuple(part.strip().lower() for part in str(raw).split(",") if part.strip())


def _messages_contain_list_with_image(messages: list[dict[str, Any]]) -> bool:
    for m in messages or []:
        if not isinstance(m, dict):
            continue
        c = m.get("content")
        if not isinstance(c, list):
            continue
        for item in c:
            if not isinstance(item, dict):
                continue
            typ = str(item.get("type") or "").strip().lower()
            if typ in ("image_url", "input_image"):
                return True
    return False


def _deepseek_strict_tools_enabled(*, base_url: str | None, model: str | None) -> bool:
    """Whether to set ``strict: true`` on each OpenAI-style ``tools[].function`` for DeepSeek.

    DeepSeek documents strict tool output in
    https://api-docs.deepseek.com/zh-cn/guides/tool_calls :
    each ``function`` should include ``\"strict\": true`` (Beta; also needs ``/beta`` base URL
    and JSON Schema rules on the provider side). Opt out with ``AIA_DEEPSEEK_STRICT_TOOL_MODE=0``.
    """
    raw = str(os.getenv("AIA_DEEPSEEK_STRICT_TOOL_MODE") or "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    hay = f"{base_url or ''} {model or ''}".lower()
    return "deepseek" in hay


def _apply_deepseek_strict_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    """Return a shallow-copied tools list with ``function.strict: true`` on each function tool."""
    if not tools:
        return tools
    out: list[dict[str, Any]] = []
    for raw in tools:
        if not isinstance(raw, dict):
            out.append(raw)  # type: ignore[arg-type]
            continue
        if str(raw.get("type") or "").strip().lower() != "function":
            out.append(dict(raw))
            continue
        t = dict(raw)
        fn = t.get("function")
        if isinstance(fn, dict):
            fn2 = dict(fn)
            fn2["strict"] = True
            t["function"] = fn2
        else:
            t["function"] = {"strict": True}
        out.append(t)
    return out


def _should_proactively_downgrade_multimodal_messages(
    messages: list[dict[str, Any]],
    *,
    model: str | None,
    base_url: str | None,
) -> bool:
    if _should_force_text_only_messages(base_url):
        return _messages_contain_list_with_image(messages)
    if not _multimodal_proactive_downgrade_enabled():
        return False
    if not _messages_contain_list_with_image(messages):
        return False
    parts = _text_only_multimodal_substrings()
    if not parts:
        return False
    hay = f"{model or ''} {base_url or ''}".lower()
    return any(p and p in hay for p in parts)


def _wire_error_message(exc: BaseException) -> str:
    chunks: list[str] = [str(exc)]
    em = getattr(exc, "message", None)
    if isinstance(em, str) and em.strip():
        chunks.append(em)
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        try:
            chunks.append(json.dumps(body, ensure_ascii=False, default=str))
        except Exception:
            chunks.append(repr(body))
    elif isinstance(body, str) and body.strip():
        chunks.append(body)
    resp = getattr(exc, "response", None)
    if resp is not None:
        t = ""
        try:
            rt = getattr(resp, "text", "")
            if isinstance(rt, str):
                t = rt
        except Exception:
            pass
        if not t.strip():
            try:
                ct = getattr(resp, "content", None)
                if isinstance(ct, (bytes, bytearray)):
                    t = bytes(ct).decode("utf-8", errors="replace")
            except Exception:
                pass
        if t.strip():
            chunks.append(t)
    inner = getattr(exc, "__cause__", None)
    if inner is not None:
        chunks.append(str(inner))
    return "\n".join(chunks)


def _is_text_only_gateway_error(msg: str) -> bool:
    m = str(msg or "").strip().lower()
    if not m:
        return False
    if "unknown variant image_url" in m:
        return True
    if "image_url" in m and "expected text" in m:
        return True
    if "failed to deserialize" in m and ("expected text" in m or "unknown variant image_url" in m):
        return True
    if "deserialize" in m and "image_url" in m and ("expected text" in m or "messages[" in m):
        return True
    if "invalid_request_error" in m and ("image_url" in m or "expected text" in m):
        return True
    return False


def _flatten_message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content or "")
    parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            if item.strip():
                parts.append(item)
            continue
        if not isinstance(item, dict):
            continue
        typ = str(item.get("type") or "").strip().lower()
        if typ in ("text", "input_text"):
            txt = str(item.get("text") or item.get("content") or "").strip()
            if txt:
                parts.append(txt)
            continue
        if typ in ("image_url", "input_image"):
            # Proactive / forced text-only path without OCR injection (or OCR disabled).
            parts.append(
                "【图片】本消息含图片，但当前以纯文本发往上游模型，像素未传入；"
                "若需要图中细节，请改用支持多模态的模型或开启看图 OCR 降级通道。"
            )
            continue
    return "\n".join([p for p in parts if p]).strip()


def _multimodal_downgrade_ocr_enabled() -> bool:
    """When True, text-only downgrade replaces image blocks with OCR text via AIA_OCR_* lane."""
    return str(os.getenv("AIA_MULTIMODAL_DOWNGRADE_OCR") or "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _image_block_to_url(item: dict[str, Any]) -> str | None:
    typ = str(item.get("type") or "").strip().lower()
    if typ == "image_url":
        u = item.get("image_url")
        if isinstance(u, dict):
            s = str(u.get("url") or "").strip()
            return s or None
        if isinstance(u, str) and u.strip():
            return u.strip()
    if typ == "input_image":
        b64 = normalize_image_b64_payload(item.get("image_base64") or item.get("data"))
        mime = str(item.get("mime") or "image/jpeg").strip() or "image/jpeg"
        if b64:
            return f"data:{mime};base64,{b64}"
    return None


def _message_list_contains_image_block(content: Any) -> bool:
    if not isinstance(content, list):
        return False
    for item in content:
        if not isinstance(item, dict):
            continue
        typ = str(item.get("type") or "").strip().lower()
        if typ in ("image_url", "input_image"):
            return True
    return False


def _downgrade_ocr_wrap_for_llm(ocr_text: str) -> str:
    """User-facing copy injected into the main model when multimodal was OCR-downgraded to text."""
    head = (
        "【图片内容·OCR】当前主对话模型仅接收纯文本，无法直接读图；"
        "下面是由独立看图通道从用户图片中转写提取的正文。请把它和用户的文字问题一起当作依据来回答；"
        "转写可能有漏字、错行或与截图不完全一致，重要结论可请用户核对原图或补充说明。"
    )
    return f"{head}\n\n{ocr_text.strip()}"


def _flatten_message_content_for_text_gateway(content: Any) -> str:
    """Flatten list content to a string; image blocks may become OCR text when configured."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content or "")
    if _multimodal_downgrade_ocr_enabled() and _message_list_contains_image_block(content):
        try:
            from svc.llm.image_ocr_client import (
                VISION_OCR_EXTRACT_PROMPT_ZH,
                send_ocr_image_messages,
                vision_llm_backend_status,
            )
        except Exception:
            return _flatten_message_content_to_text(content)
        if vision_llm_backend_status().get("ok"):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    if item.strip():
                        parts.append(item)
                    continue
                if not isinstance(item, dict):
                    continue
                typ = str(item.get("type") or "").strip().lower()
                if typ in ("image_url", "input_image"):
                    url = _image_block_to_url(item)
                    if not url:
                        parts.append(
                            "【图片】无法从本消息中还原图片数据，图中细节未传入本轮模型；"
                            "若作答需要像素级信息，请提示用户重发或改用支持多模态的模型配置。"
                        )
                        continue
                    try:
                        out = send_ocr_image_messages(images=[url], prompt=VISION_OCR_EXTRACT_PROMPT_ZH)
                    except Exception as exc:
                        parts.append(
                            f"【图片】独立看图通道 OCR 调用异常（{type(exc).__name__}），"
                            "本张图的正文未能写入对话；可请用户改述图中要点或稍后重试。"
                        )
                        continue
                    if not out.get("ok"):
                        err = str(out.get("error") or "unknown")
                        parts.append(
                            f"【图片】看图通道返回失败（{err}），本张图未转成文字；"
                            "请据用户文字说明作答，或提示检查 OCR 配置/重发图片。"
                        )
                        continue
                    t = str(out.get("text") or "").strip()
                    if not t:
                        parts.append(
                            "【图片】看图通道未返回有效文字（可能模型拒识或图不清晰）。"
                            "请提示用户补充文字说明或重发更清晰的截图。"
                        )
                    else:
                        parts.append(_downgrade_ocr_wrap_for_llm(t))
                    continue
                if typ in ("text", "input_text"):
                    txt = str(item.get("text") or item.get("content") or "").strip()
                    if txt:
                        parts.append(txt)
                    continue
            return "\n\n".join([p for p in parts if p]).strip()
    return _flatten_message_content_to_text(content)


def _normalize_messages_for_text_only_gateway(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages or []:
        if not isinstance(m, dict):
            continue
        mm = dict(m)
        if isinstance(mm.get("content"), list):
            mm["content"] = _flatten_message_content_for_text_gateway(mm.get("content"))
        out.append(mm)
    return out


def _find_thought_signature_in_obj(o: Any) -> str | None:
    if isinstance(o, dict):
        for k in ("thought_signature", "thoughtSignature"):
            v = o.get(k)
            if v is not None:
                coerced = coerce_thought_signature_for_storage(v)
                if coerced is not None:
                    return coerced
        for v in o.values():
            found = _find_thought_signature_in_obj(v)
            if found is not None:
                return found
    elif isinstance(o, list):
        for v in o:
            found = _find_thought_signature_in_obj(v)
            if found is not None:
                return found
    return None


def _extract_thought_signature_from_message_tool_call(tc: Any) -> str | None:
    if hasattr(tc, "model_dump"):
        try:
            d = tc.model_dump(mode="python")
            ec = d.get("extra_content")
            if isinstance(ec, dict):
                g = ec.get("google")
                if isinstance(g, dict) and "thought_signature" in g:
                    return coerce_thought_signature_for_storage(g.get("thought_signature"))
        except Exception:
            pass
    ec = getattr(tc, "extra_content", None)
    if isinstance(ec, dict):
        g = ec.get("google")
        if isinstance(g, dict) and "thought_signature" in g:
            return coerce_thought_signature_for_storage(g.get("thought_signature"))
    return _extract_thought_signature_from_tool_delta(tc)


def _extract_thought_signature_from_tool_delta(tc: Any) -> str | None:
    for attr in ("thought_signature", "thoughtSignature"):
        v = getattr(tc, attr, None)
        if v is not None:
            return coerce_thought_signature_for_storage(v)
    extra = getattr(tc, "model_extra", None)
    if isinstance(extra, dict):
        for k in ("thought_signature", "thoughtSignature"):
            ev = extra.get(k)
            if ev is not None:
                return coerce_thought_signature_for_storage(ev)
    pyd_ex = getattr(tc, "__pydantic_extra__", None)
    if isinstance(pyd_ex, dict):
        for k in ("thought_signature", "thoughtSignature"):
            ev = pyd_ex.get(k)
            if ev is not None:
                return coerce_thought_signature_for_storage(ev)
    if hasattr(tc, "model_dump"):
        try:
            found = _find_thought_signature_in_obj(tc.model_dump(mode="python"))
            if found is not None:
                return found
        except Exception:
            pass
    return None


class OpenAIChatModel(ChatModel):
    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        thinking_mode_enabled: bool = False,
        reasoning_effort: str | None = None,
    ):
        self.model = model or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self.thinking_mode_enabled = bool(thinking_mode_enabled)
        eff = str(reasoning_effort or "").strip().lower()
        self.reasoning_effort = eff if eff in ("low", "medium", "high") else ""

        if not self.api_key:
            raise RuntimeError("未设置 OPENAI_API_KEY，无法使用 OpenAI 模型")

        try:
            from openai import OpenAI
        except Exception as e:
            raise RuntimeError("未安装 openai 依赖，请先 pip install -r requirements.txt") from e

        client_kwargs: dict[str, Any] = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        self._client = OpenAI(**client_kwargs)
        self._skip_tools: bool = False

    def _create_chat_completion(self, norm_msgs: list[dict[str, Any]], tools: list[dict[str, Any]], *, stream: bool):
        # replay_policy/tool_wire_policy live in sibling modules; import lazily to avoid cycles.
        try:
            from svc.llm.replay_policy import apply_replay_policy_to_messages, resolve_replay_policy

            policy = resolve_replay_policy(self.base_url, self.model)
            if policy.enabled:
                norm_msgs = apply_replay_policy_to_messages(norm_msgs, policy)
        except Exception as exc:
            logger.warning("replay_policy apply failed (%s); continuing without rewrite", exc)

        minimax_compat = _is_minimax_compat(self.model, self.base_url)
        use_tools = bool(tools)
        cleaned_msgs: list[dict[str, Any]] = []
        for m in norm_msgs or []:
            if not isinstance(m, dict):
                continue
            role = str(m.get("role") or "")
            if minimax_compat and role == "assistant" and isinstance(m.get("tool_calls"), list):
                # MiniMax OpenAI-compat can reject long-history tool_use/tool_result replays.
                # Keep text semantics, but remove historical wire-level tool_calls.
                mm = dict(m)
                mm.pop("tool_calls", None)
                cleaned_msgs.append(mm)
                continue
            if minimax_compat and role == "tool":
                # Downgrade history tool_result rows to plain assistant text context,
                # avoiding strict tool_result sequence validation on replay.
                tcid = str(m.get("tool_call_id") or m.get("call_id") or "").strip()
                tname = str(m.get("name") or "").strip()
                raw = str(m.get("content") or "")
                prefix = "[tool_result replay]"
                if tname:
                    prefix += f" name={tname}"
                if tcid:
                    prefix += f" id={tcid}"
                cleaned_msgs.append({"role": "assistant", "content": f"{prefix}\n{raw}".strip()})
                continue
            if role == "tool":
                mm = dict(m)
                for k in ("tool_call_id", "call_id"):
                    if k in mm:
                        v = mm.get(k)
                        try:
                            sv = str(v).strip() if v is not None else ""
                        except Exception:
                            sv = ""
                        if not sv:
                            mm.pop(k, None)
                        else:
                            mm[k] = sv
                cleaned_msgs.append(mm)
            else:
                cleaned_msgs.append(m)

        msgs_wire = cleaned_msgs
        if _should_force_text_only_messages(self.base_url) or _should_proactively_downgrade_multimodal_messages(
            cleaned_msgs,
            model=self.model,
            base_url=self.base_url,
        ):
            msgs_wire = _normalize_messages_for_text_only_gateway(cleaned_msgs)
        kwargs: dict[str, Any] = {"model": self.model, "messages": msgs_wire, "stream": stream}
        if _should_enable_thinking(self.base_url, thinking_mode_enabled=bool(getattr(self, "thinking_mode_enabled", False))):
            extra_body = kwargs.get("extra_body") if isinstance(kwargs.get("extra_body"), dict) else {}
            extra_body = dict(extra_body)
            extra_body["thinking"] = {"type": "enabled"}
            kwargs["extra_body"] = extra_body
            eff = str(getattr(self, "reasoning_effort", "") or "").strip().lower()
            if eff in ("low", "medium", "high"):
                kwargs["reasoning_effort"] = eff
        elif _should_disable_thinking(self.base_url):
            extra_body = kwargs.get("extra_body") if isinstance(kwargs.get("extra_body"), dict) else {}
            extra_body = dict(extra_body)
            extra_body["thinking"] = {"type": "disabled"}
            kwargs["extra_body"] = extra_body
        if use_tools:
            try:
                from svc.config.paths import db_path
                from svc.persistence.sqlite_store import SqliteStore
                from runtime.tools.exposure_plan import build_llm_tools_plan

                plan = build_llm_tools_plan(
                    store=SqliteStore(db_path()),
                    role="",
                    base_url=self.base_url,
                    max_json_bytes=_default_max_openai_tools_json_bytes(self.base_url),
                    include_mcp=False,
                    preview_internal=False,
                    raw_openai_tools_override=tools,
                )
                kwargs["tools"] = plan.tools_wired
            except Exception:
                kwargs["tools"] = complete_openai_tools_wire_parameters(tools)
        if use_tools and _deepseek_strict_tools_enabled(base_url=self.base_url, model=self.model):
            tw = kwargs.get("tools")
            if isinstance(tw, list):
                kwargs["tools"] = _apply_deepseek_strict_tools(tw)
        try:
            return self._client.chat.completions.create(**kwargs)
        except Exception as exc:
            msg = _wire_error_message(exc)
            if _is_text_only_gateway_error(msg) and isinstance(kwargs.get("messages"), list):
                kwargs["messages"] = _normalize_messages_for_text_only_gateway(kwargs["messages"])
                return self._client.chat.completions.create(**kwargs)
            if "reasoning_content" in msg and "thinking mode" in msg and "must be passed back" in msg:
                # Provider requires replaying assistant.reasoning_content in thinking mode.
                # As a safety fallback, force-disable thinking and retry once.
                extra_body = kwargs.get("extra_body") if isinstance(kwargs.get("extra_body"), dict) else {}
                extra_body = dict(extra_body)
                extra_body["thinking"] = {"type": "disabled"}
                kwargs["extra_body"] = extra_body
                kwargs.pop("reasoning_effort", None)
                return self._client.chat.completions.create(**kwargs)
            raise

    def _llm_response_from_completion(self, completion: Any, *, on_token: Optional[Callable[[str], None]]) -> LLMResponse:
        msg = completion.choices[0].message
        reasoning_parts = getattr(msg, "reasoning_content", None) or ""
        reasoning_text = str(reasoning_parts).strip() if reasoning_parts else ""
        content = msg.content or ""
        if on_token:
            if reasoning_text:
                on_token(reasoning_text)
            if content:
                on_token(content)

        tool_calls: list[LLMToolCall] = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                tid = str(getattr(tc, "id", "") or "")
                fn = getattr(tc, "function", None)
                name = str(fn.name) if fn and getattr(fn, "name", None) else ""
                args_raw = str(fn.arguments) if fn and getattr(fn, "arguments", None) is not None else "{}"
                if not name and not tid:
                    continue
                if not tid:
                    tid = f"call_{uuid.uuid4().hex}"
                try:
                    args = json.loads(args_raw)
                except json.JSONDecodeError:
                    args = {"_raw": args_raw}
                sig = _extract_thought_signature_from_message_tool_call(tc)
                if sig is None and fn is not None:
                    sig = _extract_thought_signature_from_tool_delta(fn)
                tool_calls.append(LLMToolCall(id=tid, name=name, arguments=args, thought_signature=sig))
        return LLMResponse(content=content, tool_calls=tool_calls, reasoning_content=reasoning_text)

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> LLMResponse:
        # Normalize input_image to image_url.
        norm_msgs = []
        for m in messages:
            if m.get("role") == "user" and isinstance(m.get("content"), list):
                norm_content = []
                for item in m["content"]:
                    if isinstance(item, dict) and item.get("type") == "input_image":
                        mime = str(item.get("mime") or "image/jpeg").strip() or "image/jpeg"
                        b64 = normalize_image_b64_payload(item.get("image_base64") or item.get("data"))
                        if not b64:
                            continue
                        norm_content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
                    else:
                        norm_content.append(item)
                norm_msgs.append({"role": m["role"], "content": norm_content})
            else:
                norm_msgs.append(m)

        try:
            stream = self._create_chat_completion(norm_msgs, tools, stream=True)
        except Exception as exc:
            logger.info("Streaming chat completion failed; fallback to non-stream (%s)", exc)
            completion = self._create_chat_completion(norm_msgs, tools, stream=False)
            return self._llm_response_from_completion(completion, on_token=on_token)

        content_parts: list[str] = []
        tool_acc: dict[int, dict[str, Any]] = {}
        reasoning_parts: list[str] = []

        def _consume_stream(stream_obj: Any) -> None:
            nonlocal content_parts, tool_acc, reasoning_parts
            for chunk in stream_obj:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                rc = getattr(delta, "reasoning_content", None) or ""
                if rc:
                    reasoning_parts.append(rc)
                    if on_token:
                        on_token(rc)
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = int(tc.index)
                        slot = tool_acc.setdefault(idx, {"id": None, "name": None, "arguments": "", "thought_signature": None})
                        if tc.id:
                            slot["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                slot["name"] = tc.function.name
                            if tc.function.arguments:
                                slot["arguments"] = f"{slot['arguments']}{tc.function.arguments}"
                        sig = _extract_thought_signature_from_message_tool_call(tc)
                        if sig is None:
                            sig = _extract_thought_signature_from_tool_delta(tc)
                        if sig is None and tc.function is not None:
                            sig = _extract_thought_signature_from_tool_delta(tc.function)
                        if sig is not None:
                            slot["thought_signature"] = sig
                if delta.content:
                    content_parts.append(delta.content)
                    if on_token:
                        on_token(delta.content)

        try:
            _consume_stream(stream)
        except Exception:
            raise

        content = "".join(content_parts)
        reasoning_text = "".join(reasoning_parts).strip()

        tool_calls: list[LLMToolCall] = []
        for idx in sorted(tool_acc.keys()):
            slot = tool_acc[idx]
            tid = slot.get("id") or ""
            name = slot.get("name") or ""
            args_raw = slot.get("arguments") or "{}"
            if not name and not tid:
                continue
            if not tid:
                tid = f"call_{uuid.uuid4().hex}"
            try:
                args = json.loads(args_raw)
            except json.JSONDecodeError:
                args = {"_raw": args_raw}
            ts_raw = slot.get("thought_signature")
            tsig = coerce_thought_signature_for_storage(ts_raw) if ts_raw is not None else None
            tool_calls.append(LLMToolCall(id=str(tid), name=str(name), arguments=args, thought_signature=tsig))

        return LLMResponse(content=content, tool_calls=tool_calls, reasoning_content=reasoning_text)


__all__ = [
    "OpenAIChatModel",
    "_likely_gemini_openai_compat_base_url",
    "_model_id_suggests_gemini",
    "_deepseek_strict_tools_enabled",
    "_apply_deepseek_strict_tools",
]


def _default_max_openai_tools_json_bytes(base_url: str | None) -> int | None:
    u = str(base_url or "").strip().lower()
    if not u:
        return None
    # Conservative caps for some OpenAI-compatible gateways.
    if "dashscope" in u or "aliyuncs" in u:
        return 28_000
    return None

