from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Any, Optional
from collections.abc import Callable

from oclaw.platform.llm.transports.base import ChatModel, LLMResponse, LLMToolCall, normalize_image_b64_payload, coerce_thought_signature_for_storage

logger = logging.getLogger(__name__)


def _likely_gemini_openai_compat_base_url(url: str | None) -> bool:
    if not url:
        return False
    u = url.lower()
    return "generativelanguage.googleapis.com" in u or "aiplatform.googleapis.com" in u


def _model_id_suggests_gemini(model: str | None) -> bool:
    return "gemini" in (model or "").lower()


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
    ):
        self.model = model or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")

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
            from oclaw.platform.llm.replay_policy import apply_replay_policy_to_messages, resolve_replay_policy

            policy = resolve_replay_policy(self.base_url, self.model)
            if policy.enabled:
                norm_msgs = apply_replay_policy_to_messages(norm_msgs, policy)
        except Exception as exc:
            logger.warning("replay_policy apply failed (%s); continuing without rewrite", exc)

        use_tools = bool(tools)
        cleaned_msgs: list[dict[str, Any]] = []
        for m in norm_msgs or []:
            if not isinstance(m, dict):
                continue
            if str(m.get("role") or "") == "tool":
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

        kwargs: dict[str, Any] = {"model": self.model, "messages": cleaned_msgs, "stream": stream}
        if use_tools:
            try:
                from oclaw.platform.config.paths import db_path
                from oclaw.platform.persistence.sqlite_store import SqliteStore
                from oclaw.tools.exposure_plan import build_llm_tools_plan

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
                kwargs["tools"] = tools
        return self._client.chat.completions.create(**kwargs)

    def _llm_response_from_completion(self, completion: Any, *, on_token: Optional[Callable[[str], None]]) -> LLMResponse:
        msg = completion.choices[0].message
        reasoning_parts = getattr(msg, "reasoning_content", None) or ""
        reasoning_text = str(reasoning_parts).strip() if reasoning_parts else ""
        content = msg.content or ""
        if on_token and content:
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


__all__ = ["OpenAIChatModel", "_likely_gemini_openai_compat_base_url", "_model_id_suggests_gemini"]


def _default_max_openai_tools_json_bytes(base_url: str | None) -> int | None:
    u = str(base_url or "").strip().lower()
    if not u:
        return None
    # Conservative caps for some OpenAI-compatible gateways.
    if "dashscope" in u or "aliyuncs" in u:
        return 28_000
    return None

