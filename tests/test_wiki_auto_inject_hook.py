from __future__ import annotations

import importlib.util
import types
from pathlib import Path


def _load_handler_module():
    p = Path("d:/project/chatgpt/oclaw/hooks/bundled/wiki-auto-inject/handler.py").resolve()
    spec = importlib.util.spec_from_file_location("wiki_auto_inject_handler_test", str(p))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[assignment]
    return mod


def test_collect_snippets_top_k_and_relevance(tmp_path: Path) -> None:
    mod = _load_handler_module()
    wiki = tmp_path / "wiki"
    wiki.mkdir(parents=True, exist_ok=True)
    (wiki / "a.md").write_text(
        "# A\nRouter VLAN troubleshooting guide\nA guide for vlan and trunk setup.\n",
        encoding="utf-8",
    )
    (wiki / "b.md").write_text(
        "# B\nUnrelated note.\nAnother line.\n",
        encoding="utf-8",
    )
    (wiki / "c.md").write_text(
        "# C\nVLAN tagging tips for router.\nrouter vlan quick checklist.\n",
        encoding="utf-8",
    )

    text, meta = mod._collect_snippets(wiki, "router vlan", max_chars=500, top_k=2)
    lines = [x for x in text.splitlines() if x.strip()]
    assert len(lines) == 2
    assert len(meta) == 2
    assert "a.md" in text or "c.md" in text
    assert "b.md" not in text


def test_handle_sets_prepend_system_context(monkeypatch, tmp_path: Path) -> None:
    mod = _load_handler_module()
    wiki = tmp_path / "wiki"
    wiki.mkdir(parents=True, exist_ok=True)
    (wiki / "ops.md").write_text("Router vlan baseline\n", encoding="utf-8")

    monkeypatch.setattr(
        mod,
        "_load_config",
        lambda: {
            "plugins": {
                "entries": {
                    "memory-wiki": {
                        "wiki_root": str(wiki),
                        "auto": {"enabled": True, "inject": {"max_chars": 800, "top_k": 3}},
                    }
                }
            }
        },
    )

    event = types.SimpleNamespace(
        type="llm",
        action="before_prompt_build",
        context={"userText": "router vlan", "prepend_system_context": ""},
    )
    mod.handle(event)
    out = str(event.context.get("prepend_system_context") or "")
    meta = event.context.get("wiki_inject_meta") or {}
    assert "Wiki Context (Auto Inject)" in out
    assert "ops.md" in out
    assert bool(meta.get("enabled")) is True
    assert isinstance(meta.get("hits"), list)


def test_handle_ultra_saver_skips_short_query(monkeypatch, tmp_path: Path) -> None:
    mod = _load_handler_module()
    wiki = tmp_path / "wiki"
    wiki.mkdir(parents=True, exist_ok=True)
    (wiki / "ops.md").write_text("router vlan baseline\n", encoding="utf-8")
    monkeypatch.setattr(
        mod,
        "_load_config",
        lambda: {
            "plugins": {
                "entries": {
                    "memory-wiki": {
                        "wiki_root": str(wiki),
                        "auto": {
                            "enabled": True,
                            "inject": {
                                "max_chars": 800,
                                "top_k": 3,
                                "ultra_saver_enabled": True,
                                "min_query_chars": 20,
                                "require_topic_hint": True,
                            },
                        },
                    }
                }
            }
        },
    )
    event = types.SimpleNamespace(
        type="llm",
        action="before_prompt_build",
        context={"userText": "hi", "prepend_system_context": ""},
    )
    mod.handle(event)
    assert str(event.context.get("prepend_system_context") or "") == ""
    meta = event.context.get("wiki_inject_meta") or {}
    assert bool(meta.get("enabled")) is False
    assert str(meta.get("skip_reason") or "") == "short_query"


def test_handle_ultra_saver_requires_topic_hint(monkeypatch, tmp_path: Path) -> None:
    mod = _load_handler_module()
    wiki = tmp_path / "wiki"
    wiki.mkdir(parents=True, exist_ok=True)
    (wiki / "ops.md").write_text("router vlan baseline\n", encoding="utf-8")
    monkeypatch.setattr(
        mod,
        "_load_config",
        lambda: {
            "plugins": {
                "entries": {
                    "memory-wiki": {
                        "wiki_root": str(wiki),
                        "auto": {
                            "enabled": True,
                            "inject": {
                                "max_chars": 800,
                                "top_k": 3,
                                "ultra_saver_enabled": True,
                                "min_query_chars": 5,
                                "require_topic_hint": True,
                            },
                        },
                    }
                }
            }
        },
    )
    event = types.SimpleNamespace(
        type="llm",
        action="before_prompt_build",
        context={"userText": "summarize this message", "prepend_system_context": ""},
    )
    mod.handle(event)
    assert str(event.context.get("prepend_system_context") or "") == ""
    meta = event.context.get("wiki_inject_meta") or {}
    assert bool(meta.get("enabled")) is False
    assert str(meta.get("skip_reason") or "") == "no_topic_hint"


