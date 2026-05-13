from __future__ import annotations

from runtime import skills_market


def test_get_market_adapter_clawhub_default() -> None:
    a = skills_market.get_market_adapter("clawhub")
    assert a.provider == "clawhub"


def test_get_market_adapter_cocoloop() -> None:
    a = skills_market.get_market_adapter("cocoloop")
    assert a.provider == "cocoloop"


def test_get_market_adapter_cocoloop_alias() -> None:
    a = skills_market.get_market_adapter("cocoloop-cn")
    assert a.provider == "cocoloop"


def test_cocoloop_resolve_archive_url(monkeypatch) -> None:
    def _fake_detail(slug: str) -> dict:  # noqa: ANN001
        return {
            "source": "cocoloop",
            "slug": slug,
            "latestVersion": "1.0.0",
            "archiveUrl": "https://dl.example/bss/skills/demo.zip",
            "versions": [{"version": "1.0.0", "archiveUrl": "https://dl.example/bss/skills/demo.zip"}],
        }

    monkeypatch.setattr("runtime.skills_market.cocoloop_get_skill_detail", _fake_detail)
    a = skills_market.CocoloopMarketAdapter()
    url, ver = a.resolve_archive_url(slug="demo", version=None)
    assert url.endswith("demo.zip")
    assert ver == "1.0.0"
