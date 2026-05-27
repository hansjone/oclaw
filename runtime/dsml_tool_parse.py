"""Parse DeepSeek DSML tool-call blocks from assistant text.

Reference: `encoding/README.md` and `encoding/encoding_dsv4.py` in the upstream
`deepseek-ai/DeepSeek-V4-Pro` repository on Hugging Face (DSML grammar for
``<｜DSML｜tool_calls>`` / ``invoke`` / ``parameter`` with ``string=\"true|false\"``).

Some gateways emit ASCII pipes (``<||DSML||...``) instead of the fullwidth
separator (U+FF5C ``｜``); we normalize those before parsing.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any

from svc.llm.transports.base import LLMToolCall

# Official DeepSeek DSML token uses FULLWIDTH VERTICAL LINE (U+FF5C).
_DSML_PIPE = "\uFF5C"
_DSML_BARS = ("|", _DSML_PIPE)
_DSML_PIPE_GROUP = rf"(?:[|{_DSML_PIPE}]\s*)+"
_DSML_WRAPPER_KINDS = ("tool_calls", "function_calls", "tool_call", "function_call")

_RE_INVOKE_OPEN = re.compile(
    rf"<\s*{_DSML_PIPE_GROUP}DSML\s*{_DSML_PIPE_GROUP}invoke\s+name\s*=\s*\"([^\"]+)\"\s*>",
    flags=re.IGNORECASE,
)
_RE_INVOKE_CLOSE = re.compile(
    rf"</\s*{_DSML_PIPE_GROUP}DSML\s*{_DSML_PIPE_GROUP}invoke\s*>",
    flags=re.IGNORECASE,
)
_RE_PARAM_OPEN = re.compile(
    rf"<\s*{_DSML_PIPE_GROUP}DSML\s*{_DSML_PIPE_GROUP}parameter\s+name\s*=\s*\"([^\"]+)\"\s+string\s*=\s*\"(true|false)\"\s*>",
    flags=re.IGNORECASE,
)
_RE_PARAM_CLOSE = re.compile(
    rf"</\s*{_DSML_PIPE_GROUP}DSML\s*{_DSML_PIPE_GROUP}parameter\s*>",
    flags=re.IGNORECASE,
)


def _dsml_open_tokens() -> list[str]:
    tokens = [f"<{bar}DSML{bar}{kind}>" for bar in _DSML_BARS for kind in _DSML_WRAPPER_KINDS]
    tokens.extend(f"<||DSML||{kind}>" for kind in _DSML_WRAPPER_KINDS)
    return tokens


def _dsml_close_tokens() -> list[str]:
    tokens = [f"</{bar}DSML{bar}{kind}>" for bar in _DSML_BARS for kind in _DSML_WRAPPER_KINDS]
    tokens.extend(f"</||DSML||{kind}>" for kind in _DSML_WRAPPER_KINDS)
    return tokens


_RE_SPACED_DSML_OPEN = re.compile(
    rf"<\s*{_DSML_PIPE_GROUP}DSML\s*{_DSML_PIPE_GROUP}",
    flags=re.IGNORECASE,
)
_RE_SPACED_DSML_CLOSE = re.compile(
    rf"</\s*{_DSML_PIPE_GROUP}DSML\s*{_DSML_PIPE_GROUP}",
    flags=re.IGNORECASE,
)
_RE_DSML_BLOCK_OPEN = re.compile(
    rf"<\s*{_DSML_PIPE_GROUP}DSML\s*{_DSML_PIPE_GROUP}"
    rf"(?:{'|'.join(_DSML_WRAPPER_KINDS)})\s*>",
    flags=re.IGNORECASE,
)
_RE_DSML_BLOCK_CLOSE = re.compile(
    rf"</\s*{_DSML_PIPE_GROUP}DSML\s*{_DSML_PIPE_GROUP}"
    rf"(?:{'|'.join(_DSML_WRAPPER_KINDS)})\s*>",
    flags=re.IGNORECASE,
)
_DSML_OPEN_TOKENS = _dsml_open_tokens()
_DSML_CLOSE_TOKENS = _dsml_close_tokens()
_MAX_OPEN_TOKEN_LEN = max(len(t) for t in _DSML_OPEN_TOKENS)
_MAX_CLOSE_TOKEN_LEN = max(len(t) for t in _DSML_CLOSE_TOKENS)


def normalize_dsml_markup(text: str) -> str:
    """Map common gateway variants to the canonical DSML delimiter sequence."""
    s = str(text or "")
    ff2 = f"{_DSML_PIPE}{_DSML_PIPE}"
    s = s.replace(f"<{ff2}DSML{ff2}", f"<{_DSML_PIPE}DSML{_DSML_PIPE}")
    s = s.replace(f"</{ff2}DSML{ff2}", f"</{_DSML_PIPE}DSML{_DSML_PIPE}")
    s = s.replace("<||DSML||", f"<{_DSML_PIPE}DSML{_DSML_PIPE}")
    s = s.replace("</||DSML||", f"</{_DSML_PIPE}DSML{_DSML_PIPE}")
    s = _RE_SPACED_DSML_OPEN.sub(f"<{_DSML_PIPE}DSML{_DSML_PIPE}", s)
    s = _RE_SPACED_DSML_CLOSE.sub(f"</{_DSML_PIPE}DSML{_DSML_PIPE}", s)
    return s


def _find_earliest_block_open(text: str) -> tuple[int, int] | None:
    m = _RE_DSML_BLOCK_OPEN.search(text)
    if not m:
        return None
    return int(m.start()), int(m.end())


def _find_earliest_block_close(text: str) -> tuple[int, int] | None:
    m = _RE_DSML_BLOCK_CLOSE.search(text)
    if not m:
        return None
    return int(m.start()), int(m.end())


def _find_earliest_token(text: str, tokens: list[str]) -> tuple[int, str] | None:
    best: tuple[int, str] | None = None
    for token in tokens:
        idx = text.find(token)
        if idx != -1 and (best is None or idx < best[0]):
            best = (idx, token)
    return best


def _longest_dsml_open_prefix_suffix_length(text: str) -> int:
    max_len = min(len(text), _MAX_OPEN_TOKEN_LEN - 1)
    for length in range(max_len, 0, -1):
        suffix = text[-length:]
        if any(token.startswith(suffix) for token in _DSML_OPEN_TOKENS):
            return length
    return 0


def _wrapper_kind_regex(kind: str) -> tuple[re.Pattern[str], re.Pattern[str]]:
    open_re = re.compile(
        rf"<\s*{_DSML_PIPE_GROUP}DSML\s*{_DSML_PIPE_GROUP}{re.escape(kind)}\s*>",
        flags=re.IGNORECASE,
    )
    close_re = re.compile(
        rf"</\s*{_DSML_PIPE_GROUP}DSML\s*{_DSML_PIPE_GROUP}{re.escape(kind)}\s*>",
        flags=re.IGNORECASE,
    )
    return open_re, close_re


def _find_tool_calls_block_span(normalized: str) -> tuple[int, int] | None:
    best: tuple[int, int] | None = None
    for kind in _DSML_WRAPPER_KINDS:
        open_re, close_re = _wrapper_kind_regex(kind)
        m_open = open_re.search(normalized)
        if not m_open:
            continue
        start = int(m_open.start())
        from_pos = int(m_open.end())
        m_close = close_re.search(normalized, from_pos)
        if not m_close:
            continue
        end = int(m_close.end())
        if best is None or start < best[0]:
            best = (start, end)
    return best


def strip_first_dsml_tool_calls_block(text: str) -> str | None:
    """Remove the first well-formed DSML wrapper block; return None if none found."""
    raw = str(text or "")
    if not raw:
        return None
    norm = normalize_dsml_markup(raw)
    span = _find_tool_calls_block_span(norm)
    if span is None:
        return None
    a, b = span
    out = (norm[:a] + norm[b:]).strip()
    return out


def _decode_param_value(raw_value: str, *, string_flag: str) -> Any:
    v = str(raw_value or "")
    if string_flag.lower() == "true":
        return v
    v_strip = v.strip()
    if not v_strip:
        return ""
    try:
        return json.loads(v_strip)
    except Exception:
        return v_strip


def _parse_invoke_body_json(body: str) -> dict[str, Any] | None:
    stripped = str(body or "").strip()
    if not stripped or not stripped.startswith("{"):
        return None
    try:
        parsed = json.loads(stripped)
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None
    return dict(parsed)


def _parse_invoke_body(body: str) -> dict[str, Any] | None:
    args: dict[str, Any] = {}
    pos = 0
    b = str(body or "")
    while pos < len(b):
        m = _RE_PARAM_OPEN.search(b, pos)
        if not m:
            break
        pname = str(m.group(1) or "").strip()
        sflag = str(m.group(2) or "true").strip()
        start = int(m.end())
        cm = _RE_PARAM_CLOSE.search(b, start)
        if not cm or not pname:
            return None
        raw_val = b[start : int(cm.start())]
        if pname in args:
            return None
        args[pname] = _decode_param_value(raw_val, string_flag=sflag)
        pos = int(cm.end())
    if args:
        return args
    json_args = _parse_invoke_body_json(b)
    if json_args is not None:
        return json_args
    return args


def _parse_invokes(inner: str) -> list[tuple[str, dict[str, Any]]] | None:
    out: list[tuple[str, dict[str, Any]]] = []
    pos = 0
    while pos < len(inner):
        m = _RE_INVOKE_OPEN.search(inner, pos)
        if not m:
            if not out and re.search(r"invoke\s+name\s*=", inner[pos:], flags=re.IGNORECASE):
                return None
            break
        name = str(m.group(1) or "").strip()
        sub_start = int(m.end())
        cm = _RE_INVOKE_CLOSE.search(inner, sub_start)
        if not cm or not name:
            return None
        body = inner[sub_start : int(cm.start())]
        parsed_args = _parse_invoke_body(body)
        if parsed_args is None:
            return None
        out.append((name, parsed_args))
        pos = int(cm.end())
    return out


def _invokes_to_llm_tool_calls(invokes: list[tuple[str, dict[str, Any]]]) -> list[LLMToolCall]:
    out: list[LLMToolCall] = []
    for name, args in invokes:
        out.append(
            LLMToolCall(
                id=f"call_dsml_{uuid.uuid4().hex}",
                name=name,
                arguments=dict(args),
                thought_signature=None,
            )
        )
    return out


def _parse_dsml_block_inner(inner: str) -> list[LLMToolCall] | None:
    invokes = _parse_invokes(normalize_dsml_markup(inner))
    if invokes is None:
        return None
    return _invokes_to_llm_tool_calls(invokes)


def try_parse_deepseek_v4_dsml_tool_calls(text: str) -> list[LLMToolCall] | None:
    """
    If ``text`` contains a complete first DSML wrapper block, return
    ``LLMToolCall`` rows (may be empty if the block has no ``invoke`` tags).

    Returns ``None`` when no block is found or the block is malformed.
    """
    raw = str(text or "")
    if not raw.strip():
        return None
    norm = normalize_dsml_markup(raw)
    span = _find_tool_calls_block_span(norm)
    if span is None:
        return None
    a, b = span
    inner = norm[a:b]
    return _parse_dsml_block_inner(inner)


def try_parse_dsml_tool_calls_from_fields(
    *,
    content: str = "",
    reasoning_content: str = "",
) -> tuple[list[LLMToolCall] | None, str, str]:
    """Search ``content`` then ``reasoning_content`` for DSML tool calls.

    Returns ``(calls, cleaned_content, cleaned_reasoning)``. When parsing succeeds,
    the field that contained the block is stripped; the other field is unchanged.
    """
    for field_name, text in (("content", str(content or "")), ("reasoning_content", str(reasoning_content or ""))):
        parsed = try_parse_deepseek_v4_dsml_tool_calls(text)
        if parsed is None:
            continue
        if not parsed and re.search(r"invoke\s+name\s*=", text, flags=re.IGNORECASE):
            continue
        stripped = strip_first_dsml_tool_calls_block(text)
        clean = stripped if stripped is not None else ""
        if field_name == "content":
            return parsed, clean, str(reasoning_content or "")
        return parsed, str(content or ""), clean
    return None, str(content or ""), str(reasoning_content or "")


def dsml_text_tools_enabled(*, base_url: str = "", model_id: str = "") -> bool:
    """Whether DSML-in-text should be promoted to native tool calls."""
    env = str(os.getenv("AIA_DSML_TEXT_TOOLS") or "").strip().lower()
    if env in {"0", "false", "no", "off"}:
        return False
    if env in {"1", "true", "yes", "on"}:
        return True
    bu = str(base_url or "").strip().lower()
    mid = str(model_id or "").strip().lower()
    if "deepseek" in bu or "deepseek" in mid:
        return True
    if mid.startswith("deepseek-"):
        return True
    return False


def should_recover_dsml_tool_calls(
    model_id: str = "",
    base_url: str = "",
    *,
    thinking_mode_enabled: bool = False,
) -> bool:
    if dsml_text_tools_enabled(base_url=base_url, model_id=model_id):
        return True
    if thinking_mode_enabled:
        mid = str(model_id or "").strip().lower()
        if mid.startswith("deepseek-") or "deepseek" in mid:
            return True
    return False


def contains_dsml_tool_markers(text: str) -> bool:
    raw = str(text or "")
    if not raw.strip():
        return False
    lower = raw.lower()
    if "dsml" not in lower:
        return False
    return ("tool_calls" in lower) or ("function_calls" in lower) or ("invoke name" in lower)


def promote_dsml_tool_calls_in_response(
    content: str,
    reasoning: str,
    tool_calls: list[LLMToolCall],
) -> tuple[str, str, list[LLMToolCall]]:
    if tool_calls:
        return content, reasoning, tool_calls
    parsed, clean_content, clean_reasoning = try_parse_dsml_tool_calls_from_fields(
        content=content,
        reasoning_content=reasoning,
    )
    if parsed:
        return clean_content, clean_reasoning, parsed
    return content, reasoning, tool_calls


class DeepSeekTextFilter:
    """Stream filter: hide DSML from visible text and capture blocks for recovery."""

    def __init__(self) -> None:
        self._buffer = ""
        self._inside_dsml = False
        self._dsml_capture = ""
        self._captured_blocks: list[str] = []
        self._visible_parts: list[str] = []

    def push(self, chunk: str) -> list[str]:
        self._buffer += str(chunk or "")
        return self._consume(final=False)

    def flush(self) -> list[str]:
        return self._consume(final=True)

    @property
    def visible_text(self) -> str:
        return "".join(self._visible_parts)

    def recovered_tool_calls(self) -> list[LLMToolCall]:
        out: list[LLMToolCall] = []
        for block in self._captured_blocks:
            parsed = _parse_dsml_block_inner(block)
            if parsed:
                out.extend(parsed)
        return out

    def _consume(self, *, final: bool) -> list[str]:
        output: list[str] = []

        def emit(text: str) -> None:
            if text:
                output.append(text)
                self._visible_parts.append(text)

        while self._buffer:
            if self._inside_dsml:
                close = _find_earliest_block_close(self._buffer)
                if close:
                    idx, end = close
                    self._dsml_capture += self._buffer[:idx]
                    self._captured_blocks.append(self._dsml_capture)
                    self._dsml_capture = ""
                    self._buffer = self._buffer[end:]
                    self._inside_dsml = False
                    continue
                legacy_close = _find_earliest_token(self._buffer, _DSML_CLOSE_TOKENS)
                if legacy_close:
                    idx, token = legacy_close
                    self._dsml_capture += self._buffer[:idx]
                    self._captured_blocks.append(self._dsml_capture)
                    self._dsml_capture = ""
                    self._buffer = self._buffer[idx + len(token) :]
                    self._inside_dsml = False
                    continue
                keep = 0 if final else min(len(self._buffer), _MAX_CLOSE_TOKEN_LEN - 1)
                self._dsml_capture += self._buffer[: len(self._buffer) - keep]
                self._buffer = self._buffer[len(self._buffer) - keep :]
                if final:
                    if self._dsml_capture:
                        self._captured_blocks.append(self._dsml_capture)
                        self._dsml_capture = ""
                    self._inside_dsml = False
                return output

            open_match = _find_earliest_block_open(self._buffer)
            if open_match:
                idx, end = open_match
                emit(self._buffer[:idx])
                self._buffer = self._buffer[end:]
                self._inside_dsml = True
                self._dsml_capture = ""
                continue

            legacy_open = _find_earliest_token(self._buffer, _DSML_OPEN_TOKENS)
            if legacy_open:
                idx, token = legacy_open
                emit(self._buffer[:idx])
                self._buffer = self._buffer[idx + len(token) :]
                self._inside_dsml = True
                self._dsml_capture = ""
                continue

            if final:
                emit(self._buffer)
                self._buffer = ""
                return output

            keep = _longest_dsml_open_prefix_suffix_length(self._buffer)
            emit_len = len(self._buffer) - keep
            if emit_len <= 0:
                return output
            emit(self._buffer[:emit_len])
            self._buffer = self._buffer[emit_len:]
            return output

        return output


__all__ = [
    "DeepSeekTextFilter",
    "contains_dsml_tool_markers",
    "dsml_text_tools_enabled",
    "normalize_dsml_markup",
    "promote_dsml_tool_calls_in_response",
    "should_recover_dsml_tool_calls",
    "strip_first_dsml_tool_calls_block",
    "try_parse_deepseek_v4_dsml_tool_calls",
    "try_parse_dsml_tool_calls_from_fields",
]
