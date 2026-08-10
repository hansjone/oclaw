"""Always-on ops tool: query UME alarms → xlsx → optional channel deliverable in one call.

Uses shared ``netx_http`` (same REST base as MCP). MCP remains the primary interactive
query path; this collapses the WhatsApp “export Excel” loop into one tool call.
"""

from __future__ import annotations

from typing import Any

from runtime.tools.base import ToolSpec
from runtime.tools.experts.network_ops import netx_http as nt
from runtime.tools.public.write_xlsx_tool import write_xlsx_tool

_LIST_FIELDS = [
    "alarm_host_name",
    "alarm_perceived_severity",
    "alarm_event_type",
    "alarm_native_probable_cause",
    "alarm_object_name",
    "alarm_last_seen_at",
    "alarm_is_cleared",
    "ne_ip_address",
]

# Server keyword is single-substring; presets filter client-side after a wider pull.
_PRESET_CLIENT_TERMS: dict[str, tuple[str, ...]] = {
    "fiber_cut": ("los", "fiber", "断纤", "光缆", "光路", "optical"),
    "offline": ("离线", "offline", "通信中断", "单板离线", "ne communication"),
}

_MODE_DEFAULT_NAMES: dict[str, str] = {
    "list": "ume_alarms.xlsx",
    "aggregate_by_host": "ume_alarms_by_host.xlsx",
    "fiber_cut": "fiber_cut_alarms.xlsx",
    "offline": "offline_ne_alarms.xlsx",
}


def _truthy(v: Any, *, default: bool = False) -> bool:
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"1", "true", "yes", "on"}


def _host_label(row: dict[str, Any]) -> str:
    for k in ("alarm_host_name", "host_name", "ne_host_name", "ne_user_label"):
        val = str(row.get(k) or "").strip()
        if val:
            return val
    return "(host_name missing)"


def _row_blob(row: dict[str, Any]) -> str:
    parts = [
        row.get("alarm_event_type"),
        row.get("event_type"),
        row.get("alarm_native_probable_cause"),
        row.get("native_probable_cause"),
        row.get("alarm_object_name"),
        row.get("object_name"),
        row.get("alarm_alarm_key"),
        row.get("alarm_key"),
    ]
    return " ".join(str(x or "") for x in parts).lower()


