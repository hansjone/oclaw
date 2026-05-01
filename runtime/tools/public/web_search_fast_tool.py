from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from html import unescape
from typing import Any

from oclaw.runtime.tools.base import ToolSpec

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_ENGINE_URLS: dict[str, str] = {
    "bing": "https://www.bing.com/search?q={keyword}&ensearch=1",
    "bing_cn": "https://cn.bing.com/search?q={keyword}&ensearch=0",
    "bing_int": "https://cn.bing.com/search?q={keyword}&ensearch=1",
    "ddg": "https://duckduckgo.com/html/?q={keyword}",
    "google": "https://www.google.com/search?q={keyword}",
    "google_hk": "https://www.google.com.hk/search?q={keyword}",
    "baidu": "https://www.baidu.com/s?wd={keyword}",
    "sogou": "https://www.sogou.com/web?query={keyword}",
}

_ENGINE_ALIASES: dict[str, str] = {
    # config.json style names
    "baidu": "baidu",
    "bing cn": "bing_cn",
    "bing int": "bing_int",
    "bing": "bing",
    "360": "bing_cn",  # fallback route
    "sogou": "sogou",
    "wechat": "sogou",  # best-effort fallback
    "shenma": "bing_cn",  # best-effort fallback
    "google": "google",
    "google hk": "google_hk",
    "duckduckgo": "ddg",
    "yahoo": "bing",  # best-effort fallback
    "startpage": "ddg",
    "brave": "bing",
    "ecosia": "bing",
    "qwant": "bing",
    "wolframalpha": "bing",
}


def _normalize_engine_alias_key(raw: str) -> str:
    return re.sub(r"\s+", " ", str(raw or "").strip().lower().replace("_", " "))


_ENGINE_ALIASES_NORM: dict[str, str] = {_normalize_engine_alias_key(k): v for k, v in _ENGINE_ALIASES.items()}
_AUTO_PROVIDER_ORDER_DEFAULT = ("ddg_html", "bing_html", "ddg_api")
_OFFICIAL_API_KEY_ENV = "OCLAW_WEB_SEARCH_OFFICIAL_API_KEY"
_OFFICIAL_API_URL_ENV = "OCLAW_WEB_SEARCH_OFFICIAL_API_ENDPOINT"
_OFFICIAL_API_DEFAULT_URL = "https://api.bing.microsoft.com/v7.0/search"
_OFFICIAL_BING_KEY_ENV = "OCLAW_WEB_SEARCH_BING_API_KEY"
_OFFICIAL_BING_URL_ENV = "OCLAW_WEB_SEARCH_BING_API_ENDPOINT"
_OFFICIAL_BING_DEFAULT_URL = "https://api.bing.microsoft.com/v7.0/search"
_OFFICIAL_GOOGLE_KEY_ENV = "OCLAW_WEB_SEARCH_GOOGLE_API_KEY"
_OFFICIAL_GOOGLE_CSE_ENV = "OCLAW_WEB_SEARCH_GOOGLE_CSE_ID"
_OFFICIAL_GOOGLE_URL_ENV = "OCLAW_WEB_SEARCH_GOOGLE_API_ENDPOINT"
_OFFICIAL_GOOGLE_DEFAULT_URL = "https://customsearch.googleapis.com/customsearch/v1"


