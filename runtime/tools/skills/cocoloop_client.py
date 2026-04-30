"""CocoLoop 技能商店 HTTP 客户端（与 ClawHub 并列，供 `skills_market` 使用）。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

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


@dataclass(frozen=True)
class CocoloopConfig:
    api_base_url: str = "https://api.cocoloop.com"


def load_cocoloop_config() -> CocoloopConfig:
    base = str(os.getenv("AIA_COCOLOOP_API_BASE") or os.getenv("COCOLOOP_API_BASE") or "https://api.cocoloop.com").strip()
    return CocoloopConfig(api_base_url=_strip_trailing_slash(base))


def _default_headers() -> dict[str, str]:
    return {
        "User-Agent": "Oclaw-SkillMarket/1.0 (+https://github.com/oclaw)",
        "Accept": "application/json",
    }


def _get_json(url: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=12.0, follow_redirects=True) as c:
            r = c.get(url, params=params or {}, headers=_default_headers())
        if r.status_code != 200:
            return {}
        obj = r.json()
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _list_items(cfg: CocoloopConfig, *, keyword: str, page: int, page_size: int) -> list[dict[str, Any]]:
    url = _join_url(cfg.api_base_url, "/api/v1/store/skills")
    blob = _get_json(
        url,
        params={
            "page": max(1, int(page)),
            "page_size": max(1, min(int(page_size), 100)),
            "keyword": str(keyword or "").strip(),
            "sort": "downloads",
        },
    )
    data = blob.get("data") if isinstance(blob.get("data"), dict) else {}
    items = data.get("items")
    if not isinstance(items, list):
        return []
    return [x for x in items if isinstance(x, dict)]


def _normalize_list_row(raw: dict[str, Any]) -> dict[str, Any]:
    slug = str(raw.get("name") or "").strip()
    dl = str(raw.get("download_url") or "").strip()
    ver = str(raw.get("version") or "").strip() or "latest"
    return {
        "source": "cocoloop",
        "slug": slug,
        "name": str(raw.get("subtitle") or raw.get("summary") or slug),
        "description": str(raw.get("brief") or raw.get("summary") or raw.get("original_desc") or ""),
        "version": ver,
        "owner": str(raw.get("author") or ""),
        "updatedAt": "",
        "downloads": _parse_count(raw.get("downloads")),
        "stars": _parse_count(raw.get("github_stars")),
        "homepage": f"https://hub.cocoloop.cn/skills/{raw.get('id')}" if raw.get("id") else "",
        "archiveUrl": dl,
        "raw": raw,
    }


def _parse_count(v: Any) -> int:
    if isinstance(v, int):
        return v
    s = str(v or "").strip().lower().replace(",", "")
    if not s:
        return 0
    mult = 1
    if s.endswith("k"):
        mult = 1000
        s = s[:-1]
    if s.endswith("m"):
        mult = 1_000_000
        s = s[:-1]
    try:
        return int(float(s) * mult)
    except ValueError:
        return 0


def search_store_skills(query: str, *, limit: int = 20, cfg: CocoloopConfig | None = None) -> list[dict[str, Any]]:
    cfg = cfg or load_cocoloop_config()
    lim = max(1, min(int(limit or 20), 100))
    rows = _list_items(cfg, keyword=str(query or "").strip(), page=1, page_size=lim)
    return [_normalize_list_row(r) for r in rows if str(r.get("name") or "").strip()]


def get_skill_detail_by_slug(slug: str, *, cfg: CocoloopConfig | None = None) -> dict[str, Any]:
    """按商店 `name`（slug）解析技能；必要时用数字 id 直查。"""
    cfg = cfg or load_cocoloop_config()
    s = str(slug or "").strip()
    if not s:
        return {}
    if s.isdigit():
        return _detail_from_id(cfg, int(s))
    rows = _list_items(cfg, keyword=s, page=1, page_size=80)
    want = s.lower()
    hit: dict[str, Any] | None = None
    for r in rows:
        if str(r.get("name") or "").strip().lower() == want:
            hit = r
            break
    if hit is None:
        for r in rows:
            nm = str(r.get("name") or "").strip().lower()
            if want in nm or nm in want:
                hit = r
                break
    if hit is None:
        return {"slug": s, "source": "cocoloop"}
    return _detail_from_list_row(cfg, hit)


def _detail_from_id(cfg: CocoloopConfig, skill_id: int) -> dict[str, Any]:
    url = _join_url(cfg.api_base_url, f"/api/v1/store/skills/{int(skill_id)}")
    blob = _get_json(url)
    data = blob.get("data") if isinstance(blob.get("data"), dict) else {}
    if not data:
        return {"slug": str(skill_id), "source": "cocoloop"}
    return _detail_from_list_row(cfg, data)


def _detail_from_list_row(cfg: CocoloopConfig, row: dict[str, Any]) -> dict[str, Any]:
    slug = str(row.get("name") or "").strip()
    dl = str(row.get("download_url") or "").strip()
    if not dl and slug:
        asset = str(row.get("asset_name") or f"{slug}.zip").strip()
        if not asset.endswith(".zip"):
            asset = f"{asset}.zip"
        dl = f"https://dl.cocoloop.cn/bss/skills/{asset.lstrip('/')}"
    ver = str(row.get("version") or "").strip() or "latest"
    ver_clean = ver.lstrip("vV") if ver not in {"", "latest"} else ver
    versions: list[dict[str, Any]] = [{"version": ver_clean or "latest", "changelog": "", "createdAt": "", "archiveUrl": dl, "raw": row}]
    return {
        "source": "cocoloop",
        "slug": slug,
        "name": str(row.get("subtitle") or row.get("summary") or slug),
        "description": str(row.get("brief") or row.get("summary") or row.get("original_desc") or ""),
        "owner": str(row.get("author") or ""),
        "updatedAt": "",
        "homepage": f"https://hub.cocoloop.cn/skills/{row.get('id')}" if row.get("id") else "",
        "latestVersion": ver_clean if ver_clean else "latest",
        "archiveUrl": dl,
        "downloads": _parse_count(row.get("downloads")),
        "stars": _parse_count(row.get("github_stars")),
        "versions": versions,
        "raw": row,
    }


__all__ = [
    "CocoloopConfig",
    "load_cocoloop_config",
    "search_store_skills",
    "get_skill_detail_by_slug",
]
