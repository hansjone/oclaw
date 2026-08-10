"""Shared netx REST client for oclaw (context inject + ume_alarm_xlsx_report).

Aligns base URL with netx-mcp: ``NETX_API_URL`` then ``OCLAW_NETX_BASE_URL``.
"""

from __future__ import annotations

import contextvars
import os
from typing import Any

import httpx

# Set by ToolExecutor so responses match session language.
NETX_TOOL_LANG: contextvars.ContextVar[str] = contextvars.ContextVar("netx_tool_lang", default="zh")

_PROTOCOL_KEY_ZH_TO_EN: dict[str, str] = {
    "其他": "Other",
    "时钟": "Clock",
    "OTN/光": "OTN/Optical",
    "电源": "Power",
}


def _netx_base_url() -> str:
    return (
        os.getenv("NETX_API_URL") or os.getenv("OCLAW_NETX_BASE_URL") or "http://127.0.0.1:8890"
    ).strip().rstrip("/")


def _netx_headers() -> dict[str, str]:
    h = {"accept": "application/json"}
    tok = (os.getenv("OCLAW_NETX_API_TOKEN") or os.getenv("NETX_API_TOKEN") or "").strip()
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


def _http_post_json(path: str, body: dict[str, Any], *, timeout: float = 180.0) -> dict[str, Any]:
    base = _netx_base_url()
    url = f"{base}{path}"
    try:
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            resp = client.post(url, json=body, headers=_netx_headers())
            text = resp.text
            if not resp.is_success:
                return {"ok": False, "error": f"netx_http_{resp.status_code}", "detail": text[:800]}
            data = resp.json() if text else {}
            if isinstance(data, dict):
                data = _localize_netx_payload(data, lang=str(NETX_TOOL_LANG.get() or "zh"))
            return {"ok": True, "data": data if isinstance(data, dict) else {"raw": data}}
    except Exception as exc:
        return {"ok": False, "error": "netx_request_failed", "detail": str(exc)[:800]}


def _http_json(method: str, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
    base = _netx_base_url()
    url = f"{base}{path}"
    merged: dict[str, Any] = dict(_netx_lang_query_params())
    if params:
        merged.update(params)
    try:
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


__all__ = [
    "NETX_TOOL_LANG",
    "_http_json",
    "_http_post_json",
    "_localize_netx_payload",
    "_netx_base_url",
    "_netx_headers",
]
