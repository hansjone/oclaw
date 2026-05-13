from __future__ import annotations

from pathlib import Path

from runtime.tools.public.skills_install_tool import skill_market_install_tool, skill_registry_install_tool


def test_skill_registry_install_tool_forces_workspace_root(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, str] = {}

    def _mock_default_root() -> Path:
        return tmp_path / "skills"

    def _mock_install(**kwargs):  # noqa: ANN003
        captured["skills_root"] = str(kwargs.get("skills_root") or "")

        class _Out:
            ok = True
            name = "demo"
            target_dir = str((tmp_path / "skills" / "_workspace" / "demo").resolve())
            detail = "installed"
            error_code = "ok"
            retryable = False

        return _Out()

    monkeypatch.setattr("runtime.tools.public.skills_install_tool.default_skills_root", _mock_default_root)
    monkeypatch.setattr("runtime.tools.public.skills_install_tool.install_skill_from_registry_archive", _mock_install)
    tool = skill_registry_install_tool()
    result = tool.handler({"archive_url": "https://example.com/demo.zip"})
    assert bool(result.get("ok")) is True
    assert captured["skills_root"].replace("\\", "/").endswith("/skills/_workspace")


def test_skill_market_install_tool_provider_arg_overrides_setting(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, str] = {}

    class _FakeStore:
        def get_setting(self, key: str) -> str:
            if key == "AIA_SKILL_MARKET_PROVIDER":
                return "clawhub"
            return ""

    class _FakeAdapter:
        def resolve_archive_url(self, *, slug: str, version: str | None = None) -> tuple[str, str]:
            captured["slug"] = slug
            captured["version"] = str(version or "")
            return "https://example.com/demo.zip", "1.0.0"

    def _mock_store() -> _FakeStore:
        return _FakeStore()

    def _mock_default_root() -> Path:
        return tmp_path / "skills"

    def _mock_get_market_adapter(provider: str):  # noqa: ANN001
        captured["provider"] = provider
        return _FakeAdapter()

    def _mock_install(**kwargs):  # noqa: ANN003
        captured["skills_root"] = str(kwargs.get("skills_root") or "")

        class _Out:
            ok = True
            name = "demo"
            target_dir = str((tmp_path / "skills" / "_workspace" / "demo").resolve())
            detail = "installed"
            error_code = "ok"
            retryable = False

        return _Out()

    monkeypatch.setattr("runtime.tools.public.skills_install_tool._store", _mock_store)
    monkeypatch.setattr("runtime.tools.public.skills_install_tool.default_skills_root", _mock_default_root)
    monkeypatch.setattr("runtime.tools.public.skills_install_tool.get_market_adapter", _mock_get_market_adapter)
    monkeypatch.setattr("runtime.tools.public.skills_install_tool.install_skill_from_registry_archive", _mock_install)

    tool = skill_market_install_tool()
    result = tool.handler({"slug": "demo", "provider": "cocoloop", "version": "latest"})
    assert bool(result.get("ok")) is True
    assert captured["provider"] == "cocoloop"
    assert captured["skills_root"].replace("\\", "/").endswith("/skills/_workspace")