def _http_get_text(url: str, *, timeout_s: int, extra_headers: dict[str, str] | None = None) -> str:
    headers = {
        "User-Agent": _UA,
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if isinstance(extra_headers, dict):
        for k, v in extra_headers.items():
            if str(k or "").strip():
                headers[str(k).strip()] = str(v or "")
    req = urllib.request.Request(
        str(url),
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=max(3, min(int(timeout_s), 30))) as resp:
        raw = resp.read()
    return raw.decode("utf-8", errors="replace")


def _err_tag(prefix: str, exc: Exception) -> str:
    msg = str(exc or "").strip().replace("\n", " ")
    if len(msg) > 180:
        msg = msg[:180] + "..."
    return f"{prefix}:{type(exc).__name__}:{msg or 'failed'}"


def _is_chinese_query(query: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", str(query or "")))


def _classify_error(exc: Exception, provider_name: str = "") -> str:
    p = str(provider_name or "")
    if isinstance(exc, urllib.error.HTTPError):
        code = int(getattr(exc, "code", 0) or 0)
        if p.startswith("official_"):
            if code in {401, 403}:
                return "auth_failed"
            if code == 429:
                return "rate_limited"
            if code == 402:
                return "quota_exceeded"
        if code in {401, 403, 429}:
            return "anti_bot_401_403"
        if code >= 500:
            return "upstream_5xx"
        if 400 <= code < 500:
            return "upstream_4xx"
    msg = str(exc or "").lower()
    if p.startswith("official_"):
        if "invalid api key" in msg or "access denied" in msg or "unauthorized" in msg:
            return "auth_failed"
        if "keyinvalid" in msg or "apikeyinvalid" in msg:
            return "auth_failed"
        if "quota" in msg:
            return "quota_exceeded"
        if "rate limit" in msg or "too many requests" in msg:
            return "rate_limited"
    if "ssrf" in msg or "forbidden host" in msg or "disallow" in msg:
        return "ssrf_blocked"
    if "timed out" in msg or "timeout" in msg:
        return "timeout"
    if "name or service not known" in msg or "nodename nor servname" in msg:
        return "dns_error"
    if "connection reset" in msg or "connection aborted" in msg or "refused" in msg:
        return "network_error"
    return "unknown_error"


def _classify_error_from_tags(tags: list[str]) -> str:
    joined = " ".join(str(x or "").lower() for x in tags)
    if "ssrf" in joined or "forbidden host" in joined:
        return "ssrf_blocked"
    if "timed out" in joined or "timeout" in joined:
        return "timeout"
    if "httperror: http error 401" in joined or "httperror: http error 403" in joined or "httperror: http error 429" in joined:
        return "anti_bot_401_403"
    if "httperror: http error 5" in joined:
        return "upstream_5xx"
    if "httperror: http error 4" in joined:
        return "upstream_4xx"
    if "name or service not known" in joined or "nodename nor servname" in joined:
        return "dns_error"
    if "connection reset" in joined or "connection aborted" in joined or "refused" in joined:
        return "network_error"
    return "unknown_error"


def _classify_error_from_attempts(attempts: list[dict[str, Any]]) -> str:
    for a in attempts:
        if not bool(a.get("ok")) and str(a.get("error_category") or "").strip():
            return str(a.get("error_category"))
    return "unknown_error"


def _search_ddg_api(query: str, *, max_results: int, timeout_s: int) -> list[dict[str, str]]:
    q = urllib.parse.quote_plus(query)
    url = f"https://api.duckduckgo.com/?q={q}&format=json&no_html=1&skip_disambig=0"
    txt = _http_get_text(url, timeout_s=timeout_s)
    obj = json.loads(txt)
    out: list[dict[str, str]] = []

    def _push(title: str, link: str, snippet: str) -> None:
        if not title or not link:
            return
        out.append({"title": title.strip(), "url": link.strip(), "snippet": snippet.strip()})

    abs_text = str(obj.get("AbstractText") or "").strip()
    abs_url = str(obj.get("AbstractURL") or "").strip()
    heading = str(obj.get("Heading") or "").strip()
    if abs_text and abs_url:
        _push(heading or abs_url, abs_url, abs_text)

    def _walk_related(items: list[Any]) -> None:
        for it in items:
            if len(out) >= max_results:
                return
            if isinstance(it, dict) and isinstance(it.get("Topics"), list):
                _walk_related(list(it.get("Topics") or []))
                continue
            if not isinstance(it, dict):
                continue
            text = str(it.get("Text") or "").strip()
            link = str(it.get("FirstURL") or "").strip()
            if text and link:
                title = text.split(" - ", 1)[0].strip() or link
                _push(title, link, text)

    _walk_related(list(obj.get("RelatedTopics") or []))
    return out[:max_results]


def _strip_html(s: str) -> str:
    no_tags = re.sub(r"<[^>]+>", " ", str(s or ""))
    compact = re.sub(r"\s+", " ", no_tags).strip()
    return unescape(compact)


def _search_ddg_html(query: str, *, max_results: int, timeout_s: int) -> list[dict[str, str]]:
    q = urllib.parse.quote_plus(query)
    url = f"https://duckduckgo.com/html/?q={q}"
    html = _http_get_text(url, timeout_s=timeout_s)
    patt = re.compile(
        r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    snippets = re.findall(
        r'<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    out: list[dict[str, str]] = []
    for idx, m in enumerate(patt.finditer(html)):
        if len(out) >= max_results:
            break
        href = unescape(_strip_html(m.group("href")))
        title = _strip_html(m.group("title"))
        if not href or not title:
            continue
        if href.startswith("/"):
            href = urllib.parse.urljoin("https://duckduckgo.com", href)
        snippet = _strip_html(snippets[idx]) if idx < len(snippets) else ""
        out.append({"title": title, "url": href, "snippet": snippet})
    return out[:max_results]


def _search_bing_html(query: str, *, max_results: int, timeout_s: int, search_url: str | None = None) -> list[dict[str, str]]:
    q = urllib.parse.quote_plus(query)
    url = str(search_url or f"https://www.bing.com/search?q={q}&ensearch=1")
    html = _http_get_text(url, timeout_s=timeout_s)
    patt = re.compile(
        r'<li[^>]+class="[^"]*b_algo[^"]*"[^>]*>.*?<h2>\s*<a[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>\s*</h2>(?P<body>.*?)</li>',
        re.IGNORECASE | re.DOTALL,
    )
    out: list[dict[str, str]] = []
    for m in patt.finditer(html):
        if len(out) >= max_results:
            break
        href = unescape(_strip_html(m.group("href")))
        title = _strip_html(m.group("title"))
        body = str(m.group("body") or "")
        sm = re.search(r"<p[^>]*>(.*?)</p>", body, flags=re.IGNORECASE | re.DOTALL)
        snippet = _strip_html(sm.group(1)) if sm else _strip_html(body)[:220]
        if not href or not title:
            continue
        out.append({"title": title, "url": href, "snippet": snippet})
    return out[:max_results]


def _search_generic_html(url: str, *, max_results: int, timeout_s: int) -> list[dict[str, str]]:
    html = _http_get_text(url, timeout_s=timeout_s)
    # Generic fallback parser for engines not explicitly adapted:
    # pick visible anchors with http(s) href and non-trivial title text.
    patt = re.compile(r'<a[^>]+href="(?P<href>https?://[^"]+)"[^>]*>(?P<title>.*?)</a>', re.IGNORECASE | re.DOTALL)
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for m in patt.finditer(html):
        if len(out) >= max_results:
            break
        href = unescape(_strip_html(m.group("href")))
        title = _strip_html(m.group("title"))
        if not href or not title or len(title) < 3:
            continue
        # Skip obvious nav links
        low = title.lower()
        if low in {"next", "prev", "previous", "about", "help", "privacy", "login", "sign in"}:
            continue
        if href in seen:
            continue
        seen.add(href)
        out.append({"title": title, "url": href, "snippet": ""})
    return out[:max_results]


def _normalize_engine_name(raw: str) -> str:
    src = str(raw or "").strip().lower()
    if not src:
        return ""
    key_space = _normalize_engine_alias_key(src)
    alias = _ENGINE_ALIASES_NORM.get(key_space)
    if alias:
        return alias
    return src.replace(" ", "_")


def _build_query_with_site(*, query: str, site: str) -> str:
    q = str(query or "").strip()
    s = str(site or "").strip()
    if not s:
        return q
    if s.startswith("site:"):
        s = s[5:].strip()
    s = s.strip("/")
    if not s:
        return q
    return f"site:{s} {q}".strip()


def _search_by_engine_url(
    *,
    engine_url_template: str,
    query: str,
    max_results: int,
    timeout_s: int,
) -> list[dict[str, str]]:
    q = urllib.parse.quote_plus(query)
    if "{keyword}" in str(engine_url_template):
        url = str(engine_url_template).replace("{keyword}", q)
    else:
        sep = "&" if ("?" in str(engine_url_template)) else "?"
        url = f"{engine_url_template}{sep}q={q}"
    low = url.lower()
    if "bing.com/search" in low:
        return _search_bing_html(query, max_results=max_results, timeout_s=timeout_s, search_url=url)
    if "duckduckgo.com" in low:
        return _search_ddg_html(query, max_results=max_results, timeout_s=timeout_s)
    return _search_generic_html(url, max_results=max_results, timeout_s=timeout_s)


def _search_official_api(
    query: str,
    *,
    max_results: int,
    timeout_s: int,
    api_key: str,
    endpoint: str,
) -> list[dict[str, str]]:
    base = str(endpoint or "").strip() or _OFFICIAL_API_DEFAULT_URL
    sep = "&" if ("?" in base) else "?"
    url = f"{base}{sep}q={urllib.parse.quote_plus(query)}&count={int(max_results)}"
    txt = _http_get_text(
        url,
        timeout_s=timeout_s,
        extra_headers={"Ocp-Apim-Subscription-Key": str(api_key or "").strip(), "Accept": "application/json"},
    )
    obj = json.loads(txt)
    out: list[dict[str, str]] = []
    web_pages = obj.get("webPages") if isinstance(obj, dict) else None
    values = web_pages.get("value") if isinstance(web_pages, dict) else None
    if isinstance(values, list):
        for it in values:
            if len(out) >= max_results:
                break
            if not isinstance(it, dict):
                continue
            title = str(it.get("name") or "").strip()
            href = str(it.get("url") or "").strip()
            snippet = str(it.get("snippet") or "").strip()
            if title and href:
                out.append({"title": title, "url": href, "snippet": snippet})
    return out[:max_results]


def _search_official_google_api(
    query: str,
    *,
    max_results: int,
    timeout_s: int,
    api_key: str,
    cse_id: str,
    endpoint: str,
) -> list[dict[str, str]]:
    base = str(endpoint or "").strip() or _OFFICIAL_GOOGLE_DEFAULT_URL
    sep = "&" if ("?" in base) else "?"
    url = (
        f"{base}{sep}q={urllib.parse.quote_plus(query)}"
        f"&num={int(max_results)}&key={urllib.parse.quote_plus(str(api_key or '').strip())}"
        f"&cx={urllib.parse.quote_plus(str(cse_id or '').strip())}"
    )
    txt = _http_get_text(url, timeout_s=timeout_s, extra_headers={"Accept": "application/json"})
    obj = json.loads(txt)
    out: list[dict[str, str]] = []
    items = obj.get("items") if isinstance(obj, dict) else None
    if isinstance(items, list):
        for it in items:
            if len(out) >= max_results:
                break
            if not isinstance(it, dict):
                continue
            title = str(it.get("title") or "").strip()
            href = str(it.get("link") or "").strip()
            snippet = str(it.get("snippet") or "").strip()
            if title and href:
                out.append({"title": title, "url": href, "snippet": snippet})
    return out[:max_results]


def web_search_fast_tool() -> ToolSpec:
    def _handler(args: dict[str, Any]) -> dict[str, Any]:
        payload = args if isinstance(args, dict) else {}
        query = str(payload.get("query") or "").strip()
        if not query:
            return {"ok": False, "error_code": "query_required", "error": "query_required"}
        site = str(payload.get("site") or "").strip()
        query = _build_query_with_site(query=query, site=site)
        max_results = max(1, min(int(payload.get("max_results") or 8), 20))
        timeout_s = max(3, min(int(payload.get("timeout") or 12), 30))
        provider = str(payload.get("provider") or "auto").strip().lower()
        official_provider = str(payload.get("official_provider") or "auto").strip().lower()
        engine = _normalize_engine_name(str(payload.get("engine") or ""))
        engine_url = str(payload.get("engine_url") or "").strip()
        official_bing_key = str(os.getenv(_OFFICIAL_BING_KEY_ENV) or os.getenv(_OFFICIAL_API_KEY_ENV) or "").strip()
        official_bing_endpoint = str(os.getenv(_OFFICIAL_BING_URL_ENV) or os.getenv(_OFFICIAL_API_URL_ENV) or _OFFICIAL_BING_DEFAULT_URL).strip()
        official_google_key = str(os.getenv(_OFFICIAL_GOOGLE_KEY_ENV) or "").strip()
        official_google_cse_id = str(os.getenv(_OFFICIAL_GOOGLE_CSE_ENV) or "").strip()
        official_google_endpoint = str(os.getenv(_OFFICIAL_GOOGLE_URL_ENV) or _OFFICIAL_GOOGLE_DEFAULT_URL).strip()
        used = "auto"
        errors: list[str] = []
        results: list[dict[str, str]] = []
        provider_attempts: list[dict[str, Any]] = []

        def _attempt(provider_name: str, fn: Any) -> list[dict[str, str]]:
            started = time.perf_counter()
            try:
                r = list(fn() or [])
                provider_attempts.append(
                    {
                        "provider": provider_name,
                        "ok": True,
                        "count": len(r),
                        "elapsed_ms": int((time.perf_counter() - started) * 1000),
                    }
                )
                return r
            except Exception as exc:
                provider_attempts.append(
                    {
                        "provider": provider_name,
                        "ok": False,
                        "count": 0,
                        "error_category": _classify_error(exc, provider_name),
                        "error": _err_tag(provider_name, exc),
                        "elapsed_ms": int((time.perf_counter() - started) * 1000),
                    }
                )
                raise

        # Skill-controlled path: explicit engine URL template or named engine.
        if engine_url:
            try:
                results = _attempt(
                    "engine_url",
                    lambda: _search_by_engine_url(
                        engine_url_template=engine_url,
                        query=query,
                        max_results=max_results,
                        timeout_s=timeout_s,
                    ),
                )
                used = "engine_url"
            except Exception as exc:
                errors.append(_err_tag("engine_url", exc))
        elif engine:
            template = _ENGINE_URLS.get(engine, "")
            if not template:
                errors.append(f"engine:unsupported:{engine}")
            else:
                try:
                    results = _attempt(
                        f"engine:{engine}",
                        lambda: _search_by_engine_url(
                            engine_url_template=template,
                            query=query,
                            max_results=max_results,
                            timeout_s=timeout_s,
                        ),
                    )
                    used = f"engine:{engine}"
                except Exception as exc:
                    errors.append(_err_tag(f"engine:{engine}", exc))

        official_order: list[str] = []
        if official_provider in {"auto", "bing"} and official_bing_key:
            official_order.append("official_bing")
        if official_provider in {"auto", "google"} and official_google_key and official_google_cse_id:
            official_order.append("official_google")
        if official_provider == "google" and not official_order and official_bing_key:
            official_order.append("official_bing")
        if official_provider == "bing" and not official_order and official_google_key and official_google_cse_id:
            official_order.append("official_google")
        auto_order = [*official_order, *_AUTO_PROVIDER_ORDER_DEFAULT]
        run_order = auto_order if provider == "auto" else [provider]
        if provider == "official_api":
            run_order = official_order or ["official_bing", "official_google"]

        for p in run_order:
            if results:
                break
            if p == "ddg_api":
                try:
                    results = _attempt("ddg_api", lambda: _search_ddg_api(query, max_results=max_results, timeout_s=timeout_s))
                    used = "ddg_api"
                except Exception as exc:
                    errors.append(_err_tag("ddg_api", exc))
            elif p == "ddg_html":
                try:
                    results = _attempt("ddg_html", lambda: _search_ddg_html(query, max_results=max_results, timeout_s=timeout_s))
                    used = "ddg_html"
                except Exception as exc:
                    errors.append(_err_tag("ddg_html", exc))
            elif p == "bing_html":
                try:
                    results = _attempt("bing_html", lambda: _search_bing_html(query, max_results=max_results, timeout_s=timeout_s))
                    used = "bing_html"
                except Exception as exc:
                    errors.append(_err_tag("bing_html", exc))
            elif p == "official_api":
                continue
            elif p == "official_bing":
                if not official_bing_key:
                    msg = f"official_bing:missing_key_env:{_OFFICIAL_BING_KEY_ENV}"
                    errors.append(msg)
                    provider_attempts.append(
                        {
                            "provider": "official_bing",
                            "ok": False,
                            "count": 0,
                            "error_category": "auth_failed",
                            "error": msg,
                            "elapsed_ms": 0,
                        }
                    )
                    continue
                try:
                    results = _attempt(
                        "official_bing",
                        lambda: _search_official_api(
                            query,
                            max_results=max_results,
                            timeout_s=timeout_s,
                            api_key=official_bing_key,
                            endpoint=official_bing_endpoint,
                        ),
                    )
                    used = "official_bing"
                except Exception as exc:
                    errors.append(_err_tag("official_bing", exc))
            elif p == "official_google":
                if not official_google_key or not official_google_cse_id:
                    miss = _OFFICIAL_GOOGLE_KEY_ENV if not official_google_key else _OFFICIAL_GOOGLE_CSE_ENV
                    msg = f"official_google:missing_key_env:{miss}"
                    errors.append(msg)
                    provider_attempts.append(
                        {
                            "provider": "official_google",
                            "ok": False,
                            "count": 0,
                            "error_category": "auth_failed",
                            "error": msg,
                            "elapsed_ms": 0,
                        }
                    )
                    continue
                try:
                    results = _attempt(
                        "official_google",
                        lambda: _search_official_google_api(
                            query,
                            max_results=max_results,
                            timeout_s=timeout_s,
                            api_key=official_google_key,
                            cse_id=official_google_cse_id,
                            endpoint=official_google_endpoint,
                        ),
                    )
                    used = "official_google"
                except Exception as exc:
                    errors.append(_err_tag("official_google", exc))

        if not results:
            error_category = "no_results"
            if errors:
                error_category = _classify_error_from_attempts(provider_attempts)
                if error_category == "unknown_error":
                    error_category = _classify_error_from_tags(errors)
            return {
                "ok": False,
                "error_code": "search_failed",
                "error": "search_failed",
                "error_category": error_category,
                "provider": used,
                "query": query,
                "site": site,
                "engine": engine or "",
                "errors": errors,
                "tried": run_order,
                "provider_attempts": provider_attempts,
            }
        return {
            "ok": True,
            "query": query,
            "site": site,
            "engine": engine or "",
            "provider": used,
            "count": len(results),
            "results": results,
            "errors": errors,
            "provider_attempts": provider_attempts,
        }

    return ToolSpec(
        name="web_search_fast",
        description="Fast public web search with API-first and HTML fallback.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query."},
                "site": {"type": "string", "description": "Optional site/domain constraint; converted to `site:...` query qualifier."},
                "engine": {
                    "type": "string",
                    "description": "Optional named engine (e.g. bing, bing_cn, ddg, google, baidu, sogou).",
                },
                "engine_url": {
                    "type": "string",
                    "description": "Optional engine URL template containing `{keyword}`; overrides `engine` and provider fallback.",
                },
                "max_results": {"type": "integer", "default": 8, "description": "Max results [1..20]."},
                "provider": {
                    "type": "string",
                    "enum": ["auto", "official_api", "official_bing", "official_google", "ddg_api", "ddg_html", "bing_html"],
                    "default": "auto",
                    "description": "Search backend; auto tries configured official providers then ddg_html -> bing_html -> ddg_api.",
                },
                "official_provider": {
                    "type": "string",
                    "enum": ["auto", "bing", "google"],
                    "default": "auto",
                    "description": "Preference/order hint for official providers when provider=auto or official_api.",
                },
                "timeout": {"type": "integer", "default": 12, "description": "HTTP timeout seconds [3..30]."},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=_handler,
        tags=frozenset({"public", "search", "web", "read"}),
        risk_level="low",
        read_only=True,
        timeout_s=35.0,
    )


__all__ = ["web_search_fast_tool"]

