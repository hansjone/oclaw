from __future__ import annotations

from pathlib import Path

from oclaw.platform.config.paths import PROJECT_ROOT
from oclaw.runtime.tools.experts.memory.wiki_tools import (
    memory_wiki_apply_tool,
    memory_wiki_get_tool,
    memory_wiki_lint_tool,
    memory_wiki_search_tool,
    memory_wiki_status_tool,
)


def test_memory_wiki_tools_handlers_load_without_dataclass_module_error() -> None:
    status = memory_wiki_status_tool().handler({})
    assert isinstance(status, dict)
    assert "AttributeError" not in str(status.get("error", ""))
    assert "__dict__" not in str(status.get("error", ""))

    search = memory_wiki_search_tool().handler({"query": "test"})
    assert isinstance(search, dict)
    assert "AttributeError" not in str(search.get("error", ""))
    assert "__dict__" not in str(search.get("error", ""))

    get_res = memory_wiki_get_tool().handler({"path": "improvement/learnings.md"})
    assert isinstance(get_res, dict)
    assert "AttributeError" not in str(get_res.get("error", ""))
    assert "__dict__" not in str(get_res.get("error", ""))

    lint = memory_wiki_lint_tool().handler({})
    assert isinstance(lint, dict)
    assert "AttributeError" not in str(lint.get("error", ""))
    assert "__dict__" not in str(lint.get("error", ""))

    apply_res = memory_wiki_apply_tool().handler({"action": "delete", "path": "improvement/_nonexistent_test_.md"})
    assert isinstance(apply_res, dict)
    assert "AttributeError" not in str(apply_res.get("error", ""))
    assert "__dict__" not in str(apply_res.get("error", ""))


def test_memory_wiki_tools_accept_relative_prefixed_and_absolute_paths() -> None:
    wiki_root = (PROJECT_ROOT / "data" / "wiki").resolve()
    rel = Path("improvement") / "learnings.md"
    abs_path = str((wiki_root / rel).resolve())
    prefixed_rel = str(Path("data/wiki") / rel)

    # Relative
    r1 = memory_wiki_get_tool().handler({"path": str(rel)})
    assert r1.get("ok") is True

    # Prefixed by "data/wiki/..."
    r2 = memory_wiki_get_tool().handler({"path": prefixed_rel})
    assert r2.get("ok") is True

    # Absolute path under wiki_root
    r3 = memory_wiki_get_tool().handler({"path": abs_path})
    assert r3.get("ok") is True

