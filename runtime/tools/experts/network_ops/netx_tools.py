"""Internal read-only tools: query netx REST API (PostgreSQL backend on netx side).

Configure via environment:
- ``OCLAW_NETX_BASE_URL`` (default ``http://127.0.0.1:8890``)
- ``OCLAW_NETX_API_TOKEN`` (optional) → sent as ``Authorization: Bearer …`` if set.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

import httpx

from oclaw.runtime.tools.base import ToolSpec


def _netx_base_url() -> str:
    return (os.getenv("OCLAW_NETX_BASE_URL") or "http://127.0.0.1:8890").strip().rstrip("/")


def _netx_headers() -> dict[str, str]:
    h = {"accept": "application/json"}
    tok = (os.getenv("OCLAW_NETX_API_TOKEN") or "").strip()
    if tok:
        h["authorization"] = f"Bearer {tok}"
    return h


def _http_json(method: str, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
    base = _netx_base_url()
    url = f"{base}{path}"
    try:
        with httpx.Client(timeout=45.0) as client:
            resp = client.request(method, url, params=params or None, headers=_netx_headers())
            text = resp.text
            if not resp.is_success:
                return {"ok": False, "error": f"netx_http_{resp.status_code}", "detail": text[:800]}
            data = resp.json() if text else {}
            return {"ok": True, "data": data if isinstance(data, dict) else {"raw": data}}
    except Exception as exc:
        return {"ok": False, "error": "netx_request_failed", "detail": str(exc)[:800]}


def _resolve_latest_import_batch_id() -> dict[str, Any]:
    """``GET /v1/batches`` 按 created_at 降序；取第一条为当前最新导入批次。"""
    r = _http_json("GET", "/v1/batches", params={"limit": 1})
    if not r.get("ok"):
        return {"ok": False, "error": "netx_list_batches_failed", "detail": r.get("detail"), "upstream": r}
    data = r.get("data") or {}
    items = data.get("items")
    if not isinstance(items, list) or not items:
        return {"ok": False, "error": "no_import_batches", "detail": "netx 中尚无导入批次，请先导入或显式提供 batch_id"}
    first = items[0]
    if not isinstance(first, dict):
        return {"ok": False, "error": "no_import_batches", "detail": "batch 列表格式异常"}
    bid = str(first.get("batch_id") or "").strip()
    if not bid:
        return {"ok": False, "error": "no_import_batches", "detail": "batch 列表中无 batch_id"}
    return {"ok": True, "batch_id": bid, "batch_row": first}


_OPS_NETX_SYS_CTX_LOCK = threading.Lock()
# Lang code -> (monotonic_ts, formatted extension text); short TTL to avoid hammering netx each tool round.
_OPS_NETX_SYS_CTX_CACHE: dict[str, tuple[float, str]] = {}
_OPS_NETX_SYS_CTX_TTL_SEC = 5.0


def _format_ops_netx_system_extension(r: dict[str, Any], *, lang_en: bool) -> str:
    if r.get("ok"):
        bid = str(r.get("batch_id") or "")
        row = r.get("batch_row") if isinstance(r.get("batch_row"), dict) else {}
        created = str(row.get("created_at") or "")
        src = str(row.get("source_file") or "")
        status = str(row.get("status") or "")
        total = row.get("total_rows")
        lines_en = [
            "[Netx alarm import anchor]",
            f"- batch_id: {bid}",
            f"- source_file: {src}",
            f"- created_at: {created}",
        ]
        lines_zh = [
            "[当前 netx 告警导入锚点]",
            f"- batch_id: {bid}",
            f"- 源文件: {src}",
            f"- 导入时间: {created}",
        ]
        if status:
            (lines_en if lang_en else lines_zh).append(f"- status: {status}" if lang_en else f"- 状态: {status}")
        if total is not None:
            (lines_en if lang_en else lines_zh).append(f"- rows: {total}" if lang_en else f"- 行数: {total}")
        tail_en = (
            "- tools: netx_query_alarms, netx_aggregate_alarms, netx_run_diagnostics (pass batch_id above)\n"
            "- note: numbers below are not alarm facts—call tools for evidence."
        )
        tail_zh = (
            "- 工具: netx_query_alarms、netx_aggregate_alarms、netx_run_diagnostics（使用上述 batch_id）\n"
            "- 说明: 此处仅为批次锚点；具体告警必须以工具返回为准，勿臆测。"
        )
        return "\n".join(lines_en + [tail_en]) if lang_en else "\n".join(lines_zh + [tail_zh])
    err = str(r.get("error") or "")
    detail = str(r.get("detail") or "")[:240]
    if err == "no_import_batches":
        if lang_en:
            return (
                "[Netx alarm import anchor]\n"
                "- batch_id: (none)\n"
                "- note: no import batches in netx yet—import alarms or pass batch_id in chat."
            )
        return (
            "[当前 netx 告警导入锚点]\n"
            "- batch_id: （暂无）\n"
            "- 说明: netx 中尚无导入批次；请先导入告警或在对话中提供 batch_id。"
        )
    if lang_en:
        return (
            "[Netx alarm import anchor]\n"
            f"- error: {err}\n"
            f"- detail: {detail}\n"
            "- fix: check OCLAW_NETX_BASE_URL and that netx API is reachable."
        )
    return (
        "[当前 netx 告警导入锚点]\n"
        f"- 错误: {err}\n"
        f"- 详情: {detail}\n"
        "- 处理: 检查 OCLAW_NETX_BASE_URL 与 netx 服务是否可达。"
    )


def ops_netx_system_context_extension(*, lang: str = "zh") -> str:
    """Append to ops specialist system prompt: latest batch_id anchor (direct_loop injection).

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
    r = _resolve_latest_import_batch_id()
    text = _format_ops_netx_system_extension(r, lang_en=lang_en)
    store_ts = time.monotonic()
    with _OPS_NETX_SYS_CTX_LOCK:
        _OPS_NETX_SYS_CTX_CACHE[lk] = (store_ts, text)
    return text


