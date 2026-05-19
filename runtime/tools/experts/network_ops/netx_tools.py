"""Internal read-only tools: query netx REST API (PostgreSQL backend on netx side).

Configure via environment:
- ``OCLAW_NETX_BASE_URL`` (default ``http://127.0.0.1:8890``)
- ``OCLAW_NETX_API_TOKEN`` (optional) → sent as ``Authorization: Bearer …`` if set.
"""

from __future__ import annotations

import contextvars
import os
import threading
import time
from typing import Any

import httpx

from runtime.tools.base import ToolSpec

# Set by ToolExecutor for netx_* tools so responses match session language.
NETX_TOOL_LANG: contextvars.ContextVar[str] = contextvars.ContextVar("netx_tool_lang", default="zh")

_PROTOCOL_KEY_ZH_TO_EN: dict[str, str] = {
    "其他": "Other",
    "时钟": "Clock",
    "OTN/光": "OTN/Optical",
    "电源": "Power",
}

_UME_RAW_GROUP_FIELDS = [
    "alarm_alarm_key",
    "alarm_host_name",
    "alarm_ne_id",
    "alarm_object_name",
    "alarm_event_type",
    "alarm_native_probable_cause",
    "alarm_perceived_severity",
    "alarm_is_cleared",
    "alarm_time_created",
    "alarm_root_cause_alarm_indication",
    "ne_ne_id",
    "ne_ne_name",
    "ne_user_label",
    "ne_ip_address",
    "ne_ipv6_address",
    "ne_ne_type",
    "ne_device_level",
    "ne_host_name",
    "ne_location",
    "ne_hardware_version",
    "ne_loopback",
    "ne_consistent_state",
    "ne_interface_version",
    "ne_mac",
    "ne_admin_status",
    "ne_address_type",
    "ne_connection_status",
    "ne_maintain_status",
    "ne_net_mask",
    "ne_create_time",
    "ne_creator",
    "ne_vendor",
    "ne_source_type",
    "ne_exists",
]


def _netx_base_url() -> str:
    return (os.getenv("OCLAW_NETX_BASE_URL") or "http://127.0.0.1:8890").strip().rstrip("/")


def _netx_headers() -> dict[str, str]:
    h = {"accept": "application/json"}
    tok = (os.getenv("OCLAW_NETX_API_TOKEN") or "").strip()
    if tok:
        h["authorization"] = f"Bearer {tok}"
    return h


def _netx_lang_query_params() -> dict[str, str]:
    lang = str(NETX_TOOL_LANG.get() or "zh").strip().lower()
    if lang.startswith("en"):
        return {"lang": "en"}
    return {}


def _localize_netx_payload(data: dict[str, Any], *, lang: str) -> dict[str, Any]:
    """Map legacy Chinese protocol bucket labels to English for en sessions."""
    if not str(lang or "").strip().lower().startswith("en"):
        return data
    proto = data.get("protocol_summary")
    if isinstance(proto, list):
        for row in proto:
            if isinstance(row, dict):
                k = str(row.get("key") or "")
                if k in _PROTOCOL_KEY_ZH_TO_EN:
                    row["key"] = _PROTOCOL_KEY_ZH_TO_EN[k]
    return data


