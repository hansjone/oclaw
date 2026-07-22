"""Per-session serial queue: one active turn; overlaps enqueue and merge on drain."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChannelTurnHandle:
    session_id: str
    run_id: str


@dataclass
class _SessionState:
    active_run_id: str = ""
    pending: list[dict[str, Any]] = field(default_factory=list)


def merge_channel_pending_jobs(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge queued follow-ups into one job for the next agent turn."""
    rows = [j for j in (jobs or []) if isinstance(j, dict)]
    if not rows:
        return {}
    if len(rows) == 1:
        return dict(rows[0])

    lang = str(rows[-1].get("lang") or "").strip().lower()
    if lang.startswith("zh"):
        header = "处理上一问期间又收到多条跟进，请一并回答："
    else:
        header = "Several follow-up questions arrived while the previous request was still running. Please answer them together:"

    parts: list[str] = []
    attachments: list[dict[str, Any]] = []
    for idx, job in enumerate(rows, start=1):
        text = str(job.get("user_text") or "").strip()
        if text:
            parts.append(f"{idx}) {text}")
        for att in job.get("attachments") or []:
            if isinstance(att, dict):
                attachments.append(att)

    merged = dict(rows[-1])
    body = "\n\n".join(parts) if parts else ""
    merged["user_text"] = f"{header}\n\n{body}".strip() if body else header
    merged["attachments"] = attachments
    merged["merged_count"] = len(rows)
    return merged


class ChannelTurnGate:
    """Serialize channel agent turns per session_id.

    - Idle ``try_begin``: start a turn immediately.
    - Busy ``try_begin``: append job to pending and return None (caller returns quickly).
    - ``end_and_take_merged``: clear active; if pending exists, merge all into one job and
      start the next turn handle for the same HTTP request to continue.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, _SessionState] = {}

    def try_begin(self, session_id: str, job: dict[str, Any]) -> ChannelTurnHandle | None:
        sid = str(session_id or "").strip()
        if not sid:
            raise ValueError("session_id_required")
        payload = dict(job or {})
        with self._lock:
            st = self._sessions.get(sid)
            if st is None:
                st = _SessionState()
                self._sessions[sid] = st
            if st.active_run_id:
                st.pending.append(payload)
                return None
            run_id = uuid.uuid4().hex
            st.active_run_id = run_id
            return ChannelTurnHandle(session_id=sid, run_id=run_id)

    def is_current(self, handle: ChannelTurnHandle) -> bool:
        sid = str(handle.session_id or "").strip()
        rid = str(handle.run_id or "").strip()
        if not sid or not rid:
            return False
        with self._lock:
            st = self._sessions.get(sid)
            return bool(st and st.active_run_id == rid)

    def pending_count(self, session_id: str) -> int:
        sid = str(session_id or "").strip()
        with self._lock:
            st = self._sessions.get(sid)
            return len(st.pending) if st else 0

    def end_and_take_merged(self, handle: ChannelTurnHandle) -> tuple[dict[str, Any] | None, ChannelTurnHandle | None]:
        """Finish current turn. If queue non-empty, merge and return (merged_job, next_handle)."""
        sid = str(handle.session_id or "").strip()
        rid = str(handle.run_id or "").strip()
        if not sid or not rid:
            return None, None
        with self._lock:
            st = self._sessions.get(sid)
            if st is None or st.active_run_id != rid:
                return None, None
            pending = list(st.pending)
            st.pending.clear()
            if not pending:
                st.active_run_id = ""
                self._sessions.pop(sid, None)
                return None, None
            merged = merge_channel_pending_jobs(pending)
            next_id = uuid.uuid4().hex
            st.active_run_id = next_id
            return merged, ChannelTurnHandle(session_id=sid, run_id=next_id)

    def force_end(self, handle: ChannelTurnHandle) -> None:
        """Drop active marker if still ours (error paths). Pending jobs are kept."""
        sid = str(handle.session_id or "").strip()
        rid = str(handle.run_id or "").strip()
        if not sid or not rid:
            return
        with self._lock:
            st = self._sessions.get(sid)
            if st is None or st.active_run_id != rid:
                return
            st.active_run_id = ""
            if not st.pending:
                self._sessions.pop(sid, None)


_GATE = ChannelTurnGate()


def get_channel_turn_gate() -> ChannelTurnGate:
    return _GATE


def reset_channel_turn_gate_for_tests() -> ChannelTurnGate:
    global _GATE
    _GATE = ChannelTurnGate()
    return _GATE


__all__ = [
    "ChannelTurnGate",
    "ChannelTurnHandle",
    "get_channel_turn_gate",
    "merge_channel_pending_jobs",
    "reset_channel_turn_gate_for_tests",
]
