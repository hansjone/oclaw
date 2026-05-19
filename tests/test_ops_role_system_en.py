from __future__ import annotations

from pathlib import Path

from runtime.agent_context.loader import build_role_system_context


def test_ops_role_system_en_prefers_localized_file() -> None:
    zh = build_role_system_context("ops", lang="zh")
    en = build_role_system_context("ops", lang="en")
    assert "运维专家" in zh or "oclaw智能运维" in zh
    assert "ops specialist" in en.lower()
    assert "reply entirely in the user's language" in en.lower()
    assert "运维专家" not in en