def _http_json(method: str, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
    base = _netx_base_url()
    url = f"{base}{path}"
    merged: dict[str, Any] = dict(_netx_lang_query_params())
    if params:
        merged.update(params)
    try:
        # Do not inherit system proxy settings for local netx calls.
        with httpx.Client(timeout=45.0, trust_env=False) as client:
            resp = client.request(method, url, params=merged or None, headers=_netx_headers())
            text = resp.text
            if not resp.is_success:
                return {"ok": False, "error": f"netx_http_{resp.status_code}", "detail": text[:800]}
            data = resp.json() if text else {}
            if isinstance(data, dict):
                data = _localize_netx_payload(data, lang=str(NETX_TOOL_LANG.get() or "zh"))
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
            "- tools: netx_query_ume_alarms, netx_aggregate_ume_alarms, netx_run_ume_diagnostics, "
            "netx_query_ume_ne_inventory, netx_get_ume_ne\n"
            "- note: this is only runtime anchor; use tools for alarm/ne evidence.\n"
            "- English session: user-visible reply must contain NO Chinese/CJK; translate alarm text fields."
        )
        tail_zh = (
            "- 工具: netx_query_ume_alarms、netx_aggregate_ume_alarms、netx_run_ume_diagnostics、"
            "netx_query_ume_ne_inventory、netx_get_ume_ne\n"
            "- 说明: 此处仅为运行锚点；具体告警/网元信息必须以工具返回为准，勿臆测。"
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
            "[Netx UME current-alarms anchor]\n"
            f"- error: {err}\n"
            f"- detail: {detail}\n"
            "- fix: check OCLAW_NETX_BASE_URL and that netx API is reachable."
        )
    return (
        "[当前 netx UME告警锚点]\n"
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
    r = _resolve_ume_anchor()
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
            # Do not inherit system proxy settings for local netx calls.
            with httpx.Client(timeout=60.0, trust_env=False) as client:
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


def netx_query_ume_alarms_tool() -> ToolSpec:
    """Paginated UME current alarms from netx."""

    def handler(args: dict[str, Any]) -> dict[str, Any]:
        # Guardrail: avoid accidental full scans by endless paging.
        page = max(1, int(args.get("page") or 1))
        if page > 2:
            page = 2
        page_size = min(500, max(1, int(args.get("page_size") or 50)))
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if str(args.get("severity") or "").strip():
            params["severity"] = str(args.get("severity")).strip()
        ne_name = str(args.get("ne_name") or "").strip()
        keyword = str(args.get("keyword") or "").strip()
        if keyword:
            params["keyword"] = keyword
        elif ne_name:
            params["keyword"] = ne_name
        if str(args.get("ne_id") or "").strip():
            params["ne_id"] = str(args.get("ne_id")).strip()
        return _http_json("GET", "/v1/ume/alarms", params=params)

    return ToolSpec(
        name="netx_query_ume_alarms",
        description=(
            "读取 netx UME 当前告警明细（实时表）；每条含 host_name（网元主展示键，同步时已写入告警表）。"
            "支持 severity/ne_id/keyword 与分页。"
            "当需要字段级控制或复杂分析时，优先 netx_list_ume_alarm_fields + netx_query_ume_alarms_raw/netx_sql_query_ume。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "severity": {"type": "string"},
                "ne_id": {"type": "string"},
                "ne_name": {"type": "string", "description": "兼容参数，会映射到 keyword"},
                "keyword": {"type": "string", "description": "按网元名/标签/IP/对象名等关键字检索"},
                "page": {"type": "integer", "minimum": 1, "default": 1},
                "page_size": {"type": "integer", "minimum": 1, "maximum": 500, "default": 50},
            },
            "required": [],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"netx", "ops", "ume", "alarms", "read_only"}),
        risk_level="low",
        read_only=True,
    )


