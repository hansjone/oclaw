"""Parse DeepSeek-V4 DSML ``tool_calls`` blocks from assistant text.

Reference: `encoding/README.md` and `encoding/encoding_dsv4.py` in the upstream
`deepseek-ai/DeepSeek-V4-Pro` repository on Hugging Face (DSML grammar for
``<｜DSML｜tool_calls>`` / ``invoke`` / ``parameter`` with ``string=\"true|false\"``).

Some gateways emit ASCII pipes (``<||DSML||...``) instead of the fullwidth
separator (U+FF5C ``｜``); we normalize those before parsing.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from oclaw.platform.llm.transports.base import LLMToolCall

# Official DeepSeek-V4 DSML token uses FULLWIDTH VERTICAL LINE (U+FF5C).
_DSML_PIPE = "\uFF5C"

_RE_TOOL_CALLS_OPEN = re.compile(
    rf"<\s*{_DSML_PIPE}\s*DSML\s*{_DSML_PIPE}\s*tool_calls\s*>",
    flags=re.IGNORECASE,
)
_RE_TOOL_CALLS_CLOSE = re.compile(
    rf"</\s*{_DSML_PIPE}\s*DSML\s*{_DSML_PIPE}\s*tool_calls\s*>",
    flags=re.IGNORECASE,
)
_RE_INVOKE_OPEN = re.compile(
    rf"<\s*{_DSML_PIPE}\s*DSML\s*{_DSML_PIPE}\s*invoke\s+name\s*=\s*\"([^\"]+)\"\s*>",
    flags=re.IGNORECASE,
)
_RE_INVOKE_CLOSE = re.compile(
    rf"</\s*{_DSML_PIPE}\s*DSML\s*{_DSML_PIPE}\s*invoke\s*>",
    flags=re.IGNORECASE,
)
_RE_PARAM_OPEN = re.compile(
    rf"<\s*{_DSML_PIPE}\s*DSML\s*{_DSML_PIPE}\s*parameter\s+name\s*=\s*\"([^\"]+)\"\s+string\s*=\s*\"(true|false)\"\s*>",
    flags=re.IGNORECASE,
)
_RE_PARAM_CLOSE = re.compile(
    rf"</\s*{_DSML_PIPE}\s*DSML\s*{_DSML_PIPE}\s*parameter\s*>",
    flags=re.IGNORECASE,
)


def normalize_dsml_markup(text: str) -> str:
    """Map common gateway variants to the canonical DSML delimiter sequence."""
    s = str(text or "")
    s = s.replace("<||DSML||", f"<{_DSML_PIPE}DSML{_DSML_PIPE}")
    s = s.replace("</||DSML||", f"</{_DSML_PIPE}DSML{_DSML_PIPE}")
    return s


def _find_tool_calls_block_span(normalized: str) -> tuple[int, int] | None:
    m_open = _RE_TOOL_CALLS_OPEN.search(normalized)
    if not m_open:
        return None
    start = int(m_open.start())
    from_pos = int(m_open.end())
    m_close = _RE_TOOL_CALLS_CLOSE.search(normalized, from_pos)
    if not m_close:
        return None
    end = int(m_close.end())
    return (start, end)


def strip_first_dsml_tool_calls_block(text: str) -> str | None:
    """Remove the first well-formed ``tool_calls`` DSML block; return None if none found."""
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
    return args


def _parse_invokes(inner: str) -> list[tuple[str, dict[str, Any]]] | None:
    out: list[tuple[str, dict[str, Any]]] = []
    pos = 0
    while pos < len(inner):
        m = _RE_INVOKE_OPEN.search(inner, pos)
        if not m:
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


def try_parse_deepseek_v4_dsml_tool_calls(text: str) -> list[LLMToolCall] | None:
    """
    If ``text`` contains a complete first ``tool_calls`` DSML block, return
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
    invokes = _parse_invokes(inner)
    if invokes is None:
        return None
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


__all__ = [
    "normalize_dsml_markup",
    "strip_first_dsml_tool_calls_block",
    "try_parse_deepseek_v4_dsml_tool_calls",
]
