from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys

from oclaw.gateway.python_extensions_loader import build_python_extensions_registry
from oclaw.gateway.server_plugins import load_gateway_plugins
from oclaw.tools.catalog import materialize_tool_specs


def _load_memory_wiki_api_module():
    p = Path("d:/project/chatgpt/oclaw/extensions/memory-wiki/api.py")
    module_name = "test_memory_wiki_api"
    spec = importlib.util.spec_from_file_location(module_name, str(p))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_memory_wiki_tool_handlers_basic_flow(tmp_path: Path) -> None:
    mod = _load_memory_wiki_api_module()
    wiki_root = tmp_path / "wiki"

    class _Api:
        plugin_config = {"wiki_root": str(wiki_root)}

    specs = {x["name"]: x for x in mod.build_wiki_tool_specs(_Api())}
    assert {"wiki_status", "wiki_lint", "wiki_apply", "wiki_search", "wiki_get"} <= set(specs.keys())

    out_write = specs["wiki_apply"]["handler"]({"action": "write", "path": "notes/a.md", "content": "# A\n\nhello"})
    assert out_write.get("ok") is True

    out_get = specs["wiki_get"]["handler"]({"path": "notes/a.md"})
    assert out_get.get("ok") is True
    assert "hello" in str(out_get.get("content") or "")

    out_search = specs["wiki_search"]["handler"]({"query": "hello"})
    assert out_search.get("ok") is True
    assert len(out_search.get("hits") or []) >= 1

    out_lint = specs["wiki_lint"]["handler"]({})
    assert out_lint.get("ok") is True

    out_status = specs["wiki_status"]["handler"]({})
    assert out_status.get("ok") is True
    assert int(out_status.get("file_count") or 0) >= 1


def test_memory_wiki_plugin_registry_and_catalog_wiring(tmp_path: Path, monkeypatch) -> None:
    wiki_root = tmp_path / "wiki"
    app_cfg = {"plugins": {"entries": {"memory-wiki": {"wiki_root": str(wiki_root)}}}}
    reg = build_python_extensions_registry(
        app_config=app_cfg,
        workspace_dir="d:/project/chatgpt",
        only_plugin_ids=["memory-wiki"],
    )
    tools = [x for x in (reg.get("tools") or []) if isinstance(x, dict)]
    names = {str(t.get("name") or "") for t in tools}
    assert {"wiki_status", "wiki_lint", "wiki_apply", "wiki_search", "wiki_get"} <= names
    assert all(callable(t.get("handler")) for t in tools if str(t.get("name") or "").startswith("wiki_"))

    monkeypatch.setenv("AIA_PLUGIN_TOOLS_ENABLED", "1")
    monkeypatch.setenv("AIA_PLUGIN_TOOL_IDS", "memory-wiki")
    specs = materialize_tool_specs()
    spec_names = {s.name for s in specs}
    assert "wiki_status" in spec_names


def test_server_plugins_can_load_memory_wiki_only() -> None:
    cfg = {
        "plugins": {
            "slots": {"memory": "memory-wiki"},
        }
    }
    got = load_gateway_plugins(
        cfg=cfg,
        workspace_dir="d:/project/chatgpt",
        log={},
        core_gateway_handlers={},
        base_methods=[],
        plugin_ids=["memory-wiki"],
    )
    plugin_ids = {str(x.get("id") or "") for x in (got.plugin_registry.get("plugins") or [])}
    assert "memory-wiki" in plugin_ids

