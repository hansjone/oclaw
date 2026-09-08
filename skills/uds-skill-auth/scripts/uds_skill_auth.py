# -*- coding: utf-8 -*-
"""
uds-skill-auth — Python helpers for UDS-backed skills.

Resolve SSO credentials via loopback Host APIs, or call intranet APIs through
the outbound proxy.

Environment:
  DSH_SESSION_ID  — agent session id (injected by DSH shell-env)
  DSH_WEB_URL     — optional base URL of the Harness web server
  UDS_AUTH_BASE   — optional override, e.g. http://127.0.0.1:PORT/uds-auth
"""
from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse


class UdsAuthError(RuntimeError):
    def __init__(self, message: str, *, code: str = "uds_auth_error", status: int = 0):
        super().__init__(message)
        self.code = code
        self.status = status


def _base_url() -> str:
    explicit = (os.environ.get("UDS_AUTH_BASE") or "").strip().rstrip("/")
    if explicit:
        return explicit
    web = (os.environ.get("DSH_WEB_URL") or "").strip().rstrip("/")
    if web:
        return web + "/uds-auth"
    return "http://127.0.0.1:8787/uds-auth"


def _session_id() -> str:
    return (os.environ.get("DSH_SESSION_ID") or "").strip()


def _opener_no_proxy():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _http_json(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    body: Any = None,
    timeout: float = 30.0,
) -> Tuple[int, Any, str]:
    data = None
    hdrs = dict(headers or {})
    if body is not None:
        if isinstance(body, (dict, list)):
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            hdrs.setdefault("Content-Type", "application/json;charset=UTF-8")
        elif isinstance(body, str):
            data = body.encode("utf-8")
        elif isinstance(body, bytes):
            data = body
        else:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            hdrs.setdefault("Content-Type", "application/json;charset=UTF-8")
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method.upper())
    ctx = ssl._create_unverified_context()
    try:
        if "127.0.0.1" in url or "localhost" in url.lower():
            opener = _opener_no_proxy()
            with opener.open(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                status = getattr(resp, "status", 200) or 200
        else:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                status = getattr(resp, "status", 200) or 200
    except urllib.error.HTTPError as e:
        raw = (e.fp.read().decode("utf-8", errors="replace") if e.fp else "")
        status = e.code
    except urllib.error.URLError as e:
        raise UdsAuthError(f"无法连接 uds-auth: {e.reason}", code="uds_unreachable") from e

    parsed: Any = None
    if raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None
    return status, parsed, raw


def resolve(*, apply_env_aliases: bool = True) -> Dict[str, str]:
    """
    Fetch {empNo, token} for the current DSH session from Host.
    Optionally set process-local EMP_NO / AUTH_VALUE (and coclaw_* aliases).
    """
    sid = _session_id()
    if not sid:
        raise UdsAuthError("缺少 DSH_SESSION_ID，请在 Agent shell 中运行", code="no_session")

    url = _base_url() + "/agent-credentials"
    status, parsed, raw = _http_json(
        "POST",
        url,
        headers={"X-DSH-Session-Id": sid, "Accept": "application/json"},
        body={"sessionId": sid},
        timeout=15.0,
    )
    if status == 401 or (isinstance(parsed, dict) and parsed.get("error") == "no_skill_credentials"):
        msg = (parsed or {}).get("message") if isinstance(parsed, dict) else None
        raise UdsAuthError(msg or "请先完成 UDS 扫码登录", code="no_credentials", status=status)
    if status != 200 or not isinstance(parsed, dict):
        raise UdsAuthError(
            f"获取凭证失败 (HTTP {status})",
            code="credentials_http",
            status=status,
        )
    emp_no = str(parsed.get("empNo") or "").strip()
    token = str(parsed.get("token") or "").strip()
    if not emp_no or not token:
        raise UdsAuthError("凭证响应不完整", code="bad_credentials")

    if apply_env_aliases:
        os.environ["EMP_NO"] = emp_no
        os.environ["AUTH_VALUE"] = token
        os.environ["coclaw_empno"] = emp_no
        os.environ["coclaw_token"] = token

    return {"empNo": emp_no, "token": token, "updatedAt": str(parsed.get("updatedAt") or "")}


def request(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    body: Any = None,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """
    Call an intranet URL via Host outbound proxy (injects X-Emp-No / X-Auth-Value).
    Returns {statusCode, headers, body, json}.
    """
    sid = _session_id()
    if not sid:
        raise UdsAuthError("缺少 DSH_SESSION_ID，请在 Agent shell 中运行", code="no_session")

    host = urlparse(url).hostname or ""
    payload = {
        "sessionId": sid,
        "method": method.upper(),
        "url": url,
        "headers": headers or {},
        "body": body,
        "timeoutMs": int(timeout * 1000),
    }
    status, parsed, raw = _http_json(
        "POST",
        _base_url() + "/outbound",
        headers={"X-DSH-Session-Id": sid, "Accept": "application/json"},
        body=payload,
        timeout=timeout + 5.0,
    )
    if status == 401 or (isinstance(parsed, dict) and parsed.get("error") == "no_skill_credentials"):
        msg = (parsed or {}).get("message") if isinstance(parsed, dict) else None
        raise UdsAuthError(msg or "请先完成 UDS 扫码登录", code="no_credentials", status=status)
    if status == 403 and isinstance(parsed, dict) and parsed.get("error") == "host_not_allowed":
        raise UdsAuthError(f"主机不在 outbound 白名单: {host}", code="host_not_allowed", status=403)
    if not isinstance(parsed, dict) or "statusCode" not in parsed:
        raise UdsAuthError(
            f"outbound 失败 (HTTP {status}): {raw[:200]}",
            code="outbound_http",
            status=status,
        )
    return parsed
