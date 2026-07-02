from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from runtime.scheduler.system_timezone import default_system_timezone

try:
    from croniter import croniter
except ImportError:  # pragma: no cover - guarded in requirements
    croniter = None  # type: ignore[assignment,misc]


def normalize_schedule_kind(raw: Any) -> str:
    kind = str(raw or "").strip().lower()
    if kind in {"cron", "once", "interval"}:
        return kind
    return "cron"


def _parse_iso_dt(value: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("empty datetime")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def compute_next_run_at(
    *,
    schedule_kind: str,
    schedule_expr: str,
    timezone_name: str | None = None,
    from_dt: datetime | None = None,
) -> str | None:
    kind = normalize_schedule_kind(schedule_kind)
    expr = str(schedule_expr or "").strip()
    if not expr:
        return None
    base = from_dt or datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    else:
        base = base.astimezone(timezone.utc)

    if kind == "once":
        target = _parse_iso_dt(expr)
        if target <= base:
            return None
        return target.isoformat()

    if kind == "interval":
        try:
            seconds = max(1, int(expr))
        except ValueError as exc:
            raise ValueError(f"invalid interval seconds: {expr}") from exc
        nxt = base + timedelta(seconds=seconds)
        return nxt.isoformat()

    if croniter is None:
        raise RuntimeError("croniter is required for cron schedules")
    try:
        tz = ZoneInfo(str(timezone_name or default_system_timezone()))
    except Exception:
        tz = ZoneInfo(default_system_timezone())
    local_base = base.astimezone(tz)
    itr = croniter(expr, local_base)
    nxt_local = itr.get_next(datetime)
    if nxt_local.tzinfo is None:
        nxt_local = nxt_local.replace(tzinfo=tz)
    return nxt_local.astimezone(timezone.utc).isoformat()


__all__ = ["compute_next_run_at", "normalize_schedule_kind"]
