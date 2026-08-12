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


def test_ops_role_system_has_answer_shape_examples() -> None:
    zh = build_role_system_context("ops", lang="zh")
    en = build_role_system_context("ops", lang="en")
    for text in (zh, en):
        assert "Result:" in text
        assert "Evidence:" in text
        assert "Good vs bad" in text or "好例 vs 坏例" in text
        assert "Let me check the fiber cut" in text
        assert "Fiber cut / LOS — network-wide" in text
        assert "incomplete answer" in text.lower() or "不合格" in text
