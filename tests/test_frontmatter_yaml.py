from __future__ import annotations

import pytest

from runtime.prompt_templates.frontmatter import parse_frontmatter_dict, parse_markdown_document


def test_parse_yaml_frontmatter_nested_metadata() -> None:
    fm = parse_frontmatter_dict(
        "name: demo\ndescription: x\nmetadata:\n  oclaw:\n    install:\n      - id: i1\n        kind: node\n",
        source="test",
    )
    assert fm.get("name") == "demo"
    md = fm.get("metadata")
    assert isinstance(md, dict)
    assert isinstance(md.get("oclaw"), dict)


def test_parse_markdown_document_roundtrip() -> None:
    raw = "---\ntitle: t\nsummary: s\nread_when: now\n---\n\n# Body\nhello"
    meta, body = parse_markdown_document(raw, source="test")
    assert meta.get("title") == "t"
    assert "hello" in body


def test_strict_yaml_invalid_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIA_PROMPT_FRONTMATTER_STRICT", "1")
    with pytest.raises(ValueError):
        parse_frontmatter_dict("*invalid\nfoo: bar", source="test")
