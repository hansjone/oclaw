from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SessionContextStats:
    session_id: str
    total_messages: int
    sampled_messages: int
    last_n: int

    last_n_total_chars: int
    last_n_tool_total_chars: int
    last_n_max_msg_chars: int
    last_n_max_tool_chars: int
    last_n_max_user_chars: int

    empty_assistant_text_in_sampled: int
    empty_assistant_text_ids: tuple[int, ...]

    max_content_chars_in_sampled: int
    max_tool_chars_in_sampled: int


def compute_session_context_stats(
    *,
    store: Any,
    session_id: str,
    sample_n: int = 120,
    last_n: int = 80,
) -> SessionContextStats:
    """Compute lightweight DB-backed stats for diagnosing context overflow vs empty responses.

    This intentionally only inspects DB text lengths (not token counts).
    """
    sid = str(session_id or "").strip()
    if not sid:
        raise ValueError("session_id required")
    sample_n = max(1, min(int(sample_n or 120), 2000))
    last_n = max(1, min(int(last_n or 80), 2000))

    total = 0
    sampled_rows: list[tuple[int, str, str, int]] = []
    last_rows: list[tuple[int, str, str, int]] = []
    try:
        # Prefer raw SQL to avoid store-level object hydration overhead.
        with store._connect() as conn:  # noqa: SLF001
            cur = conn.execute("select count(1) from chat_message where session_id=?", (sid,))
            total = int((cur.fetchone() or [0])[0] or 0)
            cur = conn.execute(
                "select id, role, event_type, coalesce(length(content),0) as n "
                "from chat_message where session_id=? order by id desc limit ?",
                (sid, int(sample_n)),
            )
            sampled_rows = [(int(r[0]), str(r[1] or ""), str(r[2] or ""), int(r[3] or 0)) for r in (cur.fetchall() or [])]
            cur = conn.execute(
                "select id, role, event_type, coalesce(length(content),0) as n "
                "from chat_message where session_id=? order by id desc limit ?",
                (sid, int(last_n)),
            )
            last_rows = [(int(r[0]), str(r[1] or ""), str(r[2] or ""), int(r[3] or 0)) for r in (cur.fetchall() or [])]
    except Exception:
        # Fallback path via store API if direct SQL fails for any reason.
        msgs = list(store.get_messages(session_id=sid, limit=int(sample_n)))
        total = len(msgs)
        sampled_rows = [
            (int(getattr(m, "id", 0) or 0), str(getattr(m, "role", "") or ""), str(getattr(m, "event_type", "") or ""), len(str(getattr(m, "content", "") or "")))
            for m in msgs
        ]
        last_rows = sampled_rows[: int(last_n)]

    empty_ids = tuple(sorted([mid for mid, role, ev, n in sampled_rows if role == "assistant" and ev == "assistant_text" and int(n) == 0]))
    max_content = max([n for *_rest, n in sampled_rows] or [0])
    max_tool = max([n for _mid, role, _ev, n in sampled_rows if role == "tool"] or [0])

    last_total = sum(int(n) for *_rest, n in last_rows)
    last_tool_total = sum(int(n) for _mid, role, _ev, n in last_rows if role == "tool")
    last_max = max([int(n) for *_rest, n in last_rows] or [0])
    last_tool_max = max([int(n) for _mid, role, _ev, n in last_rows if role == "tool"] or [0])
    last_user_max = max([int(n) for _mid, role, _ev, n in last_rows if role == "user"] or [0])

    return SessionContextStats(
        session_id=sid,
        total_messages=int(total),
        sampled_messages=len(sampled_rows),
        last_n=int(last_n),
        last_n_total_chars=int(last_total),
        last_n_tool_total_chars=int(last_tool_total),
        last_n_max_msg_chars=int(last_max),
        last_n_max_tool_chars=int(last_tool_max),
        last_n_max_user_chars=int(last_user_max),
        empty_assistant_text_in_sampled=len(empty_ids),
        empty_assistant_text_ids=empty_ids,
        max_content_chars_in_sampled=int(max_content),
        max_tool_chars_in_sampled=int(max_tool),
    )


__all__ = [
    "SessionContextStats",
    "compute_session_context_stats",
]

