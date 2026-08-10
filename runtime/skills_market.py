from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from runtime.tools.skills.clawhub_client import get_skill_detail, search_skills


def normalize_skill_market_provider_setting(raw: str | None) -> str:
    """Tenant setting value for ``AIA_SKILL_MARKET_PROVIDER`` (clawhub only)."""
    del raw
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


def get_market_adapter(provider: str | None) -> SkillMarketAdapter:
    del provider
    return ClawHubMarketAdapter()


__all__ = [
    "ClawHubMarketAdapter",
    "SkillMarketAdapter",
    "get_market_adapter",
    "normalize_skill_market_provider_setting",
]