def netx_aggregate_ume_alarms_tool() -> ToolSpec:
    """Aggregate UME current alarms from netx."""

    def handler(args: dict[str, Any]) -> dict[str, Any]:
        _ = args
        return _http_json("GET", "/v1/ume/alarms/aggregate", params=None)

    return ToolSpec(
        name="netx_aggregate_ume_alarms",
        description="读取 netx UME 当前告警聚合（by_severity/by_ne）。",
        parameters={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        handler=handler,
        tags=frozenset({"netx", "ops", "ume", "alarms", "aggregate", "read_only"}),
        risk_level="low",
        read_only=True,
    )


def netx_run_ume_diagnostics_tool() -> ToolSpec:
    """Diagnostics summary for UME current alarms."""

    def handler(args: dict[str, Any]) -> dict[str, Any]:
        _ = args
        return _http_json("GET", "/v1/ume/diagnostics", params=None)

    return ToolSpec(
        name="netx_run_ume_diagnostics",
        description="读取 netx UME 告警诊断摘要（级别分布、Top 告警码、Top 网元、协议归类）。",
        parameters={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        handler=handler,
        tags=frozenset({"netx", "ops", "ume", "diagnostics", "read_only"}),
        risk_level="low",
        read_only=True,
    )


def netx_query_ume_ne_inventory_tool() -> ToolSpec:
    """Paged UME NE inventory synced in netx (PostgreSQL-backed)."""

    def handler(args: dict[str, Any]) -> dict[str, Any]:
        page = max(1, int(args.get("page") or 1))
        page_size = min(500, max(1, int(args.get("page_size") or 50)))
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if str(args.get("keyword") or "").strip():
            params["keyword"] = str(args.get("keyword")).strip()
        return _http_json("GET", "/v1/ume/inventory/ne", params=params)

    return ToolSpec(
        name="netx_query_ume_ne_inventory",
        description=(
            "查询 netx 已同步的 UME 网元清单（读 /v1/ume/inventory/ne，与 netx Web「网元清单」同源）。"
            "keyword 可选：匹配 ne_id / ne_name / user_label / ip_address / host_name（主机名）包含。"
            "返回 total、page、page_size、items（含 host_name、在线状态、地址、类型等）。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "关键字过滤（可选）"},
                "page": {"type": "integer", "minimum": 1, "default": 1},
                "page_size": {"type": "integer", "minimum": 1, "maximum": 500, "default": 50},
            },
            "required": [],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"netx", "ops", "ume", "inventory", "ne", "read_only"}),
        risk_level="low",
        read_only=True,
    )


def netx_get_ume_ne_tool() -> ToolSpec:
    """Single UME NE detail by ne_id from netx."""

    def handler(args: dict[str, Any]) -> dict[str, Any]:
        from urllib.parse import quote

        ne_id = str(args.get("ne_id") or "").strip()
        if not ne_id:
            return {"ok": False, "error": "ne_id_required", "error_code": "ne_id_required"}
        safe = quote(ne_id, safe="")
        return _http_json("GET", f"/v1/ume/inventory/ne/{safe}", params=None)

    return ToolSpec(
        name="netx_get_ume_ne",
        description=(
            "按网元 UUID（ne_id）读取 netx 中单条 UME 网元详情（GET /v1/ume/inventory/ne/{ne_id}）。"
            "含 vendor、source_type、raw_json 等；404 时上游返回 ume_ne_not_found。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "ne_id": {"type": "string", "description": "网元 UUID（与清单中 ne_id 一致）"},
            },
            "required": ["ne_id"],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"netx", "ops", "ume", "inventory", "ne", "read_only"}),
        risk_level="low",
        read_only=True,
    )


