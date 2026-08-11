"""Rate-limited WhatsApp interim progress during long channel turns.

Field groups hate spam: keep at most a few ticks, never alternate
"Running CLI" ↔ "composing", and announce each long tool at most once.
"""

from __future__ import annotations

import os
import re
import threading
import time
from typing import Any, Callable

_TOOLS_DONE_RE = re.compile(r"tools done\s*\((\d+)\s*ms\)", re.IGNORECASE)

# Tools that commonly exceed ~10s on production WA turns.
_LONG_TOOL_LABELS_ZH: dict[str, str] = {
    "execmanagedne": "正在设备上执行命令，请稍候…",
    "listclitargets": "正在枚举 CLI 目标，请稍候…",
    "umealarmxlsxreport": "正在生成告警 Excel，请稍候…",
    "queryumealarms": "正在查询 UME 告警，请稍候…",
    "queryumealarmsraw": "正在查询 UME 告警，请稍候…",
    "aggregateumealarms": "正在汇总 UME 告警，请稍候…",
    "aggregateumealarmsraw": "正在汇总 UME 告警，请稍候…",
    "runumediagnostics": "正在跑 UME 诊断，请稍候…",
    "sqlqueryume": "正在执行 UME SQL，请稍候…",
    "findtopologypaths": "正在查拓扑路径，请稍候…",
    "writexlsx": "正在写 Excel，请稍候…",
    "getmanagedne": "正在读取纳管网元信息，请稍候…",
    "getumene": "正在读取 UME 网元详情，请稍候…",
}

_LONG_TOOL_LABELS_EN: dict[str, str] = {
    "execmanagedne": "Running device CLI, please wait…",
    "listclitargets": "Listing CLI targets, please wait…",
    "umealarmxlsxreport": "Building alarm Excel, please wait…",
    "queryumealarms": "Querying UME alarms, please wait…",
    "queryumealarmsraw": "Querying UME alarms, please wait…",
    "aggregateumealarms": "Aggregating UME alarms, please wait…",
    "aggregateumealarmsraw": "Aggregating UME alarms, please wait…",
    "runumediagnostics": "Running UME diagnostics, please wait…",
    "sqlqueryume": "Running UME SQL, please wait…",
    "findtopologypaths": "Finding topology paths, please wait…",
    "writexlsx": "Writing Excel, please wait…",
    "getmanagedne": "Loading managed NE, please wait…",
    "getumene": "Loading UME NE detail, please wait…",
}


def whatsapp_turn_progress_enabled() -> bool:
    raw = str(os.environ.get("OCLAW_WHATSAPP_TURN_PROGRESS") or "").strip().lower()
    if not raw:
        return True
    return raw not in {"0", "false", "no", "off"}


def progress_min_interval_sec() -> float:
    """Default 45s — field turns often run multi-hop CLI for minutes."""
    raw = str(os.environ.get("OCLAW_WHATSAPP_PROGRESS_MIN_INTERVAL_SEC") or "").strip()
    try:
        return max(5.0, min(float(raw), 300.0))
    except Exception:
        return 45.0


def progress_max_per_turn() -> int:
    """Hard cap on interim WA ticks per inbound turn (final reply is separate)."""
    raw = str(os.environ.get("OCLAW_WHATSAPP_PROGRESS_MAX_PER_TURN") or "").strip()
    try:
        return max(0, min(int(raw), 20))
    except Exception:
        return 2


def normalize_tool_key(name: str) -> str:
    s = str(name or "").strip()
    if not s:
        return ""
    low = s.lower()
    if low.startswith("mcp__"):
        # mcp__netx__execManagedNe -> execmanagedne
        parts = low.split("__")
        if len(parts) >= 3:
            low = parts[-1]
    elif low.startswith("netx_"):
        low = low[len("netx_") :]
    return low.replace("_", "")


def humanize_long_tool(*, tool_name: str, lang: str = "en") -> str | None:
    key = normalize_tool_key(tool_name)
    if not key:
        return None
    # Field WhatsApp is English-first; only use Chinese when lang is explicitly zh.
    table = _LONG_TOOL_LABELS_ZH if str(lang or "").strip().lower().startswith("zh") else _LONG_TOOL_LABELS_EN
    return table.get(key)


def should_forward_progress_text(text: str) -> bool:
    """Filter noisy think/retry/composing ticks; keep rare meaningful waits only."""
    t = str(text or "").strip()
    if not t:
        return False
    low = t.lower()
    if low in {"oclaw: running…", "oclaw: running...", "oclaw: finalize…", "oclaw: finalize..."}:
        return False
    if "think (" in low or low.startswith("oclaw: think"):
        return False
    if "retry-empty" in low or "retry-native-tool-calls" in low:
        return False
    if "idle-guard" in low:
        return False
    # Mid-turn "tools done / composing" is the main WA spam pattern when CLI loops.
    if _TOOLS_DONE_RE.search(t) or "composing" in low or "整理回复" in t:
        return False
    # Specialist / other explicit progress lines (rare)
    if low.startswith("oclaw:"):
        return True
    return len(t) >= 8