def netx_query_alarms_tool() -> ToolSpec:
    """Paginated alarm rows from netx (same filters as netx UI REST)."""

    def handler(args: dict[str, Any]) -> dict[str, Any]:
        explicit = str(args.get("batch_id") or "").strip()
        resolution = "explicit"
        batch_id = explicit
        if not batch_id:
            res = _resolve_latest_import_batch_id()
            if not res.get("ok"):
                return res
            batch_id = str(res.get("batch_id") or "")
            resolution = "latest_import"
        page = max(1, int(args.get("page") or 1))
        page_size = min(200, max(1, int(args.get("page_size") or 50)))
        params: dict[str, Any] = {
            "batch_id": batch_id,
            "page": page,
            "page_size": page_size,
        }
        if str(args.get("alarm_code") or "").strip():
            params["alarm_code"] = str(args.get("alarm_code")).strip()
        if str(args.get("ne_name") or "").strip():
            params["ne_name"] = str(args.get("ne_name")).strip()
        if str(args.get("severity") or "").strip():
            params["severity"] = str(args.get("severity")).strip()
        out = _http_json("GET", "/v1/alarms", params=params)
        if out.get("ok") and resolution == "latest_import":
            out = {**out, "batch_id_used": batch_id, "batch_resolution": resolution}
        return out

    return ToolSpec(
        name="netx_query_alarms",
        description=(
            "从独立运维工具 netx 读取告警明细（PostgreSQL 侧由 netx 托管）。"
            "batch_id 可选：不传表示使用 netx 当前「最新」导入批次（/v1/batches 第一条）。"
            "可选 alarm_code / ne_name / severity（与 netx 告警列表过滤语义一致）；支持分页。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "batch_id": {"type": "string", "description": "导入批次 ID；省略则用最新导入批次"},
                "alarm_code": {"type": "string", "description": "告警码包含匹配（可选）"},
                "ne_name": {"type": "string", "description": "网元名包含匹配（可选）"},
                "severity": {"type": "string", "description": "规范化级别 critical/major/minor/warning/..."},
                "page": {"type": "integer", "minimum": 1, "default": 1},
                "page_size": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
            },
            "required": [],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"netx", "ops", "alarms", "read_only"}),
        risk_level="low",
        read_only=True,
    )


