from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

from .shared_types import GatewayRequestHandlers
from .validation import error_shape

COST_USAGE_CACHE_TTL_MS = 30_000
DAY_MS = 24 * 60 * 60 * 1000
_cost_usage_cache: dict[str, dict[str, Any]] = {}


def _ok(respond, payload: Any, meta: dict[str, Any] | None = None) -> None:
    if callable(respond):
        respond(True, payload, None, meta or None)


def _bad(respond, message: str) -> None:
    if callable(respond):
        respond(False, None, error_shape("INVALID_REQUEST", message), None)


def _unavailable(respond, message: str) -> None:
    if callable(respond):
        respond(False, None, error_shape("UNAVAILABLE", message), None)


def _parse_date_parts(raw: Any) -> tuple[int, int, int] | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        dt = datetime.strptime(raw.strip(), "%Y-%m-%d")
    except ValueError:
        return None
    return dt.year, dt.month, dt.day


def _parse_utc_offset_minutes(raw: Any) -> int | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()
    if not text.startswith("UTC"):
        return None
    sign_part = text[3:4]
    if sign_part not in {"+", "-"}:
        return None
    rest = text[4:]
    if ":" in rest:
        hh_s, mm_s = rest.split(":", 1)
    else:
        hh_s, mm_s = rest, "0"
    try:
        hh = int(hh_s)
        mm = int(mm_s)
    except ValueError:
        return None
    if hh > 14 or mm < 0 or mm >= 60:
        return None
    total = hh * 60 + mm
    if sign_part == "-":
        total = -total
    if total < -12 * 60 or total > 14 * 60:
        return None
    return total


def _resolve_date_mode(params: dict[str, Any]) -> dict[str, Any]:
    mode = params.get("mode")
    if mode == "gateway":
        return {"mode": "gateway"}
    if mode == "specific":
        offset = _parse_utc_offset_minutes(params.get("utcOffset"))
        if offset is not None:
            return {"mode": "specific", "utcOffsetMinutes": offset}
    return {"mode": "utc"}


def _parse_date_to_ms(raw: Any, interpretation: dict[str, Any]) -> int | None:
    parts = _parse_date_parts(raw)
    if not parts:
        return None
    y, m, d = parts
    if interpretation["mode"] == "gateway":
        return int(datetime(y, m, d).timestamp() * 1000)
    if interpretation["mode"] == "specific":
        offset = interpretation["utcOffsetMinutes"]
        base = datetime(y, m, d, tzinfo=timezone.utc).timestamp() * 1000
        return int(base - offset * 60 * 1000)
    return int(datetime(y, m, d, tzinfo=timezone.utc).timestamp() * 1000)


def _today_start_ms(now: datetime, interpretation: dict[str, Any]) -> int:
    if interpretation["mode"] == "gateway":
        local = datetime(now.year, now.month, now.day)
        return int(local.timestamp() * 1000)
    if interpretation["mode"] == "specific":
        offset = interpretation["utcOffsetMinutes"]
        shifted = now + timedelta(minutes=offset)
        start = datetime(shifted.year, shifted.month, shifted.day, tzinfo=timezone.utc)
        return int(start.timestamp() * 1000) - offset * 60 * 1000
    start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    return int(start.timestamp() * 1000)


def _parse_days(raw: Any) -> int | None:
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            return int(float(raw.strip()))
        except ValueError:
            return None
    return None


def _parse_date_range(params: dict[str, Any]) -> dict[str, int]:
    now = datetime.now(timezone.utc)
    interpretation = _resolve_date_mode(params)
    today_start = _today_start_ms(now, interpretation)
    today_end = today_start + DAY_MS - 1

    start_ms = _parse_date_to_ms(params.get("startDate"), interpretation)
    end_ms = _parse_date_to_ms(params.get("endDate"), interpretation)
    if start_ms is not None and end_ms is not None:
        return {"startMs": start_ms, "endMs": end_ms + DAY_MS - 1}

    days = _parse_days(params.get("days"))
    if days is not None:
        clamped = max(1, days)
        return {"startMs": today_start - (clamped - 1) * DAY_MS, "endMs": today_end}

    return {"startMs": today_start - 29 * DAY_MS, "endMs": today_end}


