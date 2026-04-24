"""基于 DuckDuckGo（ddgs 包）的公网搜索工具（无需 API Key）。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from oclaw.runtime.tools.base import ToolSpec

_MAX_SNIPPET = 800
_DDGS_TIMEOUT = 15


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truncate(s: str, limit: int) -> str:
    t = (s or "").strip()
    if len(t) <= limit:
        return t
    return t[: limit - 3] + "..."


def _published_display_and_sort_key(raw: Any) -> tuple[str | None, float]:
    if raw is None:
        return None, float("-inf")
    if isinstance(raw, (int, float)):
        try:
            ts = float(raw)
            dt = datetime.fromtimestamp(ts, timezone.utc)
            return dt.isoformat(), ts
        except (OSError, OverflowError, ValueError):
            return str(raw), float("-inf")
    s = str(raw).strip()
    if not s:
        return None, float("-inf")
    try:
        s2 = s[:-1] + "+00:00" if s.endswith("Z") else s
        dt = datetime.fromisoformat(s2)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        iso = dt.astimezone(timezone.utc).isoformat()
        return iso, dt.timestamp()
    except Exception:
        return s, float("-inf")


def web_search_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        q = str(args.get("query") or "").strip()
        if not q:
            return {"ok": False, "error": "query is required"}
        raw_max = args.get("max_results")
        try:
            max_n = int(raw_max) if raw_max is not None else 8
        except (TypeError, ValueError):
            max_n = 8
        max_n = max(1, min(15, max_n))
        stype = str(args.get("search_type") or "web").strip().lower()
        if stype not in ("web", "news"):
            return {"ok": False, "error": "search_type must be 'web' or 'news'"}
        timelimit = args.get("time_range")
        if timelimit is not None and timelimit != "":
            tl = str(timelimit).strip().lower()
            allowed = {"d", "w", "m", "y"}
            if tl not in allowed:
                return {"ok": False, "error": f"time_range must be one of {sorted(allowed)} or omitted"}
            timelimit = tl
        else:
            timelimit = None
        try:
            from ddgs import DDGS
        except ImportError:
            return {"ok": False, "error": "Package `ddgs` is not installed. Run: pip install ddgs"}

        retrieved_at = _utc_now_iso()
        try:
            rows: list[dict[str, Any]] = []
            with DDGS(timeout=_DDGS_TIMEOUT) as ddgs:
                if stype == "web":
                    for r in ddgs.text(q, max_results=max_n, timelimit=timelimit):
                        if not isinstance(r, dict):
                            continue
                        title = _truncate(str(r.get("title") or ""), 300)
                        url = str(r.get("href") or r.get("url") or "").strip()
                        body = _truncate(str(r.get("body") or ""), _MAX_SNIPPET)
                        if title or url or body:
                            rows.append({"title": title, "url": url, "snippet": body, "published_time": None})
                    sort_mode = "relevance"
                    note = "Web index does not provide reliable per-result publication times; order follows search relevance. Use search_type=news for time-sorted news."
                else:
                    decorated: list[tuple[float, dict[str, Any]]] = []
                    for r in ddgs.news(q, max_results=max_n, timelimit=timelimit):
                        if not isinstance(r, dict):
                            continue
                        title = _truncate(str(r.get("title") or ""), 300)
                        url = str(r.get("url") or r.get("href") or "").strip()
                        body = _truncate(str(r.get("body") or ""), _MAX_SNIPPET)
                        pub, sk = _published_display_and_sort_key(r.get("date"))
                        src = str(r.get("source") or "").strip()
                        item = {"title": title, "url": url, "snippet": body, "published_time": pub}
                        if src:
                            item["source"] = src
                        if title or url or body:
                            decorated.append((sk, item))
                    decorated.sort(key=lambda x: x[0], reverse=True)
                    rows = [x[1] for x in decorated]
                    sort_mode = "published_time_desc"
                    note = "News results sorted by published_time (newest first). Snippets are from third-party indexes; verify critical facts."

            if not rows:
                return {"ok": True, "query": q, "search_type": stype, "retrieved_at": retrieved_at, "sort": sort_mode, "results": [], "note": "No results (empty or blocked). Try rephrasing the query."}
            return {"ok": True, "query": q, "search_type": stype, "retrieved_at": retrieved_at, "sort": sort_mode, "results": rows, "source": "duckduckgo", "note": note}
        except Exception as e:
            return {"ok": False, "error": f"Web search failed: {e}"}

    return ToolSpec(
        name="web_search",
        description="Search the public web (DuckDuckGo via ddgs, no API key).",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keywords or question."},
                "max_results": {"type": "integer", "description": "Optional. Number of results (1–15). Default 8."},
                "search_type": {"type": "string", "enum": ["web", "news"], "description": "Optional. 'web' or 'news'."},
                "time_range": {"type": "string", "enum": ["d", "w", "m", "y"], "description": "Optional time limit."},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=handler,
    )


__all__ = ["web_search_tool"]