def netx_aggregate_alarms_tool() -> ToolSpec:
    """Aggregate buckets from netx."""

    def handler(args: dict[str, Any]) -> dict[str, Any]:
        explicit = str(args.get("batch_id") or "").strip()
        resolution = "explicit"
        batch_id = explicit
        if not batch_id:
            res = _resolve_latest_import_batch_id()
            if not res.get("ok"):
                return res
            batch_id = str(res.get("batch_id") or "")
            resolution = "latest_import"
        group_by = str(args.get("group_by") or "severity_norm").strip()
        if group_by not in {"severity_norm", "alarm_code", "ne_name"}:
            return {"ok": False, "error": "invalid_group_by"}
        params: dict[str, Any] = {"group_by": group_by, "batch_id": batch_id}
        out = _http_json("GET", "/v1/alarms/aggregate", params=params)
        if out.get("ok") and resolution == "latest_import":
            out = {**out, "batch_id_used": batch_id, "batch_resolution": resolution}
        return out

    return ToolSpec(
        name="netx_aggregate_alarms",
        description=(
            "按 severity_norm / alarm_code / ne_name 对 netx 告警做聚合统计（读 netx API，不落直连 PG）。"
            "batch_id 可选：不传则限定为 netx 当前最新导入批次（与告警查询默认语义一致）。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "batch_id": {"type": "string"},
                "group_by": {
                    "type": "string",
                    "enum": ["severity_norm", "alarm_code", "ne_name"],
                    "default": "severity_norm",
                },
            },
            "required": [],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"netx", "ops", "alarms", "aggregate", "read_only"}),
        risk_level="low",
        read_only=True,
    )


def netx_run_diagnostics_tool() -> ToolSpec:
    """Diagnostics summary (same stats netx uses for dashboard slices)."""

    def handler(args: dict[str, Any]) -> dict[str, Any]:
        explicit = str(args.get("batch_id") or "").strip()
        resolution = "explicit"
        batch_id = explicit
        if not batch_id:
            res = _resolve_latest_import_batch_id()
            if not res.get("ok"):
                return res
            batch_id = str(res.get("batch_id") or "")
            resolution = "latest_import"
        out = _http_json("GET", "/v1/diagnostics", params={"batch_id": batch_id})
        if out.get("ok") and resolution == "latest_import":
            out = {**out, "batch_id_used": batch_id, "batch_resolution": resolution}
        return out

    return ToolSpec(
        name="netx_run_diagnostics",
        description=(
            "读取 netx /v1/diagnostics 统计摘要（批次维度：级别分布、Top 告警码/网元、协议归类等）。"
            "batch_id 可选：不传则使用 netx 当前最新导入批次。"
        ),
        parameters={
            "type": "object",
            "properties": {"batch_id": {"type": "string", "description": "批次 ID；省略则用最新导入批次"}},
            "required": [],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"netx", "ops", "diagnostics", "read_only"}),
        risk_level="low",
        read_only=True,
    )


def netx_list_import_batches_tool() -> ToolSpec:
    """List recent import batches (newest first)."""

    def handler(args: dict[str, Any]) -> dict[str, Any]:
        limit = max(1, min(100, int(args.get("limit") or 20)))
        return _http_json("GET", "/v1/batches", params={"limit": limit})

    return ToolSpec(
        name="netx_list_import_batches",
        description="列出 netx 最近导入批次（与 UI 一致，按创建时间降序）。用于核对 batch_id 或确认「最新」批次。",
        parameters={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
            },
            "required": [],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"netx", "ops", "batches", "read_only"}),
        risk_level="low",
        read_only=True,
    )


def netx_list_alarm_fields_tool() -> ToolSpec:
    """List alarms_norm columns from netx."""

    def handler(args: dict[str, Any]) -> dict[str, Any]:
        _ = args
        return _http_json("GET", "/v1/alarms/fields", params=None)

    return ToolSpec(
        name="netx_list_alarm_fields",
        description="列出 netx alarms_norm 表所有字段名（供自由查询时选择字段/确认可用字段）。",
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"netx", "ops", "alarms", "schema", "read_only"}),
        risk_level="low",
        read_only=True,
    )


