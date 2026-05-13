"""OpenAI-compatible tool_call_id / tool result id rewriting.

Inspired by Oclaw (MIT) `src/agents/tool-call-id.ts`: sanitize ids to strict
alphanumeric form and keep assistant.tool_calls[].id paired with role=tool
tool_call_id in encounter order.

See OCLAW_MIT_LICENSE.txt in this package.
"""

from __future__ import annotations

import hashlib
import re
from collections import deque
from typing import Any, Literal

ToolCallIdMode = Literal["strict", "strict9"]

# OpenAI Chat Completions: tool_calls[].id commonly capped ~40 chars on some gateways.
DEFAULT_MAX_OPENAI_TOOL_CALL_ID_LEN = 40


def _short_hash(text: str, length: int = 8) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:length]


def sanitize_tool_call_id(raw: str | None, *, mode: ToolCallIdMode = "strict") -> str:
    """Strip to [a-zA-Z0-9] only; empty input gets a deterministic placeholder."""
    if not raw or not isinstance(raw, str):
        return "sanitizedtoolid" if mode == "strict" else "defaultid"
    s = raw.strip()
    if not s:
        return "sanitizedtoolid" if mode == "strict" else "defaultid"
    alnum = re.sub(r"[^a-zA-Z0-9]", "", s)
    if mode == "strict9":
        if len(alnum) >= 9:
            return alnum[:9]
        if alnum:
            return _short_hash(alnum, 9)
        return _short_hash("sanitized", 9)
    return alnum if alnum else "sanitizedtoolid"


def _make_unique(seed: str, used: set[str], *, max_len: int) -> str:
    base = sanitize_tool_call_id(seed, mode="strict")[:max_len]
    if base and base not in used:
        used.add(base)
        return base
    h = _short_hash(seed, 8)
    for i in range(1000):
        cand = f"{base[: max(0, max_len - len(h) - 1)]}{h}"[:max_len]
        if i > 0:
            suf = f"x{i}"
            cand = f"{base[: max(0, max_len - len(suf) - len(h))]}{suf}{h}"[:max_len]
        if cand not in used:
            used.add(cand)
            return cand
    cand = _short_hash(f"{seed}:{id(used)}", max_len)[:max_len]
    used.add(cand)
    return cand


def rewrite_openai_chat_messages_tool_ids(
    messages: list[dict[str, Any]],
    *,
    max_len: int = DEFAULT_MAX_OPENAI_TOOL_CALL_ID_LEN,
) -> list[dict[str, Any]]:
    """Rewrite assistant tool_calls ids and matching tool tool_call_id/call_id.

    Uses a per-raw-id queue (oclaw-style) so repeated raw ids map to distinct
    new ids in order, and tool results consume the queue FIFO.
    """
    if not messages:
        return messages

    pending: dict[str, deque[str]] = {}
    used: set[str] = set()

    def _alloc_for_raw(raw: str) -> str:
        raw = str(raw or "").strip()
        seed = raw if raw else "empty"
        return _make_unique(seed, used, max_len=max_len)

    out: list[dict[str, Any]] = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "")
        if role == "assistant" and m.get("tool_calls"):
            mm = dict(m)
            tcs = mm.get("tool_calls")
            if isinstance(tcs, list):
                new_tcs: list[dict[str, Any]] = []
                for tc in tcs:
                    if not isinstance(tc, dict):
                        new_tcs.append(tc)
                        continue
                    raw_id = str(tc.get("id") or "").strip()
                    new_id = _alloc_for_raw(raw_id)
                    q = pending.setdefault(raw_id, deque())
                    q.append(new_id)
                    new_tcs.append({**tc, "id": new_id})
                mm["tool_calls"] = new_tcs
            out.append(mm)
            continue
        if role == "tool":
            mm = dict(m)
            raw_ref = (
                str(mm.get("tool_call_id") or mm.get("call_id") or "").strip()
            )
            new_ref: str | None = None
            if raw_ref and raw_ref in pending and pending[raw_ref]:
                new_ref = pending[raw_ref].popleft()
            elif raw_ref:
                # Orphan or ordering mismatch: allocate fresh id (best-effort pairing)
                new_ref = _alloc_for_raw(raw_ref)
            if new_ref:
                mm["tool_call_id"] = new_ref
                # Keep call_id in sync when both present (some gateways expect call_id)
                if "call_id" in mm:
                    mm["call_id"] = new_ref
            else:
                mm.pop("tool_call_id", None)
                mm.pop("call_id", None)
            out.append(mm)
            continue
        out.append(dict(m) if isinstance(m, dict) else m)
    return out


def repair_orphan_tool_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop tool_call_id/call_id from tool rows that reference no prior assistant tool_calls id."""
    allowed: set[str] = set()
    for m in messages:
        if not isinstance(m, dict):
            continue
        if str(m.get("role") or "") != "assistant":
            continue
        tcs = m.get("tool_calls")
        if not isinstance(tcs, list):
            continue
        for tc in tcs:
            if isinstance(tc, dict) and tc.get("id"):
                allowed.add(str(tc.get("id")))

    out: list[dict[str, Any]] = []
    for m in messages:
        if not isinstance(m, dict):
            out.append(m)
            continue
        if str(m.get("role") or "") != "tool":
            out.append(m)
            continue
        mm = dict(m)
        tid = str(mm.get("tool_call_id") or mm.get("call_id") or "").strip()
        if tid and tid not in allowed:
            mm.pop("tool_call_id", None)
            mm.pop("call_id", None)
        out.append(mm)
    return out
