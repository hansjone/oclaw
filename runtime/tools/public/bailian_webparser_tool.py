from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from typing import Any

from oclaw.runtime.tools.base import ToolSpec

_WEBPARSER_SSE_URL = "https://dashscope.aliyuncs.com/api/v1/mcps/WebParser/sse"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _open_request(
    url: str,
    *,
    timeout_s: int,
    headers: dict[str, str],
    body: dict[str, Any] | None = None,
):
    data = None
    method = "GET"
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        method = "POST"
    req = urllib.request.Request(str(url), data=data, headers=headers, method=method)
    return urllib.request.urlopen(req, timeout=max(5, min(int(timeout_s), 90)))


def _read_sse_until(
    sse_resp,
    *,
    timeout_s: int,
    message_url: str | None = None,
    wait_id: int | None = None,
    auth_header: str = "",
) -> dict[str, Any] | None:
    deadline = time.time() + max(3, int(timeout_s))
    event_name = ""
    while time.time() < deadline:
        raw = sse_resp.readline()
        if not raw:
            continue
        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        if line.startswith("event:"):
            event_name = line[6:].strip()
            continue
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if event_name == "endpoint" and wait_id is None:
            return {"endpoint": data}
        try:
            obj = json.loads(data)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        # Keep-alive ping from server; respond with empty result.
        if (
            message_url
            and isinstance(obj.get("id"), (int, str))
            and str(obj.get("method") or "").strip() == "ping"
        ):
            try:
                _open_request(
                    message_url,
                    timeout_s=10,
                    headers={
                        "Authorization": auth_header,
                        "Content-Type": "application/json",
                        "User-Agent": _UA,
                    },
                    body={"jsonrpc": "2.0", "id": obj.get("id"), "result": {}},
                ).close()
            except Exception:
                pass
            continue
        if wait_id is not None and obj.get("id") == wait_id:
            return obj
    return None


