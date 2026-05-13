from __future__ import annotations

from runtime.tools.catalog import materialize_tool_specs


def test_memory_tools_only_expose_canonical_names() -> None:
    specs = materialize_tool_specs(expert="memory")
    names = {str(x.name or "") for x in specs}
    assert "memory_wiki_status" in names
    assert "memory_wiki_get" in names
    assert "memory_wiki_search" in names
    assert "memory_wiki_lint" in names
    assert "memory_wiki_apply" in names
    assert all(not str(x).startswith("memory_curator_") for x in names)


def test_generalist_also_exposes_memory_wiki_tools() -> None:
    specs = materialize_tool_specs(expert="generalist")
    names = {str(x.name or "") for x in specs}
    assert "memory_wiki_status" in names
    assert "memory_wiki_get" in names
    assert "memory_wiki_search" in names
    assert "memory_wiki_lint" in names
    assert "memory_wiki_apply" in names