def _filter_preset_items(mode: str, items: list[Any]) -> list[dict[str, Any]]:
    terms = _PRESET_CLIENT_TERMS.get(mode)
    if not terms:
        return [x for x in items if isinstance(x, dict)]
    out: list[dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        blob = _row_blob(raw)
        if any(t.lower() in blob for t in terms):
            out.append(raw)
    return out


def _rows_from_list_items(items: list[Any]) -> tuple[list[str], list[list[Any]]]:
    headers = [
        "host_name",
        "severity",
        "event_type",
        "probable_cause",
        "object_name",
        "last_seen_at",
        "is_cleared",
        "ip",
    ]
    rows: list[list[Any]] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        rows.append(
            [
                _host_label(raw),
                raw.get("alarm_perceived_severity") or raw.get("perceived_severity") or "",
                raw.get("alarm_event_type") or raw.get("event_type") or "",
                raw.get("alarm_native_probable_cause") or raw.get("native_probable_cause") or "",
                raw.get("alarm_object_name") or raw.get("object_name") or "",
                raw.get("alarm_last_seen_at") or raw.get("last_seen_at") or "",
                raw.get("alarm_is_cleared") if "alarm_is_cleared" in raw else raw.get("is_cleared"),
                raw.get("ne_ip_address") or raw.get("ip_address") or "",
            ]
        )
    return headers, rows


def _rows_from_aggregate_buckets(data: dict[str, Any]) -> tuple[list[str], list[list[Any]], dict[str, Any]]:
    headers = ["host_name", "count"]
    rows: list[list[Any]] = []
    # raw aggregate returns buckets as list of {key/keys, count} or similar
    buckets = data.get("buckets")
    if isinstance(buckets, list):
        for b in buckets:
            if not isinstance(b, dict):
                continue
            key = b.get("key")
            if key is None and isinstance(b.get("keys"), (list, tuple)) and b.get("keys"):
                key = b["keys"][0]
            if key is None:
                key = b.get("alarm_host_name") or b.get("host_name") or b.get("group")
            rows.append([str(key or "(host_name missing)"), int(b.get("count") or b.get("n") or 0)])
    elif isinstance(data.get("by_ne"), list):
        for b in data["by_ne"]:
            if not isinstance(b, dict):
                continue
            rows.append(
                [
                    str(b.get("host_name") or b.get("ne") or b.get("key") or "(host_name missing)"),
                    int(b.get("count") or b.get("n") or 0),
                ]
            )
    meta = {
        "total": data.get("total"),
        "by_ne_missing": data.get("by_ne_missing"),
        "group_by": data.get("group_by") or "alarm_host_name",
        "meta": data.get("meta"),
    }
    return headers, rows, meta


def _fetch_list(*, keyword: str, severity: str, time_from: str, time_to: str, page_size: int) -> dict[str, Any]:
    params: dict[str, Any] = {
        "page": 1,
        "page_size": page_size,
        "select_fields": ",".join(_LIST_FIELDS),
    }
    if keyword:
        params["keyword"] = keyword
    if severity:
        params["severity"] = severity
    if time_from:
        params["time_from"] = time_from
    if time_to:
        params["time_to"] = time_to
    return nt._http_json("GET", "/v1/ume/alarms/raw", params=params)


def _fetch_aggregate_by_host(
    *, severity: str, keyword: str, time_from: str, time_to: str, limit: int
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "group_by": "alarm_host_name",
        "limit": limit,
        "exclude_missing_host": True,
    }
    if severity:
        params["severity"] = severity
    if keyword:
        params["keyword"] = keyword
    if time_from:
        params["time_from"] = time_from
    if time_to:
        params["time_to"] = time_to
    return nt._http_json("GET", "/v1/ume/alarms/aggregate/raw", params=params)


def ume_alarm_xlsx_report_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        mode = str(args.get("mode") or "list").strip().lower() or "list"
        if mode not in _MODE_DEFAULT_NAMES:
            return {
                "ok": False,
                "error": "invalid_mode",
                "allowed": sorted(_MODE_DEFAULT_NAMES.keys()),
            }

        severity = str(args.get("severity") or "").strip()
        keyword = str(args.get("keyword") or "").strip()
        time_from = str(args.get("time_from") or "").strip()
        time_to = str(args.get("time_to") or "").strip()
        page_size = max(1, min(500, int(args.get("page_size") or args.get("limit") or 100)))
        # Preset modes pull a wider page then filter client-side (API keyword is single substring).
        fetch_size = page_size
        if mode in _PRESET_CLIENT_TERMS and not keyword:
            fetch_size = max(page_size, min(500, page_size * 3))
        deliverable = _truthy(args.get("deliverable"), default=True)
        filename = str(args.get("name") or args.get("filename") or "").strip() or _MODE_DEFAULT_NAMES[mode]
        if not filename.lower().endswith(".xlsx"):
            filename = f"{filename}.xlsx"

        sheet_name = "alarms"
        summary_meta: dict[str, Any] = {"mode": mode, "keyword": keyword or None, "severity": severity or None}

        if mode == "aggregate_by_host":
            upstream = _fetch_aggregate_by_host(
                severity=severity,
                keyword=keyword,
                time_from=time_from,
                time_to=time_to,
                limit=page_size,
            )
            if not upstream.get("ok"):
                return {"ok": False, "error": "ume_query_failed", "upstream": upstream}
            data = upstream.get("data") if isinstance(upstream.get("data"), dict) else {}
            headers, rows, agg_meta = _rows_from_aggregate_buckets(data)
            summary_meta.update(agg_meta)
            sheet_name = "by_host"
        else:
            # list / fiber_cut / offline share raw list path
            upstream = _fetch_list(
                keyword=keyword,
                severity=severity,
                time_from=time_from,
                time_to=time_to,
                page_size=fetch_size,
            )
            if not upstream.get("ok"):
                return {"ok": False, "error": "ume_query_failed", "upstream": upstream}
            data = upstream.get("data") if isinstance(upstream.get("data"), dict) else {}
            items = data.get("items") if isinstance(data.get("items"), list) else []
            if mode in _PRESET_CLIENT_TERMS and not keyword:
                items = _filter_preset_items(mode, items)[:page_size]
            headers, rows = _rows_from_list_items(items)
            summary_meta["total"] = data.get("total")
            summary_meta["returned"] = len(rows)
            summary_meta["meta"] = data.get("meta")
            if mode == "fiber_cut":
                sheet_name = "fiber_cut"
            elif mode == "offline":
                sheet_name = "offline"

        xlsx = write_xlsx_tool().handler(
            {
                "name": filename,
                "deliverable": deliverable,
                "sheets": [{"name": sheet_name, "headers": headers, "rows": rows}],
            }
        )
        if not xlsx.get("ok"):
            return {"ok": False, "error": "xlsx_build_failed", "detail": xlsx}

        return {
            "ok": True,
            "attachment_id": xlsx.get("attachment_id"),
            "name": xlsx.get("name"),
            "mime": xlsx.get("mime"),
            "bytes": xlsx.get("bytes"),
            "deliverable": bool(xlsx.get("deliverable")),
            "row_count": len(rows),
            "columns": headers,
            "summary": summary_meta,
            "hint": (
                "Report ready and marked deliverable for channel send."
                if deliverable
                else "Report saved; call save_deliverable_attachment to send on WhatsApp."
            ),
        }

    return ToolSpec(
        name="ume_alarm_xlsx_report",
        description=(
            "One-shot UME alarm Excel for WhatsApp ops: query netx alarms and build .xlsx "
            "(optionally mark deliverable). Modes: list, aggregate_by_host, fiber_cut, offline. "
            "Prefer this over query+write_xlsx+save_deliverable_attachment for short WA requests."
        ),
        parameters={
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["list", "aggregate_by_host", "fiber_cut", "offline"],
                    "default": "list",
                    "description": (
                        "list=raw alarm rows; aggregate_by_host=count by host_name; "
                        "fiber_cut/offline=preset keyword filters for common WA intents."
                    ),
                },
                "severity": {
                    "type": "string",
                    "description": "Optional perceived_severity filter (critical/major/minor/warning).",
                },
                "keyword": {
                    "type": "string",
                    "description": "Optional keyword; fiber_cut/offline apply defaults when omitted.",
                },
                "time_from": {"type": "string", "description": "ISO time; filters last_seen_at >="},
                "time_to": {"type": "string", "description": "ISO time; filters last_seen_at <="},
                "page_size": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 500,
                    "default": 100,
                    "description": "Max rows / aggregate buckets (alias: limit).",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 500,
                    "description": "Alias for page_size.",
                },
                "name": {
                    "type": "string",
                    "description": "Output filename, e.g. fiber_cut.xlsx",
                },
                "filename": {"type": "string", "description": "Alias for name."},
                "deliverable": {
                    "type": "boolean",
                    "default": True,
                    "description": "Mark for WhatsApp/WeChat delivery (default true).",
                },
            },
            "required": [],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"netx", "ops", "ume", "alarms", "xlsx", "attachment"}),
        read_only=False,
        risk_level="low",
        timeout_s=90.0,
    )


__all__ = ["ume_alarm_xlsx_report_tool"]
