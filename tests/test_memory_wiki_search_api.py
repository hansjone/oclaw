from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

from oclaw.platform.config.paths import PROJECT_ROOT


def _wiki_search_handler(tmp_path: Path):
    api_path = (PROJECT_ROOT / "runtime" / "extensions" / "memory-wiki" / "api.py").resolve()
    spec = importlib.util.spec_from_file_location("memory_wiki_api_test", str(api_path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[assignment]
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)
    rows = mod.build_wiki_tool_specs(
        SimpleNamespace(plugin_config={"wiki_root": str(wiki_root), "max_search_results": 10, "max_get_lines": 200})
    )
    for r in rows:
        if str(r.get("name") or "") == "wiki_search":
            return wiki_root, r["handler"]
    raise AssertionError("wiki_search handler missing")


def test_wiki_search_returns_context_and_pagination_metadata(tmp_path: Path) -> None:
    wiki_root, handler = _wiki_search_handler(tmp_path)
    p = wiki_root / "users" / "identity.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "\n".join(
            [
                "# Identity",
                "creator is Oliver",
                "project owner is Oliver",
                "session profile line",
            ]
        ),
        encoding="utf-8",
    )

    out = handler({"query": "Oliver", "limit": 1, "offset": 0, "context_lines": 1})

    assert out.get("ok") is True
    assert out.get("query") == "Oliver"
    assert out.get("truncated") is True
    assert out.get("next_offset") == 1
    hits = out.get("hits") or []
    assert len(hits) == 1
    hit = hits[0]
    assert hit.get("path") == "users/identity.md"
    assert isinstance(hit.get("before"), list)
    assert isinstance(hit.get("after"), list)
    assert "matched_query" in hit


def test_wiki_search_offset_paginates_deterministically(tmp_path: Path) -> None:
    wiki_root, handler = _wiki_search_handler(tmp_path)
    p = wiki_root / "identity.md"
    p.write_text("Oliver one\nOliver two\nOliver three\n", encoding="utf-8")

    page1 = handler({"query": "Oliver", "limit": 2, "offset": 0})
    page2 = handler({"query": "Oliver", "limit": 2, "offset": 2})

    hits1 = page1.get("hits") or []
    hits2 = page2.get("hits") or []
    assert [h.get("line") for h in hits1] == [1, 2]
    assert [h.get("line") for h in hits2] == [3]
    assert page2.get("truncated") is False
    assert page2.get("next_offset") is None


def test_wiki_search_expand_query_reports_attempted_queries(tmp_path: Path) -> None:
    wiki_root, handler = _wiki_search_handler(tmp_path)
    p = wiki_root / "users" / "identity.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("项目所有者：Oliver\n", encoding="utf-8")

    out = handler({"query": "用户", "expand_query": True, "max_rounds": 3, "limit": 5})
    assert out.get("ok") is True
    attempted = out.get("queries_attempted") or []
    assert attempted
    assert attempted[0] == "用户"
    assert len(attempted) <= 3
    hits = out.get("hits") or []
    assert hits
    assert any(h.get("matched_query") != "用户" for h in hits)


def test_wiki_search_keeps_backward_compatible_keys(tmp_path: Path) -> None:
    wiki_root, handler = _wiki_search_handler(tmp_path)
    (wiki_root / "a.md").write_text("hello\n", encoding="utf-8")
    out = handler({"query": "hello"})
    assert {"ok", "query", "hits", "truncated"}.issubset(set(out.keys()))