def netx_query_ume_alarms_raw_tool() -> ToolSpec:
    """Power query UME current alarms with full alarm+NE fields."""

    presets: dict[str, list[str]] = {
        "brief": [
            "alarm_alarm_key",
            "alarm_host_name",
            "alarm_perceived_severity",
            "alarm_event_type",
            "alarm_last_seen_at",
            "ne_host_name",
            "ne_user_label",
            "ne_ne_name",
            "ne_ip_address",
            "ne_exists",
        ],
        "evidence": [
            "alarm_alarm_key",
            "alarm_host_name",
            "alarm_object_name",
            "alarm_event_type",
            "alarm_native_probable_cause",
            "alarm_perceived_severity",
            "alarm_is_cleared",
            "alarm_time_created",
            "alarm_last_seen_at",
            "ne_host_name",
            "ne_user_label",
            "ne_ne_name",
            "ne_ip_address",
            "ne_connection_status",
            "ne_exists",
        ],
        "ne_debug": [
            "alarm_alarm_key",
            "alarm_ne_id",
            "alarm_perceived_severity",
            "alarm_last_seen_at",
            "ne_user_label",
            "ne_ne_name",
            "ne_ip_address",
            "ne_ipv6_address",
            "ne_device_level",
            "ne_host_name",
            "ne_connection_status",
            "ne_admin_status",
            "ne_address_type",
            "ne_maintain_status",
            "ne_exists",
        ],
    }

    def handler(args: dict[str, Any]) -> dict[str, Any]:
        page = max(1, int(args.get("page") or 1))
        page_size = min(500, max(1, int(args.get("page_size") or 50)))
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        for k in ("severity", "is_cleared", "ne_id", "event_type", "keyword", "time_from", "time_to", "order_by", "order"):
            v = str(args.get(k) or "").strip()
            if v:
                params[k] = v
        sf = args.get("select_fields")
        fields: list[str] = []
        if isinstance(sf, list):
            fields = [str(x).strip() for x in sf if str(x).strip()]
        if not fields:
            preset = str(args.get("field_preset") or "").strip().lower()
            fields = list(presets.get(preset) or [])
        if fields:
            params["select_fields"] = ",".join(fields)
        return _http_json("GET", "/v1/ume/alarms/raw", params=params)

    return ToolSpec(
        name="netx_query_ume_alarms_raw",
        description=(
            "自由查询 netx UME 当前告警原始视图，返回 alarm_* + ne_* 全字段。"
            "可按 severity/is_cleared/ne_id/event_type/keyword/time_from/time_to 过滤，支持排序分页。"
            "select_fields 可按需指定返回字段，降低输出体积。"
            "field_preset 可快速选用默认字段集（brief/evidence/ne_debug）。"
            "建议先调用 netx_list_ume_alarm_fields 查看可用字段。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "severity": {"type": "string"},
                "is_cleared": {"type": "string"},
                "ne_id": {"type": "string"},
                "event_type": {"type": "string"},
                "keyword": {"type": "string"},
                "time_from": {"type": "string", "description": "ISO8601 时间下界（按 last_seen_at）"},
                "time_to": {"type": "string", "description": "ISO8601 时间上界（按 last_seen_at）"},
                "order_by": {"type": "string", "enum": ["last_seen_at", "time_created", "perceived_severity", "event_type", "ne_id"]},
                "order": {"type": "string", "enum": ["asc", "desc"]},
                "select_fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "可选返回字段，如 alarm_alarm_key/ne_user_label/ne_exists",
                },
                "field_preset": {
                    "type": "string",
                    "enum": ["brief", "evidence", "ne_debug"],
                    "description": "字段集预设；当未传 select_fields 时生效",
                },
                "page": {"type": "integer", "minimum": 1, "default": 1},
                "page_size": {"type": "integer", "minimum": 1, "maximum": 500, "default": 50},
            },
            "required": [],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"netx", "ops", "ume", "alarms", "power_query", "read_only"}),
        risk_level="low",
        read_only=True,
    )


def netx_list_ume_alarm_fields_tool() -> ToolSpec:
    """List field names for UME raw alarm query."""

    def handler(args: dict[str, Any]) -> dict[str, Any]:
        _ = args
        return _http_json("GET", "/v1/ume/alarms/fields", params=None)

    return ToolSpec(
        name="netx_list_ume_alarm_fields",
        description="列出 UME 当前告警 raw 查询可用字段（alarm_fields/ne_fields/order_by_allowed）。",
        parameters={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        handler=handler,
        tags=frozenset({"netx", "ops", "ume", "alarms", "schema", "read_only"}),
        risk_level="low",
        read_only=True,
    )


def netx_sql_query_ume_tool() -> ToolSpec:
    """Execute read-only SQL on UME tables in netx."""

    def handler(args: dict[str, Any]) -> dict[str, Any]:
        sql = str(args.get("sql") or "").strip()
        limit = max(1, min(2000, int(args.get("limit") or 200)))
        statement_timeout_ms = max(0, min(30000, int(args.get("statement_timeout_ms") or 0)))
        if not sql:
            return {"ok": False, "error": "sql_required"}
        base = _netx_base_url()
        url = f"{base}/v1/sql/ume_query"
        try:
            # Do not inherit system proxy settings for local netx calls.
            with httpx.Client(timeout=60.0, trust_env=False) as client:
                resp = client.post(
                    url,
                    json={"sql": sql, "limit": limit, "statement_timeout_ms": statement_timeout_ms},
                    headers=_netx_headers(),
                )
                text = resp.text
                if not resp.is_success:
                    return {"ok": False, "error": f"netx_http_{resp.status_code}", "detail": text[:800]}
                data = resp.json() if text else {}
                return {"ok": True, "data": data if isinstance(data, dict) else {"raw": data}}
        except Exception as exc:
            return {"ok": False, "error": "netx_request_failed", "detail": str(exc)[:800]}

    return ToolSpec(
        name="netx_sql_query_ume",
        description=(
            "在 netx 上执行 UME 只读 SQL（服务端强制 SELECT-only、单语句、限制表为 "
            "ume_alarms_current/ume_inventory_ne，并强制 limit）。"
            "推荐默认模板：设置 statement_timeout_ms=8000，且 SQL 带时间窗过滤（last_seen_at >= now() - interval '30 minutes'）。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "只读 SELECT SQL；仅允许 UME 当前告警与网元表"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 2000, "default": 200},
                "statement_timeout_ms": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 30000,
                    "default": 0,
                    "description": "可选查询超时(ms)，0表示使用数据库默认超时",
                },
            },
            "required": ["sql"],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"netx", "ops", "ume", "sql", "power_query", "read_only"}),
        risk_level="low",
        read_only=True,
    )


