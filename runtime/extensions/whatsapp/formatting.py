from __future__ import annotations

import os
import re
from typing import Callable


def whatsapp_markdown_convert_enabled() -> bool:
    raw = str(os.getenv("AIA_WHATSAPP_MARKDOWN_CONVERT") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


_FENCE_RE = re.compile(r"```([^\n`]*)\n?(.*?)```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_LINK_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)|\[([^\]]+)\]\(([^)]+)\)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_BOLD_STARS_RE = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_BOLD_UNDERS_RE = re.compile(r"__(.+?)__", re.DOTALL)
_STRIKE_RE = re.compile(r"~~(.+?)~~", re.DOTALL)
_HR_RE = re.compile(r"^[ \t]{0,3}(?:-{3,}|\*{3,}|_{3,})[ \t]*$", re.MULTILINE)
_TABLE_SEP_RE = re.compile(r"^\s*\|?(?:\s*:?-+:?\s*\|)+\s*:?-+:?\s*\|?\s*$")
_TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")


def _protect_segments(
    text: str,
    pattern: re.Pattern[str],
    *,
    tag: str,
    rebuild: Callable[[re.Match[str]], str] | None = None,
) -> tuple[str, dict[str, str]]:
    slots: dict[str, str] = {}

    def _sub(m: re.Match[str]) -> str:
        key = f"\x00{tag}{len(slots)}\x00"
        slots[key] = rebuild(m) if rebuild else m.group(0)
        return key

    return pattern.sub(_sub, text), slots


def _restore(text: str, slots: dict[str, str]) -> str:
    out = text
    # Restore longer keys first in case of nested numbering.
    for key in sorted(slots.keys(), key=len, reverse=True):
        out = out.replace(key, slots[key])
    return out


def _convert_link(m: re.Match[str]) -> str:
    if m.group(1) is not None:  # image
        alt = str(m.group(1) or "").strip()
        url = str(m.group(2) or "").strip()
        if alt and url:
            return f"{alt}: {url}"
        return alt or url
    label = str(m.group(3) or "").strip()
    url = str(m.group(4) or "").strip()
    if not url:
        return label
    if not label or label == url:
        return url
    return f"{label}: {url}"


def _convert_table_block(lines: list[str]) -> list[str]:
    rows: list[list[str]] = []
    for line in lines:
        if _TABLE_SEP_RE.match(line):
            continue
        m = _TABLE_ROW_RE.match(line)
        if not m:
            # Loose pipe row without outer requirement.
            if "|" in line:
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if any(cells):
                    rows.append(cells)
            continue
        cells = [c.strip() for c in m.group(1).split("|")]
        if any(cells):
            rows.append(cells)
    if not rows:
        return lines
    headers = rows[0]
    body = rows[1:] if len(rows) > 1 else []
    out: list[str] = []
    if not body:
        # Header-only / single row: keep as one line.
        out.append(" · ".join(c for c in headers if c))
        return out
    for row in body:
        parts: list[str] = []
        for i, cell in enumerate(row):
            if not cell:
                continue
            key = headers[i] if i < len(headers) and headers[i] else f"c{i+1}"
            parts.append(f"{key}: {cell}")
        if parts:
            out.append("- " + " · ".join(parts))
    return out or [" · ".join(headers)]


def _rewrite_tables(text: str) -> str:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if "|" in line and (
            _TABLE_ROW_RE.match(line)
            or (i + 1 < len(lines) and _TABLE_SEP_RE.match(lines[i + 1]))
        ):
            block = [line]
            i += 1
            while i < len(lines) and ("|" in lines[i] or _TABLE_SEP_RE.match(lines[i])):
                block.append(lines[i])
                i += 1
            out.extend(_convert_table_block(block))
            continue
        out.append(line)
        i += 1
    return "\n".join(out)


def markdown_to_whatsapp_text(text: str) -> str:
    """
    Convert common Markdown (LLM output) into WhatsApp native formatting.

    WhatsApp uses *bold*, _italic_, ~strike~, ```monospace``` / `code`.
    Standard Markdown **bold**, # headings, tables, and [label](url) are rewritten.

    Note: single-asterisk Markdown italic is NOT rewritten to _italic_. That conflicts
    with WhatsApp bold (*text*) and would corrupt already-correct WA messages.
    """
    raw = str(text or "")
    if not raw.strip():
        return raw
    if not whatsapp_markdown_convert_enabled():
        return raw

    work = raw.replace("\r\n", "\n").replace("\r", "\n")

    # 1) Protect fenced + inline code (restore as WhatsApp monospace/code).
    def _fence_rebuild(m: re.Match[str]) -> str:
        body = str(m.group(2) or "").strip("\n")
        return f"```{body}```" if body else "``` ```"

    work, fence_slots = _protect_segments(work, _FENCE_RE, tag="FENCE", rebuild=_fence_rebuild)
    work, inline_slots = _protect_segments(
        work,
        _INLINE_CODE_RE,
        tag="CODE",
        rebuild=lambda m: f"`{m.group(1)}`",
    )

    # 2) Links / images before emphasis (URLs may contain underscores).
    work = _LINK_RE.sub(_convert_link, work)

    # 3) Horizontal rules + tables.
    work = _HR_RE.sub("────", work)
    work = _rewrite_tables(work)

    # 4) Bold / headings / strike. Keep bold as placeholders until the end so we
    # never mistake *bold* for Markdown italic.
    bold_slots: dict[str, str] = {}

    def _hold_bold(inner: str) -> str:
        text_inner = str(inner or "").strip()
        if not text_inner:
            return ""
        key = f"\x00BOLD{len(bold_slots)}\x00"
        bold_slots[key] = f"*{text_inner}*"
        return key

    def _bold_sub(m: re.Match[str]) -> str:
        held = _hold_bold(m.group(1))
        return held if held else m.group(0)

    work = _BOLD_STARS_RE.sub(_bold_sub, work)
    work = _BOLD_UNDERS_RE.sub(_bold_sub, work)
    work = _HEADING_RE.sub(lambda m: _hold_bold(m.group(2)) or m.group(0), work)
    work = _STRIKE_RE.sub(lambda m: f"~{str(m.group(1) or '').strip()}~", work)

    # 5) Restore protected segments. Do not map *italic* → _italic_ (WA collision).
    work = _restore(work, bold_slots)
    work = _restore(work, inline_slots)
    work = _restore(work, fence_slots)

    # Collapse 3+ blank lines from table/heading rewrites.
    work = re.sub(r"\n{3,}", "\n\n", work)
    return work.strip()


def prepare_whatsapp_outbound_text(text: str) -> str:
    """Public entry used by outbound enqueue paths."""
    return markdown_to_whatsapp_text(text)


__all__ = [
    "markdown_to_whatsapp_text",
    "prepare_whatsapp_outbound_text",
    "whatsapp_markdown_convert_enabled",
]
