"""Rate-limited WhatsApp interim progress during long channel turns."""

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
    raw = str(os.environ.get("OCLAW_WHATSAPP_PROGRESS_MIN_INTERVAL_SEC") or "").strip()
    try:
        return max(3.0, min(float(raw), 120.0))
    except Exception:
        return 12.0


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


def humanize_long_tool(*, tool_name: str, lang: str = "zh") -> str | None:
    key = normalize_tool_key(tool_name)
    if not key:
        return None
    table = _LONG_TOOL_LABELS_EN if str(lang or "").startswith("en") else _LONG_TOOL_LABELS_ZH
    # Keys in tables are already underscore-free lower names.
    return table.get(key)


def should_forward_progress_text(text: str) -> bool:
    """Filter noisy think/retry ticks; keep meaningful wait signals."""
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
    m = _TOOLS_DONE_RE.search(t)
    if m:
        try:
            return int(m.group(1)) >= 8000
        except Exception:
            return False
    # Specialist / other explicit progress lines
    if low.startswith("oclaw:"):
        return True
    return len(t) >= 8


def humanize_progress_text(*, text: str, lang: str = "zh") -> str:
    t = str(text or "").strip()
    m = _TOOLS_DONE_RE.search(t)
    if m:
        if str(lang or "").startswith("en"):
            return "Tools finished; composing the reply…"
        return "工具已完成，正在整理回复…"
    if t.lower().startswith("oclaw:"):
        body = t.split(":", 1)[-1].strip()
        if str(lang or "").startswith("en"):
            return body or t
        # Keep short Chinese-friendly wait copy for unknown oclaw:* lines.
        return f"处理中：{body}" if body else "处理中，请稍候…"
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
        lang: str = "zh",
        is_group: bool = False,
        inbound: Any = None,
        min_interval_sec: float | None = None,
        enabled: bool | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._enqueue = enqueue
        self._lang = str(lang or "zh")
        self._is_group = bool(is_group)
        self._inbound = inbound
        self._min_interval = float(min_interval_sec if min_interval_sec is not None else progress_min_interval_sec())
        self._enabled = bool(whatsapp_turn_progress_enabled() if enabled is None else enabled)
        self._clock = clock or time.monotonic
        self._lock = threading.Lock()
        self._last_sent_at = 0.0
        self._last_text = ""
        self._sent_count = 0

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
        label = humanize_long_tool(tool_name=str(pl.get("tool_name") or ""), lang=self._lang)
        if not label:
            return
        self._maybe_send(label)

    def _reply_metadata(self) -> dict[str, Any] | None:
        if not self._is_group or self._inbound is None:
            return None
        try:
            return build_whatsapp_group_progress_metadata(inbound=self._inbound)
        except Exception:
            return None

    def _maybe_send(self, text: str) -> None:
        msg = str(text or "").strip()
        if not msg:
            return
        with self._lock:
            now = float(self._clock())
            if msg == self._last_text and self._sent_count > 0:
                return
            if self._sent_count > 0 and (now - self._last_sent_at) < self._min_interval:
                return
            try:
                self._enqueue(msg, self._reply_metadata())
            except Exception:
                return
            self._last_sent_at = now
            self._last_text = msg
            self._sent_count += 1


__all__ = [
    "WhatsappTurnProgressPublisher",
    "build_whatsapp_group_progress_metadata",
    "humanize_long_tool",
    "humanize_progress_text",
    "normalize_tool_key",
    "progress_min_interval_sec",
    "should_forward_progress_text",
    "whatsapp_turn_progress_enabled",
]
