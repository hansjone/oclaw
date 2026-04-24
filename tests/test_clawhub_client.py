from __future__ import annotations

from oclaw.runtime.tools.skills import clawhub_client


def test_get_skill_detail_handles_latest_version_object(monkeypatch) -> None:
    def _fake_get_json(url, *, params=None, headers=None):  # noqa: ANN001,ARG001
        return {
            "slug": "self-improving-agent",
            "latestVersion": {"version": "3.0.16"},
            "versions": [{"version": "3.0.16"}],
        }

    monkeypatch.setattr(clawhub_client, "_safe_get_json", _fake_get_json)
    out = clawhub_client.get_skill_detail("self-improving-agent")
    assert out.get("latestVersion") == "3.0.16"
    assert "version=3.0.16" in str(out.get("archiveUrl") or "")