def netx_aggregate_ume_alarms_raw_tool() -> ToolSpec:
    """Dynamic aggregation on UME raw fields."""

    def handler(args: dict[str, Any]) -> dict[str, Any]:
        params: dict[str, Any] = {}
        for k in (
            "group_by",
            "group_by2",
            "severity",
            "is_cleared",
            "ne_id",
            "event_type",
            "keyword",
            "time_from",
            "time_to",
            "limit",
        ):
            v = args.get(k)
            if v is None:
                continue
            sv = str(v).strip()
            if sv:
                params[k] = sv
        return _http_json("GET", "/v1/ume/alarms/aggregate/raw", params=params)

    return ToolSpec(
        name="netx_aggregate_ume_alarms_raw",
        description=(
            "按 UME raw 字段做动态聚合（group_by/group_by2），支持与 raw 同口径过滤条件。"
            "group_by 需使用 alarm_*/ne_* 字段，建议先 netx_list_ume_alarm_fields。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "group_by": {
                    "type": "string",
                    "enum": _UME_RAW_GROUP_FIELDS,
                    "description": "主分组字段（网元主键优先 alarm_host_name 或 ne_host_name；勿用 alarm_ne_id/ne_ne_id）",
                },
                "group_by2": {"type": "string", "enum": _UME_RAW_GROUP_FIELDS, "description": "可选第二分组字段"},
                "severity": {"type": "string"},
                "is_cleared": {"type": "string"},
                "ne_id": {"type": "string"},
                "event_type": {"type": "string"},
                "keyword": {"type": "string"},
                "time_from": {"type": "string"},
                "time_to": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 2000, "default": 200},
            },
            "required": ["group_by"],
            "additionalProperties": False,
        },
        handler=handler,
        tags=frozenset({"netx", "ops", "ume", "alarms", "aggregate", "power_query", "read_only"}),
        risk_level="low",
        read_only=True,
    )


__all__ = [
    # "netx_query_alarms_tool",
    # "netx_aggregate_alarms_tool",
    # "netx_run_diagnostics_tool",
    # "netx_list_import_batches_tool",
    # "netx_list_alarm_fields_tool",
    # "netx_query_alarms_raw_tool",
    # "netx_sql_query_tool",
    "netx_query_ume_alarms_tool",
    "netx_aggregate_ume_alarms_tool",
    "netx_run_ume_diagnostics_tool",
    "netx_query_ume_ne_inventory_tool",
    "netx_get_ume_ne_tool",
    "netx_query_ume_alarms_raw_tool",
    "netx_aggregate_ume_alarms_raw_tool",
    "netx_list_ume_alarm_fields_tool",
    "netx_sql_query_ume_tool",
]