def _load_cost_usage_summary_cached(start_ms: int, end_ms: int, context: Any) -> tuple[dict[str, Any], bool]:
    cache_key = f"{start_ms}-{end_ms}"
    now_ms = int(time.time() * 1000)
    cached = _cost_usage_cache.get(cache_key)
    if cached and now_ms - int(cached.get("updatedAt", 0)) < COST_USAGE_CACHE_TTL_MS:
        return dict(cached.get("summary") or {}), True

    hook = context.get("load_cost_usage_summary") if isinstance(context, dict) else None
    if callable(hook):
        summary = hook({"startMs": start_ms, "endMs": end_ms})
        if not isinstance(summary, dict):
            summary = {}
    else:
        summary = {
            "startMs": start_ms,
            "endMs": end_ms,
            "totals": {
                "input": 0,
                "output": 0,
                "cacheRead": 0,
                "cacheWrite": 0,
                "totalTokens": 0,
                "totalCost": 0,
            },
        }
    _cost_usage_cache[cache_key] = {"summary": summary, "updatedAt": now_ms}
    return summary, False


def _usage_status_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    context = opts.get("context")
    hook = context.get("load_provider_usage_summary") if isinstance(context, dict) else None
    try:
        summary = hook() if callable(hook) else {"providers": [], "generatedAt": int(time.time() * 1000)}
        _ok(respond, summary if isinstance(summary, dict) else {})
    except Exception as exc:
        _unavailable(respond, str(exc))


def _usage_cost_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params") or {}
    context = opts.get("context")
    if params is not None and not isinstance(params, dict):
        _bad(respond, "invalid usage.cost params")
        return
    date_range = _parse_date_range(dict(params))
    try:
        summary, was_cached = _load_cost_usage_summary_cached(date_range["startMs"], date_range["endMs"], context)
        _ok(respond, summary, {"cached": True} if was_cached else None)
    except Exception as exc:
        _unavailable(respond, str(exc))


def _sessions_usage_handler(opts: dict[str, Any]) -> None:
    respond = opts.get("respond")
    params = opts.get("params") or {}
    context = opts.get("context")
    if not isinstance(params, dict):
        _bad(respond, "invalid sessions.usage params")
        return
    limit = params.get("limit")
    limit = int(limit) if isinstance(limit, (int, float)) and not isinstance(limit, bool) else 50
    limit = max(1, min(limit, 500))
    specific_key = params.get("key")
    if specific_key is not None and not isinstance(specific_key, str):
        _bad(respond, "invalid sessions.usage params")
        return
    date_range = _parse_date_range(params)

    hook = context.get("load_sessions_usage") if isinstance(context, dict) else None
    if callable(hook):
        try:
            out = hook(
                {
                    "startMs": date_range["startMs"],
                    "endMs": date_range["endMs"],
                    "limit": limit,
                    "key": specific_key,
                    "includeContextWeight": bool(params.get("includeContextWeight", False)),
                }
            )
            _ok(respond, out if isinstance(out, dict) else {"sessions": [], "aggregates": {}, "range": date_range})
            return
        except Exception as exc:
            _unavailable(respond, str(exc))
            return

    payload = {
        "sessions": ([] if not specific_key else [{"key": specific_key, "sessionId": specific_key, "updatedAt": date_range["endMs"]}])[:limit],
        "aggregates": {
            "totals": {
                "input": 0,
                "output": 0,
                "cacheRead": 0,
                "cacheWrite": 0,
                "totalTokens": 0,
                "totalCost": 0,
                "missingCostEntries": 0,
            },
            "messages": {
                "total": 0,
                "user": 0,
                "assistant": 0,
                "toolCalls": 0,
                "toolResults": 0,
                "errors": 0,
            },
            "tools": [],
            "byModel": [],
            "byProvider": [],
            "byAgent": [],
            "byChannel": [],
            "daily": [],
            "latency": None,
            "dailyLatency": [],
            "modelDaily": [],
            "aggregateTail": [],
        },
        "range": date_range,
        "limit": limit,
    }
    _ok(respond, payload)


usage_handlers: GatewayRequestHandlers = {
    "usage.status": _usage_status_handler,
    "usage.cost": _usage_cost_handler,
    "sessions.usage": _sessions_usage_handler,
}