def _call_webparser(url: str, *, api_key: str, timeout_s: int) -> dict[str, Any]:
    auth_header = f"Bearer {api_key}"
    sse_headers = {
        "Authorization": auth_header,
        "Accept": "text/event-stream",
        "User-Agent": _UA,
    }
    with _open_request(_WEBPARSER_SSE_URL, timeout_s=timeout_s, headers=sse_headers) as sse_resp:
        endpoint_evt = _read_sse_until(sse_resp, timeout_s=timeout_s)
        endpoint = str((endpoint_evt or {}).get("endpoint") or "").strip()
        if not endpoint or "/message?" not in endpoint:
            return {"ok": False, "error_code": "webparser_no_endpoint", "error": "webparser_no_endpoint"}
        message_url = urllib.parse.urljoin(_WEBPARSER_SSE_URL, endpoint)

        def _post(payload: dict[str, Any], post_timeout: int = 30) -> None:
            with _open_request(
                message_url,
                timeout_s=post_timeout,
                headers={
                    "Authorization": auth_header,
                    "Content-Type": "application/json",
                    "User-Agent": _UA,
                },
                body=payload,
            ):
                return

        _post(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "oclaw-bailian-webparser", "version": "0.1.0"},
                },
            }
        )
        init_res = _read_sse_until(
            sse_resp,
            timeout_s=timeout_s,
            message_url=message_url,
            wait_id=1,
            auth_header=auth_header,
        )
        if not init_res or not isinstance(init_res.get("result"), dict):
            return {"ok": False, "error_code": "webparser_initialize_failed", "error": "initialize_no_result"}

        _post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}, post_timeout=12)
        _post({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        list_res = _read_sse_until(
            sse_resp,
            timeout_s=timeout_s,
            message_url=message_url,
            wait_id=2,
            auth_header=auth_header,
        )
        tools = []
        try:
            tools = list((list_res or {}).get("result", {}).get("tools") or [])
        except Exception:
            tools = []
        if not tools:
            return {
                "ok": False,
                "error_code": "webparser_tools_empty",
                "error": "tools_list_empty",
                "initialize": init_res,
                "tools_list": list_res,
            }
        tool_name = str((tools[0] or {}).get("name") or "").strip()
        if not tool_name:
            return {"ok": False, "error_code": "webparser_tool_name_missing", "error": "tool_name_missing"}

        candidate_args = (
            {"url": url},
            {"urls": [url]},
            {"query": url},
        )
        call_res: dict[str, Any] | None = None
        used_args: dict[str, Any] | None = None
        for args in candidate_args:
            _post({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": tool_name, "arguments": args}})
            call_res = _read_sse_until(
                sse_resp,
                timeout_s=timeout_s,
                message_url=message_url,
                wait_id=3,
                auth_header=auth_header,
            )
            if call_res and not isinstance(call_res.get("error"), dict):
                used_args = args
                break
        if not call_res:
            return {"ok": False, "error_code": "webparser_call_timeout", "error": "call_timeout"}
        if isinstance(call_res.get("error"), dict):
            return {
                "ok": False,
                "error_code": "webparser_call_failed",
                "error": str((call_res.get("error") or {}).get("message") or "webparser_call_failed"),
                "rpc_error": call_res.get("error"),
                "tool_name": tool_name,
                "arguments": used_args or {"url": url},
            }
        result = call_res.get("result")
        text_parts: list[str] = []
        if isinstance(result, dict):
            for it in list(result.get("content") or []):
                if isinstance(it, dict) and str(it.get("type") or "") == "text":
                    txt = str(it.get("text") or "").strip()
                    if txt:
                        text_parts.append(txt)
        return {
            "ok": True,
            "tool_name": tool_name,
            "arguments": used_args or {"url": url},
            "text": "\n\n".join(text_parts).strip(),
            "result": result,
        }


def bailian_webparser_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        payload = args if isinstance(args, dict) else {}
        url = str(payload.get("url") or "").strip()
        if not url:
            return {
                "ok": False,
                "error_code": "url_required",
                "error": 'url_required: provide {"url":"https://example.com/article"}',
            }
        timeout_s = max(8, min(int(payload.get("timeout") or 35), 90))
        api_key = str(payload.get("api_key") or os.getenv("DASHSCOPE_API_KEY") or "").strip()
        if not api_key:
            return {"ok": False, "error_code": "api_key_missing", "error": "DASHSCOPE_API_KEY required"}
        try:
            p = urllib.parse.urlparse(url)
        except Exception:
            return {
                "ok": False,
                "error_code": "invalid_url",
                "error": 'invalid_url: provide full http/https URL, e.g. {"url":"https://example.com/article"}',
            }
        if p.scheme not in {"http", "https"}:
            return {
                "ok": False,
                "error_code": "unsupported_scheme",
                "error": "unsupported_scheme: url must start with http:// or https://",
            }
        try:
            out = _call_webparser(url, api_key=api_key, timeout_s=timeout_s)
            return out
        except Exception as exc:
            return {"ok": False, "error_code": "webparser_runtime_failed", "error": f"{type(exc).__name__}: {exc}"}

    return ToolSpec(
        name="bailian_webparser",
        description="Parse webpage content via DashScope WebParser (SSE-compatible fallback path). `url` is required.",
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Target webpage URL to parse (required). Example: https://example.com/article",
                },
                "timeout": {
                    "type": "integer",
                    "default": 35,
                    "minimum": 8,
                    "maximum": 90,
                    "description": "Total timeout seconds [8..90].",
                },
                "api_key": {
                    "type": "string",
                    "description": "Optional DashScope API key override; defaults to DASHSCOPE_API_KEY.",
                },
            },
            "required": ["url"],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "web", "parser", "read"}),
        risk_level="low",
        read_only=True,
        timeout_s=95.0,
    )


__all__ = ["bailian_webparser_tool"]