def test_handle_store_only_mode_skips_injection(monkeypatch, tmp_path: Path) -> None:
    mod = _load_handler_module()
    wiki = tmp_path / "wiki"
    wiki.mkdir(parents=True, exist_ok=True)
    (wiki / "ops.md").write_text("router vlan baseline\n", encoding="utf-8")
    monkeypatch.setattr(
        mod,
        "_load_config",
        lambda: {
            "plugins": {
                "entries": {
                    "memory-wiki": {
                        "wiki_root": str(wiki),
                        "auto": {"enabled": True, "inject": {"max_chars": 800, "top_k": 3}},
                    }
                }
            }
        },
    )
    event = types.SimpleNamespace(
        type="llm",
        action="before_prompt_build",
        context={"userText": "router vlan", "memory_mode": "store_only", "prepend_system_context": ""},
    )
    mod.handle(event)
    assert str(event.context.get("prepend_system_context") or "") == ""
    meta = event.context.get("wiki_inject_meta") or {}
    assert bool(meta.get("enabled")) is False
    assert str(meta.get("skip_reason") or "") == "memory_mode_store_only"


def test_collect_snippets_prioritizes_merged_turns(tmp_path: Path) -> None:
    mod = _load_handler_module()
    wiki = tmp_path / "wiki"
    (wiki / "inbox").mkdir(parents=True, exist_ok=True)
    (wiki / ".oclaw").mkdir(parents=True, exist_ok=True)
    (wiki / "inbox" / "merged-turns.md").write_text("router vlan merged signal\n", encoding="utf-8")
    (wiki / "normal.md").write_text("router vlan normal note\n", encoding="utf-8")
    (wiki / ".oclaw" / "index.json").write_text(
        '{"files":["normal.md","inbox/merged-turns.md"]}',
        encoding="utf-8",
    )
    text, meta = mod._collect_snippets(wiki, "router vlan", max_chars=800, top_k=1)
    assert "inbox/merged-turns.md" in text
    assert meta and str(meta[0].get("source") or "").endswith("merged-turns.md")


def test_collect_snippets_prefers_topic_page_before_merged(tmp_path: Path) -> None:
    mod = _load_handler_module()
    wiki = tmp_path / "wiki"
    (wiki / "inbox").mkdir(parents=True, exist_ok=True)
    (wiki / "topics").mkdir(parents=True, exist_ok=True)
    (wiki / ".oclaw").mkdir(parents=True, exist_ok=True)
    (wiki / "topics" / "auto-network.md").write_text("router vlan topic page\n", encoding="utf-8")
    (wiki / "inbox" / "merged-turns.md").write_text("router vlan merged page\n", encoding="utf-8")
    (wiki / ".oclaw" / "topic-index.json").write_text(
        '{"topics":{"network":{"path":"topics/auto-network.md","merged_count":3}}}',
        encoding="utf-8",
    )
    text, meta = mod._collect_snippets(wiki, "router vlan", max_chars=900, top_k=1)
    assert "topics/auto-network.md" in text
    assert meta and str(meta[0].get("source") or "").endswith("topics/auto-network.md")


def test_collect_snippets_honors_configured_topic_rules(tmp_path: Path) -> None:
    mod = _load_handler_module()
    wiki = tmp_path / "wiki"
    (wiki / "topics").mkdir(parents=True, exist_ok=True)
    (wiki / ".oclaw").mkdir(parents=True, exist_ok=True)
    (wiki / "topics" / "auto-iac.md").write_text("terraform module baseline\n", encoding="utf-8")
    (wiki / ".oclaw" / "topic-index.json").write_text(
        '{"topics":{"iac":{"path":"topics/auto-iac.md","merged_count":1}}}',
        encoding="utf-8",
    )
    rules = [{"topic": "iac", "keywords": ["terraform", "ansible"]}]
    text, meta = mod._collect_snippets(
        wiki,
        "terraform drift",
        max_chars=800,
        top_k=1,
        topic_rules=rules,
    )
    assert "topics/auto-iac.md" in text
    assert meta and str(meta[0].get("source") or "").endswith("topics/auto-iac.md")
