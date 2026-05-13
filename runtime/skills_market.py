from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from runtime.tools.skills.clawhub_client import get_skill_detail, search_skills
from runtime.tools.skills.cocoloop_client import get_skill_detail_by_slug as cocoloop_get_skill_detail
from runtime.tools.skills.cocoloop_client import search_store_skills as cocoloop_search_skills


def normalize_skill_market_provider_setting(raw: str | None) -> str:
    """Tenant setting value for ``AIA_SKILL_MARKET_PROVIDER``: ``clawhub`` or ``cocoloop``."""
    p = str(raw or "").strip().lower()
    if p in {"cocoloop", "cocoloop-cn", "cocoloop_cn"}:
        return "cocoloop"
    return "clawhub"


class SkillMarketAdapter(Protocol):
    provider: str

    def search(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]: ...

    def detail(self, slug: str) -> dict[str, Any]: ...

    def resolve_archive_url(self, *, slug: str, version: str | None = None) -> tuple[str, str]:
        """Return (archive_url, resolved_version)."""


@dataclass(frozen=True)
class ClawHubMarketAdapter:
    provider: str = "clawhub"

    def search(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        return search_skills(query, limit=limit)

    def detail(self, slug: str) -> dict[str, Any]:
        return get_skill_detail(slug)

    def resolve_archive_url(self, *, slug: str, version: str | None = None) -> tuple[str, str]:
        detail = self.detail(slug)
        requested = str(version or "").strip()
        if requested:
            for row in detail.get("versions") or []:
                if not isinstance(row, dict):
                    continue
                if str(row.get("version") or "").strip() != requested:
                    continue
                return str(row.get("archiveUrl") or "").strip(), requested
            return "", requested
        latest = str(detail.get("latestVersion") or "").strip()
        return str(detail.get("archiveUrl") or "").strip(), latest


@dataclass(frozen=True)
class CocoloopMarketAdapter:
    provider: str = "cocoloop"

    def search(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        return cocoloop_search_skills(query, limit=limit)

    def detail(self, slug: str) -> dict[str, Any]:
        return cocoloop_get_skill_detail(slug)

    def resolve_archive_url(self, *, slug: str, version: str | None = None) -> tuple[str, str]:
        detail = self.detail(slug)
        requested = str(version or "").strip().lstrip("vV")
        if requested:
            for row in detail.get("versions") or []:
                if not isinstance(row, dict):
                    continue
                ver = str(row.get("version") or "").strip().lstrip("vV")
                if ver != requested:
                    continue
                return str(row.get("archiveUrl") or "").strip(), str(row.get("version") or requested)
        latest = str(detail.get("latestVersion") or "").strip()
        return str(detail.get("archiveUrl") or "").strip(), latest


def get_market_adapter(provider: str | None) -> SkillMarketAdapter:
    p = normalize_skill_market_provider_setting(provider)
    if p in {"clawhub", "openclaw"}:
        return ClawHubMarketAdapter(provider="clawhub")
    if p in {"cocoloop", "cocoloop-cn", "cocoloop_cn"}:
        return CocoloopMarketAdapter(provider="cocoloop")
    raise ValueError(f"unsupported_market_provider:{p}")


__all__ = [
    "SkillMarketAdapter",
    "ClawHubMarketAdapter",
    "CocoloopMarketAdapter",
    "get_market_adapter",
    "normalize_skill_market_provider_setting",
]

