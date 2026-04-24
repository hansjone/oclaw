from __future__ import annotations

from oclaw.runtime.skills_prompt import format_skills_for_prompt


def test_format_skills_for_prompt_xml_shape() -> None:
    out = format_skills_for_prompt(
        [("demo", "desc", "/tmp/skills/demo/SKILL.md")],
        max_chars=50_000,
    )
    assert "<available_skills>" in out
    assert "</available_skills>" in out
    assert "<name>demo</name>" in out
    assert "read_file" in out


def test_format_skills_for_prompt_truncates_by_budget() -> None:
    entries = [(f"s{i}", "d", f"/p/{i}") for i in range(30)]
    out = format_skills_for_prompt(entries, max_chars=800)
    assert len(out) <= 800