def humanize_progress_text(*, text: str, lang: str = "en") -> str:
    t = str(text or "").strip()
    is_zh = str(lang or "").strip().lower().startswith("zh")
    # tools-done is filtered by should_forward; keep a soft fallback if callers bypass.
    if _TOOLS_DONE_RE.search(t):
        if is_zh:
            return "仍在处理，请稍候…"
        return "Still working, please wait…"
    if t.lower().startswith("oclaw:"):
        body = t.split(":", 1)[-1].strip()
        if is_zh:
            return f"处理中：{body}" if body else "处理中，请稍候…"
        return body or "Still working, please wait…"
    return t


def build_whatsapp_group_progress_metadata(*, inbound: Any) -> dict[str, Any]:
    """@sender without quoting (avoids sticky quote spam on interim ticks)."""
    from runtime.orchestration.group_ingest import build_whatsapp_group_reply_metadata

    meta = build_whatsapp_group_reply_metadata(inbound=inbound)
    for key in (
        "quote_remote_jid",
        "quote_stanza_id",
        "quote_participant",
        "quote_text",
        "quote_push_name",
    ):
        meta.pop(key, None)
    return meta


class WhatsappTurnProgressPublisher:
    """Enqueue throttled interim WhatsApp texts during a channel turn."""

    def __init__(
        self,
        *,
        enqueue: Callable[[str, dict[str, Any] | None], None],
        lang: str = "en",
        is_group: bool = False,
        inbound: Any = None,
        min_interval_sec: float | None = None,
        max_per_turn: int | None = None,
        enabled: bool | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._enqueue = enqueue
        self._lang = str(lang or "zh")
        self._is_group = bool(is_group)
        self._inbound = inbound
        self._min_interval = float(min_interval_sec if min_interval_sec is not None else progress_min_interval_sec())
        self._max_per_turn = int(max_per_turn if max_per_turn is not None else progress_max_per_turn())
        self._enabled = bool(whatsapp_turn_progress_enabled() if enabled is None else enabled)
        self._clock = clock or time.monotonic
        self._lock = threading.Lock()
        self._last_sent_at = 0.0
        self._last_text = ""
        self._sent_count = 0
        self._announced_tools: set[str] = set()

    @property
    def sent_count(self) -> int:
        return int(self._sent_count)

    def on_progress(self, text: str) -> None:
        if not self._enabled:
            return
        if not should_forward_progress_text(text):
            return
        msg = humanize_progress_text(text=text, lang=self._lang)
        self._maybe_send(msg)

    def on_tool_ui(self, event: str, payload: dict[str, Any] | None) -> None:
        if not self._enabled:
            return
        if str(event or "").strip() != "tool_use_call":
            return
        pl = payload if isinstance(payload, dict) else {}
        tool_name = str(pl.get("tool_name") or "")
        key = normalize_tool_key(tool_name)
        label = humanize_long_tool(tool_name=tool_name, lang=self._lang)
        if not label:
            return
        with self._lock:
            # Same long tool (e.g. repeated execManagedNe hops) → one WA tick only.
            if key and key in self._announced_tools:
                return
        if self._maybe_send(label) and key:
            with self._lock:
                self._announced_tools.add(key)

    def _reply_metadata(self) -> dict[str, Any] | None:
        if not self._is_group or self._inbound is None:
            return None
        try:
            return build_whatsapp_group_progress_metadata(inbound=self._inbound)
        except Exception:
            return None

    def _maybe_send(self, text: str) -> bool:
        msg = str(text or "").strip()
        if not msg:
            return False
        with self._lock:
            if self._max_per_turn >= 0 and self._sent_count >= self._max_per_turn:
                return False
            now = float(self._clock())
            if msg == self._last_text and self._sent_count > 0:
                return False
            if self._sent_count > 0 and (now - self._last_sent_at) < self._min_interval:
                return False
            try:
                self._enqueue(msg, self._reply_metadata())
            except Exception:
                return False
            self._last_sent_at = now
            self._last_text = msg
            self._sent_count += 1
            return True


__all__ = [
    "WhatsappTurnProgressPublisher",
    "build_whatsapp_group_progress_metadata",
    "humanize_long_tool",
    "humanize_progress_text",
    "normalize_tool_key",
    "progress_max_per_turn",
    "progress_min_interval_sec",
    "should_forward_progress_text",
    "whatsapp_turn_progress_enabled",
]
