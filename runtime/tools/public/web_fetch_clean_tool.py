from __future__ import annotations

import re
import urllib.parse
import urllib.request
from html import unescape
from typing import Any

from runtime.tools.base import ToolSpec

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _http_get(url: str, *, timeout_s: int) -> tuple[int, dict[str, str], bytes]:
    req = urllib.request.Request(
        str(url),
        headers={
            "User-Agent": _UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=max(3, min(int(timeout_s), 45))) as resp:
            code = int(getattr(resp, "status", 200) or 200)
            headers = {str(k).lower(): str(v) for k, v in (getattr(resp, "headers", {}) or {}).items()}
            body = resp.read()
            return code, headers, body
    except urllib.error.HTTPError as e:  # type: ignore[attr-defined]
        try:
            body = e.read() or b""
        except Exception:
            body = b""
        headers = {str(k).lower(): str(v) for k, v in (getattr(e, "headers", {}) or {}).items()}
        return int(getattr(e, "code", 0) or 0), headers, body


def _strip_html_keep_lines(html: str) -> str:
    s = str(html or "")
    # Drop scripts/styles/noscript
    s = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", s)
    # Add line breaks for common block tags before stripping
    s = re.sub(r"(?i)</(p|div|br|li|h1|h2|h3|h4|h5|h6|tr|section|article)>", "\n", s)
    s = re.sub(r"(?i)<br\\s*/?>", "\n", s)
    # Strip tags
    s = re.sub(r"(?is)<[^>]+>", " ", s)
    # Decode entities and normalize whitespace
    s = unescape(s)
    s = re.sub(r"[\t\r\f\v]+", " ", s)
    s = re.sub(r" *\\n *", "\n", s)
    s = re.sub(r"\\n{3,}", "\n\n", s)
    s = re.sub(r" {2,}", " ", s)
    return s.strip()


def _extract_title(html: str) -> str:
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", str(html or ""))
    if not m:
        return ""
    t = _strip_html_keep_lines(m.group(1))
    return t.splitlines()[0].strip() if t else ""


def web_fetch_clean_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        payload = args if isinstance(args, dict) else {}
        url = str(payload.get("url") or "").strip()
        if not url:
            return {"ok": False, "error_code": "url_required", "error": "url_required"}
        timeout_s = max(3, min(int(payload.get("timeout") or 20), 45))
        max_chars = max(500, min(int(payload.get("max_chars") or 18000), 200000))

        try:
            parsed = urllib.parse.urlparse(url)
        except Exception:
            return {"ok": False, "error_code": "invalid_url", "error": "invalid_url"}
        if parsed.scheme not in {"http", "https"}:
            return {"ok": False, "error_code": "unsupported_scheme", "error": "unsupported_scheme"}

        try:
            code, headers, body = _http_get(url, timeout_s=timeout_s)
        except Exception as exc:
            return {"ok": False, "error_code": "fetch_failed", "error": f"fetch_failed:{type(exc).__name__}"}

        if int(code) < 200 or int(code) >= 300:
            return {
                "ok": False,
                "error_code": "http_error",
                "error": "http_error",
                "status_code": int(code),
                "content_type": str(headers.get("content-type") or ""),
            }

        ctype = str(headers.get("content-type") or "").lower()
        if ctype and ("text/html" not in ctype and "application/xhtml" not in ctype):
            # Still try to decode as text, but label as non_html for caller decisions.
            try:
                text = body.decode("utf-8", errors="replace")
            except Exception:
                text = ""
            text = text.strip()
            if len(text) > max_chars:
                text = text[:max_chars]
            return {
                "ok": True,
                "url": url,
                "status_code": int(code),
                "content_type": ctype,
                "title": "",
                "text": text,
                "truncated": len(body) > max_chars,
                "mode": "raw_non_html",
            }

        html = body.decode("utf-8", errors="replace")
        title = _extract_title(html)
        text = _strip_html_keep_lines(html)
        truncated = False
        if len(text) > max_chars:
            text = text[:max_chars]
            truncated = True
        return {
            "ok": True,
            "url": url,
            "status_code": int(code),
            "content_type": ctype or "text/html",
            "title": title,
            "text": text,
            "truncated": truncated,
            "mode": "html_strip",
        }

    return ToolSpec(
        name="web_fetch_clean",
        description="Fetch a web page and return cleaned main text (simple HTML stripping).",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "HTTP/HTTPS URL to fetch."},
                "timeout": {"type": "integer", "default": 20, "description": "Timeout seconds [3..45]."},
                "max_chars": {"type": "integer", "default": 18000, "description": "Max returned text chars [500..200000]."},
            },
            "required": ["url"],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "web", "fetch", "read"}),
        risk_level="low",
        read_only=True,
        timeout_s=55.0,
    )


__all__ = ["web_fetch_clean_tool"]