def netx_query_alarms_raw_tool() -> ToolSpec:
    """Power query alarms_norm with all fields."""

    def handler(args: dict[str, Any]) -> dict[str, Any]:
        explicit = str(args.get("batch_id") or "").strip()
        batch_id = explicit
        if not batch_id:
            res = _resolve_latest_import_batch_id()
            if not res.get("ok"):
                return res
            batch_id = str(res.get("batch_id") or "")
        page = max(1, int(args.get("page") or 1))
        page_size = min(200, max(1, int(args.get("page_size") or 50)))
        params: dict[str, Any] = {
            "batch_id": batch_id,
            "page": page,
            "page_size": page_size,
        }
        if str(args.get("alarm_code") or "").strip():
            params["alarm_code"] = str(args.get("alarm_code")).strip()
        if str(args.get("ne_name") or "").strip():
            params["ne_name"] = str(args.get("ne_name")).strip()
        if str(args.get("severity") or "").strip():
            params["severity"] = str(args.get("severity")).strip()
        if str(args.get("q") or "").strip():
            params["q"] = str(args.get("q")).strip()
        if str(args.get("order_by") or "").strip():
            params["order_by"] = str(args.get("order_by")).strip()
        if str(args.get("order") or "").strip():
            params["order"] = str(args.get("order")).strip()
        return _http_json("GET", "/v1/alarms/raw", params=params)

    return ToolSpec(
        name="netx_query_alarms_raw",
        description=(
            "自由查询 netx alarms_norm：返回所有字段。"
            "batch_id 可选（省略则使用最新导入批次）；支持 severity/alarm_code/ne_name/q 过滤与分页；"
            "order_by 仅允许 id/alarm_time/severity_norm/ne_name/alarm_code。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "batch_id": {"type": "string", "description": "批次 ID；省略则用最新导入批次"},
                "severity": {"type": "string"},
                "alarm_code": {"type": "string"},
                "ne_name": {"type": "string"},
                "q": {"type": "string", "description": "自由文本 contains（alarm_code/ne_name/description/service）"},
                "order_by": {"type": "string", "enum": ["id", "alarm_time", "severity_norm", "ne_name", "alarm_code"]},
                "order": {"type": "string", "enum": ["asc", "desc"]},
                "page": {"type": "integer", "minimum": 1, "default": 1},
                "page_size": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
            },
            "required": [],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"netx", "ops", "alarms", "power_query", "read_only"}),
        risk_level="low",
        read_only=True,
    )


def netx_sql_query_tool() -> ToolSpec:
    """Execute read-only SQL on netx (server enforced SELECT-only)."""

    def handler(args: dict[str, Any]) -> dict[str, Any]:
        batch_id = str(args.get("batch_id") or "").strip()
        if not batch_id:
            res = _resolve_latest_import_batch_id()
            if not res.get("ok"):
                return res
            batch_id = str(res.get("batch_id") or "")
        sql = str(args.get("sql") or "").strip()
        limit = max(1, min(2000, int(args.get("limit") or 200)))
        if not sql:
            return {"ok": False, "error": "sql_required"}
        base = _netx_base_url()
        url = f"{base}/v1/sql/query"
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(url, json={"sql": sql, "batch_id": batch_id, "limit": limit}, headers=_netx_headers())
                text = resp.text
                if not resp.is_success:
                    return {"ok": False, "error": f"netx_http_{resp.status_code}", "detail": text[:800]}
                data = resp.json() if text else {}
                return {"ok": True, "data": data if isinstance(data, dict) else {"raw": data}}
        except Exception as exc:
            return {"ok": False, "error": "netx_request_failed", "detail": str(exc)[:800]}

    return ToolSpec(
        name="netx_sql_query",
        description=(
            "在 netx 上执行只读 SQL（服务端强制 SELECT-only、单语句、必须包含 :batch_id 参数，并强制 limit）。"
            "用于自由组合查询；建议先用 netx_list_alarm_fields 确认可用字段。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "batch_id": {"type": "string", "description": "批次 ID；省略则用最新导入批次"},
                "sql": {"type": "string", "description": "必须是 SELECT，且包含 :batch_id 占位符"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 2000, "default": 200},
            },
            "required": ["sql"],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"netx", "ops", "sql", "power_query", "read_only"}),
        risk_level="low",
        read_only=True,
    )


__all__ = [
    "netx_query_alarms_tool",
    "netx_aggregate_alarms_tool",
    "netx_run_diagnostics_tool",
    "netx_list_import_batches_tool",
    "netx_list_alarm_fields_tool",
    "netx_query_alarms_raw_tool",
    "netx_sql_query_tool",
]
