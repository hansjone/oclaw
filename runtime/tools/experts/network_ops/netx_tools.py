"""netx ops helpers: runtime context inject for ops specialist.

Alarm/NE tools are exposed only via stdio MCP (``mcp__netx__*``).
HTTP helpers live in ``netx_http`` (shared with ``ume_alarm_xlsx_report``).

Configure via environment:
- ``NETX_API_URL`` or ``OCLAW_NETX_BASE_URL`` (default ``http://127.0.0.1:8890``)
- ``OCLAW_NETX_API_TOKEN`` / ``NETX_API_TOKEN`` (optional Bearer)
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

from runtime.tools.experts.network_ops.netx_http import (
    NETX_TOOL_LANG,
    _http_json,
    _http_post_json,
    _localize_netx_payload,
    _netx_base_url,
    _netx_headers,
)

__all__ = [
    "NETX_TOOL_LANG",
    "ops_netx_system_context_extension",
    "_http_json",
    "_http_post_json",
    "_localize_netx_payload",
    "_netx_base_url",
    "_netx_headers",
]


def _resolve_ume_anchor() -> dict[str, Any]:
    """Resolve current UME alarm anchor from netx sync status."""
    r = _http_json("GET", "/v1/ume/sync/status", params={"page": 1, "page_size": 20})
    if not r.get("ok"):
        return {"ok": False, "error": "netx_ume_sync_status_failed", "detail": r.get("detail"), "upstream": r}
    data = r.get("data") or {}
    latest = data.get("latest_by_domain") if isinstance(data.get("latest_by_domain"), dict) else {}
    cur = latest.get("alarms_current") if isinstance(latest.get("alarms_current"), dict) else {}
    return {
        "ok": True,
        "anchor": {
            "domain": "alarms_current",
            "status": str(cur.get("status") or ""),
            "trigger_mode": str(cur.get("trigger_mode") or ""),
            "started_at": str(cur.get("started_at") or ""),
            "ended_at": str(cur.get("ended_at") or ""),
            "pulled_count": int(cur.get("pulled_count") or 0),
            "inserted_count": int(cur.get("inserted_count") or 0),
            "updated_count": int(cur.get("updated_count") or 0),
            "error_message": str(cur.get("error_message") or ""),
        },
    }


_OPS_NETX_SYS_CTX_LOCK = threading.Lock()
# Lang code -> (monotonic_ts, formatted extension text); short TTL to avoid hammering netx each tool round.
_OPS_NETX_SYS_CTX_CACHE: dict[str, tuple[float, str]] = {}
_OPS_NETX_SYS_CTX_TTL_SEC = 5.0


def _format_ops_netx_system_extension(r: dict[str, Any], *, lang_en: bool) -> str:
    if r.get("ok"):
        row = r.get("anchor") if isinstance(r.get("anchor"), dict) else {}
        status = str(row.get("status") or "")
        mode = str(row.get("trigger_mode") or "")
        started = str(row.get("started_at") or "")
        ended = str(row.get("ended_at") or "")
        pulled = int(row.get("pulled_count") or 0)
        inserted = int(row.get("inserted_count") or 0)
        updated = int(row.get("updated_count") or 0)
        err = str(row.get("error_message") or "").strip()
        lines_en = [
            "[Netx UME current-alarms anchor]",
            f"- status: {status}",
            f"- trigger_mode: {mode}",
            f"- started_at: {started}",
            f"- ended_at: {ended}",
        ]
        lines_zh = [
            "[当前 netx UME告警锚点]",
            f"- 状态: {status}",
            f"- 触发方式: {mode}",
            f"- 开始时间: {started}",
            f"- 结束时间: {ended}",
        ]
        (lines_en if lang_en else lines_zh).append(
            f"- pulled/inserted/updated: {pulled}/{inserted}/{updated}"
            if lang_en
            else f"- 拉取/新增/更新: {pulled}/{inserted}/{updated}"
        )
        if err:
            (lines_en if lang_en else lines_zh).append(
                f"- last_error: {err[:200]}" if lang_en else f"- 最近错误: {err[:200]}"
            )
        tail_en = (
            "- MCP tools (server_id=netx): mcp__netx__queryUmeAlarms, mcp__netx__aggregateUmeAlarms, "
            "mcp__netx__runUmeDiagnostics, mcp__netx__queryUmeNeInventory, mcp__netx__getUmeNe, "
            "mcp__netx__queryUmeAlarmsRaw, mcp__netx__aggregateUmeAlarmsRaw, mcp__netx__listUmeAlarmFields, "
            "mcp__netx__sqlQueryUme, mcp__netx__listManagedNe, mcp__netx__getManagedNe, mcp__netx__execManagedNe\n"
            "- note: this is only runtime anchor; use tools for alarm/ne evidence.\n"
            "- English session: user-visible reply must contain NO Chinese/CJK; translate alarm text fields."
        )
        tail_zh = (
            "- MCP 工具（server_id=netx）：mcp__netx__queryUmeAlarms、mcp__netx__aggregateUmeAlarms、"
            "mcp__netx__runUmeDiagnostics、mcp__netx__queryUmeNeInventory、mcp__netx__getUmeNe、"
            "mcp__netx__queryUmeAlarmsRaw、mcp__netx__aggregateUmeAlarmsRaw、mcp__netx__listUmeAlarmFields、"
            "mcp__netx__sqlQueryUme、mcp__netx__listManagedNe、mcp__netx__getManagedNe、mcp__netx__execManagedNe\n"
            "- 说明: 此处仅为运行锚点；具体告警/网元信息必须以工具返回为准，勿臆测。"
        )
        return "\n".join(lines_en + [tail_en]) if lang_en else "\n".join(lines_zh + [tail_zh])
    err = str(r.get("error") or "")
    detail = str(r.get("detail") or "")[:240]
    if lang_en:
        return (
            "[Netx UME current-alarms anchor]\n"
            f"- error: {err}\n"
            f"- detail: {detail}\n"
            "- fix: check NETX_API_URL (or OCLAW_NETX_BASE_URL) and that netx API is reachable; "
            "ensure MCP server_id=netx is bound and synced."
        )
    return (
        "[当前 netx UME告警锚点]\n"
        f"- 错误: {err}\n"
        f"- 详情: {detail}\n"
        "- 处理: 检查 NETX_API_URL（或 OCLAW_NETX_BASE_URL）与 netx 服务是否可达；"
        "确认 Admin 已安装并绑定 MCP server_id=netx。"
    )


def ops_netx_system_context_extension(*, lang: str = "zh") -> str:
    """Append to ops specialist system prompt: UME sync anchor (direct_loop injection).

    Cached briefly to reduce duplicate HTTP calls across tool rounds.
    """
    if str(os.getenv("OCLAW_OPS_NETX_CONTEXT_INJECT") or "1").strip().lower() in {"0", "false", "no", "off"}:
        return ""
    lang_en = str(lang or "").strip().lower().startswith("en")
    lk = "en" if lang_en else "zh"
    now = time.monotonic()
    with _OPS_NETX_SYS_CTX_LOCK:
        hit = _OPS_NETX_SYS_CTX_CACHE.get(lk)
        if hit and (now - hit[0]) < _OPS_NETX_SYS_CTX_TTL_SEC:
            return hit[1]
    r = _resolve_ume_anchor()
    text = _format_ops_netx_system_extension(r, lang_en=lang_en)
    store_ts = time.monotonic()
    with _OPS_NETX_SYS_CTX_LOCK:
        _OPS_NETX_SYS_CTX_CACHE[lk] = (store_ts, text)
    return text
