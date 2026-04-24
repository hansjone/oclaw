from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any, Optional
from collections.abc import Callable, Iterable

from oclaw.platform.llm.transports.base import ChatModel, LLMResponse, LLMToolCall

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


def parse_anthropic_stream_events(
    events: Iterable[Any],
    *,
    on_token: Optional[Callable[[str], None]] = None,
) -> tuple[str, list[LLMToolCall]]:
    parts: list[str] = []
    tool_by_id: dict[str, dict[str, Any]] = {}
    current_block: dict[str, Any] | None = None

    for ev in events:
        d = _as_dict(ev) or {}
        typ = str(d.get("type") or "")
        if typ in ("message_start", "message_delta", "message_stop"):
            continue
        if typ == "content_block_start":
            cb = d.get("content_block") if isinstance(d.get("content_block"), dict) else {}
            current_block = cb
            # tool_use blocks carry name/id/input in start
            if str(cb.get("type") or "") == "tool_use":
                tid = str(cb.get("id") or "") or f"call_{uuid.uuid4().hex}"
                tool_by_id[tid] = {
                    "id": tid,
                    "name": str(cb.get("name") or ""),
                    "input_json": cb.get("input") if isinstance(cb.get("input"), dict) else {},
                    "_input_buf": "",
                }
            continue
        if typ == "content_block_delta":
            delta = d.get("delta") if isinstance(d.get("delta"), dict) else {}
            dt = str(delta.get("type") or "")
            if dt == "text_delta":
                t = str(delta.get("text") or "")
                if t:
                    parts.append(t)
                    if on_token:
                        on_token(t)
                continue
            if dt in ("input_json_delta", "tool_use_delta"):
                partial = delta.get("partial_json") or delta.get("partial") or ""
                s = str(partial or "")
                # attach to last tool_use block if any
                # Anthropics uses content block index; we just buffer by most recent tool_use id.
                if current_block and str(current_block.get("type") or "") == "tool_use":
                    tid = str(current_block.get("id") or "")
                    if tid and tid in tool_by_id:
                        tool_by_id[tid]["_input_buf"] = str(tool_by_id[tid].get("_input_buf") or "") + s
                continue
            continue
        if typ == "content_block_stop":
            current_block = None
            continue

    tool_calls: list[LLMToolCall] = []
    for tid, slot in tool_by_id.items():
        args = slot.get("input_json") if isinstance(slot.get("input_json"), dict) else {}
        buf = str(slot.get("_input_buf") or "").strip()
        if buf:
            try:
                parsed = json.loads(buf)
                if isinstance(parsed, dict):
                    args = parsed
                else:
                    args = {"_raw": parsed}
            except Exception:
                # keep best-effort
                pass
        tool_calls.append(LLMToolCall(id=tid, name=str(slot.get("name") or ""), arguments=args, thought_signature=None))

    return "".join(parts), tool_calls


class AnthropicMessagesModel(ChatModel):
    def __init__(self, *, model: str | None = None, api_key: str | None = None, base_url: str | None = None):
        self.model = (model or os.getenv("ANTHROPIC_MODEL") or "claude-3-5-sonnet-latest").strip()
        self.api_key = (api_key or os.getenv("ANTHROPIC_API_KEY") or "").strip()
        self.base_url = (base_url or os.getenv("ANTHROPIC_BASE_URL") or "").strip() or None
        if not self.api_key:
            raise RuntimeError("未设置 ANTHROPIC_API_KEY，无法使用 Anthropic 模型")
        try:
            import anthropic
        except Exception as exc:
            raise RuntimeError("未安装 anthropic 依赖，请先 pip install -r requirements.txt") from exc
        kw: dict[str, Any] = {"api_key": self.api_key}
        if self.base_url:
            kw["base_url"] = self.base_url
        self._client = anthropic.Anthropic(**kw)

    @staticmethod
    def _to_anthropic_messages(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
        system_chunks: list[str] = []
        out: list[dict[str, Any]] = []
        for m in messages or []:
            if not isinstance(m, dict):
                continue
            role = str(m.get("role") or "")
            content = m.get("content")
            if role == "system":
                if isinstance(content, str) and content.strip():
                    system_chunks.append(content)
                continue
            if role in ("user", "assistant"):
                if isinstance(content, str):
                    out.append({"role": role, "content": content})
                else:
                    out.append({"role": role, "content": str(content)})
                continue
            if role == "tool":
                # Anthropic expects tool results as user content blocks; we stringify.
                name = str(m.get("name") or m.get("tool_name") or m.get("toolName") or "tool").strip()
                out.append({"role": "user", "content": f"[tool_result:{name}] {str(content)}"})
                continue
        return "\n\n".join(system_chunks).strip(), out

    @staticmethod
    def _to_anthropic_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for t in tools or []:
            if not isinstance(t, dict) or str(t.get("type") or "") != "function":
                continue
            fn = t.get("function")
            if not isinstance(fn, dict):
                continue
            name = str(fn.get("name") or "").strip()
            if not name:
                continue
            out.append(
                {
                    "name": name,
                    "description": str(fn.get("description") or ""),
                    "input_schema": fn.get("parameters") if isinstance(fn.get("parameters"), dict) else {"type": "object"},
                }
            )
        return out

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> LLMResponse:
        system, msgs = self._to_anthropic_messages(messages)
        atools = self._to_anthropic_tools(tools)
        try:
            stream = self._client.messages.stream(
                model=self.model,
                system=system or None,
                messages=msgs,
                tools=atools or None,
                max_tokens=2048,
            )
            text, tool_calls = parse_anthropic_stream_events(stream, on_token=on_token)
            return LLMResponse(content=text, tool_calls=tool_calls)
        except Exception as exc:
            logger.info("anthropic stream failed; fallback to non-stream (%s)", exc)
            resp = self._client.messages.create(
                model=self.model,
                system=system or None,
                messages=msgs,
                tools=atools or None,
                max_tokens=2048,
            )
            d = _as_dict(resp) or {}
            content = d.get("content")
            text = ""
            if isinstance(content, list):
                for blk in content:
                    if isinstance(blk, dict) and blk.get("type") == "text":
                        text += str(blk.get("text") or "")
            if on_token and text:
                on_token(text)
            return LLMResponse(content=text, tool_calls=[])


__all__ = ["AnthropicMessagesModel", "parse_anthropic_stream_events"]

