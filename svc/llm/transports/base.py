from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Optional
from collections.abc import Callable


@dataclass(frozen=True)
class LLMToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
    # Gemini OpenAI-compat and native transports may require preserving a signature across tool loops.
    thought_signature: str | None = None


@dataclass(frozen=True)
class LLMResponse:
    content: str
    tool_calls: list[LLMToolCall]
    reasoning_content: str = ""


class ChatModel:
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> LLMResponse:
        raise NotImplementedError


def coerce_thought_signature_for_storage(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, (bytes, bytearray)):
        try:
            return bytes(v).decode("utf-8")
        except UnicodeDecodeError:
            return base64.b64encode(bytes(v)).decode("ascii")
    if isinstance(v, (dict, list)):
        return json.dumps(v, separators=(",", ":"), ensure_ascii=False)
    return str(v)


def normalize_image_b64_payload(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, (bytes, bytearray)):
        return base64.b64encode(bytes(raw)).decode("ascii")
    s = str(raw).strip()
    if not s:
        return ""
    if s.startswith("data:") and ";base64," in s:
        s = s.split(";base64,", 1)[-1].strip()
    return "".join(s.split())

