from __future__ import annotations

from typing import Any
import time

import httpx

_TRENDING_CACHE: dict[str, Any] = {"ts": 0.0, "items": []}
_TRENDING_TTL_S = 1800


def _safe_get_json(url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=8.0, follow_redirects=True) as c:
            r = c.get(url, params=params or {}, headers=headers or {})
        if r.status_code != 200:
            return {}
        obj = r.json()
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def search_github_repos(query: str, *, limit: int = 8) -> list[dict[str, Any]]:
    q = str(query or "").strip()
    if not q:
        return []
    blob = _safe_get_json(
        "https://api.github.com/search/repositories",
        params={"q": f"{q} mcp server", "sort": "stars", "order": "desc", "per_page": max(1, min(limit, 20))},
        headers={"Accept": "application/vnd.github+json"},
    )
    items = blob.get("items") if isinstance(blob.get("items"), list) else []
    out: list[dict[str, Any]] = []
    for it in items[:limit]:
        if not isinstance(it, dict):
            continue
        out.append(
            {
                "source_type": "github",
                "name": str(it.get("full_name") or ""),
                "source_ref": str(it.get("clone_url") or it.get("html_url") or ""),
                "description": str(it.get("description") or ""),
                "version": "",
                "homepage": str(it.get("html_url") or ""),
                "stars": int(it.get("stargazers_count") or 0),
                "install_template": infer_install_template("github", str(it.get("clone_url") or it.get("html_url") or "")),
            }
        )
    return out


def search_npm_packages(query: str, *, limit: int = 8) -> list[dict[str, Any]]:
    q = str(query or "").strip()
    if not q:
        return []
    blob = _safe_get_json(
        "https://registry.npmjs.org/-/v1/search",
        params={"text": f"{q} mcp", "size": max(1, min(limit, 20))},
    )
    items = blob.get("objects") if isinstance(blob.get("objects"), list) else []
    out: list[dict[str, Any]] = []
    for it in items[:limit]:
        pkg = it.get("package") if isinstance(it, dict) else None
        if not isinstance(pkg, dict):
            continue
        out.append(
            {
                "source_type": "npm",
                "name": str(pkg.get("name") or ""),
                "source_ref": str(pkg.get("name") or ""),
                "description": str(pkg.get("description") or ""),
                "version": str(pkg.get("version") or ""),
                "homepage": str(pkg.get("links", {}).get("npm") if isinstance(pkg.get("links"), dict) else ""),
                "stars": 0,
                "install_template": infer_install_template("npm", str(pkg.get("name") or "")),
            }
        )
    return out


def search_pypi_packages(query: str, *, limit: int = 8) -> list[dict[str, Any]]:
    q = str(query or "").strip()
    if not q:
        return []
    blob = _safe_get_json(
        "https://pypi.org/search/",
        params={"q": f"{q} mcp"},
        headers={"Accept": "application/json"},
    )
    # PyPI JSON search API is not officially stable; keep best-effort.
    projects = blob.get("projects") if isinstance(blob.get("projects"), list) else []
    out: list[dict[str, Any]] = []
    for it in projects[:limit]:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name") or "")
        out.append(
            {
                "source_type": "pypi",
                "name": name,
                "source_ref": name,
                "description": str(it.get("description") or ""),
                "version": str(it.get("version") or ""),
                "homepage": f"https://pypi.org/project/{name}/" if name else "",
                "stars": 0,
                "install_template": infer_install_template("pypi", name),
            }
        )
    return out


def search_mcp_market(query: str, *, per_source_limit: int = 6) -> list[dict[str, Any]]:
    lim = max(1, min(int(per_source_limit or 6), 20))
    out: list[dict[str, Any]] = []
    out.extend(search_github_repos(query, limit=lim))
    out.extend(search_npm_packages(query, limit=lim))
    out.extend(search_pypi_packages(query, limit=lim))
    return out


def infer_install_template(source_type: str, source_ref: str) -> dict[str, Any]:
    st = str(source_type or "").strip().lower()
    sr = str(source_ref or "").strip()
    if st == "npm":
        pkg = sr.split("/")[-1] if sr else ""
        return {"entry_command": "npx", "entry_args": [pkg] if pkg else []}
    if st == "pypi":
        pkg = sr.replace("-", "_")
        return {"entry_command": "python", "entry_args": ["-m", pkg] if pkg else []}
    return {"entry_command": "python", "entry_args": []}


def trending_mcp_market(*, force_refresh: bool = False, per_source_limit: int = 5) -> list[dict[str, Any]]:
    now = time.time()
    if not force_refresh and _TRENDING_CACHE["items"] and (now - float(_TRENDING_CACHE["ts"] or 0.0) < _TRENDING_TTL_S):
        return list(_TRENDING_CACHE["items"])
    items = search_mcp_market("mcp", per_source_limit=per_source_limit)
    items = sorted(items, key=lambda x: int(x.get("stars") or 0), reverse=True)
    _TRENDING_CACHE["ts"] = now
    _TRENDING_CACHE["items"] = list(items)
    return items


__all__ = [
    "search_mcp_market",
    "search_github_repos",
    "search_npm_packages",
    "search_pypi_packages",
    "infer_install_template",
    "trending_mcp_market",
]

