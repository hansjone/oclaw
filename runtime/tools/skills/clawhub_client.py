from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx


def _strip_trailing_slash(url: str) -> str:
    return str(url or "").strip().rstrip("/")


def _join_url(base: str, path: str) -> str:
    b = _strip_trailing_slash(base)
    p = str(path or "").strip()
    if not p:
        return b
    if not p.startswith("/"):
        p = "/" + p
    return b + p


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


def _safe_get_json_list(url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> list[dict[str, Any]]:
    try:
        with httpx.Client(timeout=8.0, follow_redirects=True) as c:
            r = c.get(url, params=params or {}, headers=headers or {})
        if r.status_code != 200:
            return []
        obj = r.json()
        if isinstance(obj, list):
            return [x for x in obj if isinstance(x, dict)]
        if isinstance(obj, dict) and isinstance(obj.get("items"), list):
            return [x for x in obj.get("items") if isinstance(x, dict)]
        if isinstance(obj, dict) and isinstance(obj.get("results"), list):
            return [x for x in obj.get("results") if isinstance(x, dict)]
        return []
    except Exception:
        return []


@dataclass(frozen=True)
class ClawHubConfig:
    site_base_url: str = "https://clawhub.ai"
    registry_base_url: str | None = None
    token: str | None = None
    api_base_path: str = "/api/v1"


def load_clawhub_config() -> ClawHubConfig:
    site = str(os.getenv("AIA_CLAWHUB_SITE") or os.getenv("CLAWHUB_SITE") or "https://clawhub.ai").strip() or "https://clawhub.ai"
    registry = str(os.getenv("AIA_CLAWHUB_REGISTRY") or os.getenv("CLAWHUB_REGISTRY") or "").strip() or None
    token = str(os.getenv("AIA_CLAWHUB_TOKEN") or os.getenv("CLAWHUB_TOKEN") or "").strip() or None
    api_base = str(os.getenv("AIA_CLAWHUB_API_BASE") or "").strip() or "/api/v1"
    if not api_base.startswith("/"):
        api_base = "/" + api_base
    return ClawHubConfig(site_base_url=site, registry_base_url=registry, token=token, api_base_path=api_base)


def discover_registry_base_url(cfg: ClawHubConfig) -> str:
    if cfg.registry_base_url:
        return _strip_trailing_slash(cfg.registry_base_url)
    wk = _safe_get_json(_join_url(cfg.site_base_url, "/.well-known/clawhub.json"))
    api_base = str(wk.get("apiBase") or "").strip()
    if api_base and api_base.startswith("/"):
        return _strip_trailing_slash(cfg.site_base_url)
    return _strip_trailing_slash(cfg.site_base_url)


def _auth_headers(cfg: ClawHubConfig) -> dict[str, str]:
    tok = str(cfg.token or "").strip()
    if not tok:
        return {}
    return {"Authorization": f"Bearer {tok}"}


def build_download_url(*, registry_base_url: str, api_base_path: str, slug: str, version: str) -> str:
    q = urlencode({"slug": slug, "version": version})
    return _join_url(registry_base_url, f"{api_base_path.rstrip('/')}/download?{q}")


def search_skills(query: str, *, limit: int = 20, cfg: ClawHubConfig | None = None) -> list[dict[str, Any]]:
    cfg = cfg or load_clawhub_config()
    registry = discover_registry_base_url(cfg)
    api = cfg.api_base_path.rstrip("/")
    q = str(query or "").strip()
    lim = max(1, min(int(limit or 20), 200))
    items = _safe_get_json_list(_join_url(registry, f"{api}/search"), params={"q": q, "limit": lim}, headers=_auth_headers(cfg))
    out: list[dict[str, Any]] = []
    for it in items:
        slug = str(it.get("slug") or it.get("name") or "").strip()
        if not slug:
            continue
        version = str(it.get("version") or it.get("latestVersion") or it.get("latest") or "").strip()
        archive_url = build_download_url(registry_base_url=registry, api_base_path=api, slug=slug, version=version) if version else ""
        out.append({"source": "clawhub", "slug": slug, "name": str(it.get("displayName") or it.get("name") or slug), "description": str(it.get("summary") or it.get("description") or ""), "version": version, "owner": str(it.get("owner") or it.get("ownerHandle") or ""), "updatedAt": str(it.get("updatedAt") or ""), "downloads": int(it.get("downloads") or (it.get("stats") or {}).get("downloads") or 0) if isinstance(it.get("stats"), dict) else int(it.get("downloads") or 0), "stars": int(it.get("stars") or (it.get("stats") or {}).get("stars") or 0) if isinstance(it.get("stats"), dict) else int(it.get("stars") or 0), "homepage": str(it.get("homepage") or it.get("url") or ""), "archiveUrl": archive_url, "raw": it})
    return out


def get_skill_detail(slug: str, *, cfg: ClawHubConfig | None = None) -> dict[str, Any]:
    cfg = cfg or load_clawhub_config()
    registry = discover_registry_base_url(cfg)
    api = cfg.api_base_path.rstrip("/")
    s = str(slug or "").strip()
    if not s:
        return {}
    blob = _safe_get_json(_join_url(registry, f"{api}/skills/{s}"), headers=_auth_headers(cfg))
    if not blob:
        return {"slug": s}
    core = blob.get("skill") if isinstance(blob.get("skill"), dict) else blob
    core = core if isinstance(core, dict) else {}
    stats = core.get("stats") if isinstance(core.get("stats"), dict) else {}
    versions: list[dict[str, Any]] = []
    versions_raw = blob.get("versions")
    if not isinstance(versions_raw, list):
        versions_raw = core.get("versions")
    if isinstance(versions_raw, list):
        for v in versions_raw:
            if not isinstance(v, dict):
                continue
            ver = str(v.get("version") or v.get("tag") or "").strip()
            if not ver:
                continue
            versions.append({"version": ver, "changelog": str(v.get("changelog") or ""), "createdAt": str(v.get("createdAt") or ""), "archiveUrl": build_download_url(registry_base_url=registry, api_base_path=api, slug=s, version=ver), "raw": v})
    latest_version_raw = blob.get("latestVersion")
    if latest_version_raw is None:
        latest_version_raw = core.get("latestVersion") or (core.get("tags") if isinstance(core.get("tags"), dict) else {}).get("latest")
    latest_version = str(latest_version_raw.get("version") or "").strip() if isinstance(latest_version_raw, dict) else str(latest_version_raw or blob.get("latest") or "").strip()
    if not latest_version and versions:
        latest_version = str(versions[0].get("version") or "")
    return {
        "source": "clawhub",
        "slug": str(core.get("slug") or s),
        "name": str(core.get("displayName") or core.get("name") or s),
        "description": str(core.get("summary") or core.get("description") or ""),
        "owner": str(core.get("ownerHandle") or (core.get("owner") or {}).get("handle") or "") if isinstance(core.get("owner"), dict) else str(core.get("ownerHandle") or ""),
        "updatedAt": str(core.get("updatedAt") or ""),
        "homepage": str(core.get("homepage") or core.get("url") or ""),
        "latestVersion": latest_version,
        "archiveUrl": build_download_url(registry_base_url=registry, api_base_path=api, slug=s, version=latest_version) if latest_version else "",
        "downloads": int(core.get("downloads") or stats.get("downloads") or 0),
        "stars": int(core.get("stars") or stats.get("stars") or 0),
        "versions": versions,
        "raw": blob,
    }


__all__ = ["ClawHubConfig", "load_clawhub_config", "discover_registry_base_url", "build_download_url", "search_skills", "get_skill_detail"]
