from __future__ import annotations

import asyncio
import importlib.util
import shutil

import pytest
from pathlib import Path

from oclaw.runtime.hooks.internal_hooks import clear_hooks, create_hook_event, trigger_hook
from oclaw.runtime.hooks.loader import load_internal_hooks


def _load_module(module_path: Path):
    spec = importlib.util.spec_from_file_location(f"testmod_{module_path.stem}", str(module_path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_load_internal_hooks_does_not_duplicate_handlers_on_reload(tmp_path: Path) -> None:
    hooks_root = tmp_path / "hooks"
    demo = hooks_root / "demo"
    demo.mkdir(parents=True)
    (demo / "HOOK.md").write_text(
        "---\n"
        "name: demo\n"
        "description: demo hook\n"
        "metadata:\n"
        "  oclaw:\n"
        "    events: [\"command:new\"]\n"
        "---\n",
        encoding="utf-8",
    )
    (demo / "handler.py").write_text(
        "def handle(event):\n"
        "    ctx = event.context\n"
        "    ctx['calls'] = int(ctx.get('calls') or 0) + 1\n",
        encoding="utf-8",
    )

    cfg: dict = {"hooks": {"internal": {"enabled": True}}}
    clear_hooks()
    assert load_internal_hooks(cfg, workspace_dir=str(tmp_path), bundled_hooks_dir=str(hooks_root)) == 1
    assert load_internal_hooks(cfg, workspace_dir=str(tmp_path), bundled_hooks_dir=str(hooks_root)) == 1

    ctx: dict = {"calls": 0}

    async def _run() -> None:
        ev = create_hook_event("command", "new", "agent:main:main", context=ctx)
        await trigger_hook(ev)

    asyncio.run(_run())
    assert ctx["calls"] == 1


def test_bootstrap_extra_files_only_injects_allowed_basenames(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    ws.mkdir(parents=True)
    (ws / "AGENTS.md").write_text("# agents\n", encoding="utf-8")
    (ws / "README.md").write_text("# readme\n", encoding="utf-8")

    handler_path = (
        Path(__file__).resolve().parents[1]
        / "runtime"
        / "hooks"
        / "bundled"
        / "bootstrap-extra-files"
        / "handler.py"
    )
    mod = _load_module(handler_path)
    event = create_hook_event(
        "agent",
        "bootstrap",
        "agent:main:main",
        context={
            "workspaceDir": str(ws),
            "bootstrapFiles": [],
            "cfg": {
                "hooks": {
                    "internal": {
                        "entries": {
                            "bootstrap-extra-files": {"enabled": True, "paths": ["**/*.md"]},
                        }
                    }
                }
            },
        },
    )
    mod.handle(event)
    files = event.context.get("bootstrapFiles") or []
    assert isinstance(files, list)
    names = {str((item or {}).get("name")) for item in files if isinstance(item, dict)}
    assert "AGENTS.md" in names
    assert "README.md" not in names


def test_workspace_hook_discovery_supports_package_manifest_hooks(tmp_path: Path) -> None:
    from oclaw.runtime.hooks.workspace import load_hook_entries_from_dir
    from oclaw.runtime.hooks.hook_types import ensure_entry_dict

    hooks_root = tmp_path / "hooks"
    pkg = hooks_root / "pack-a"
    declared = pkg / "nested" / "demo-hook"
    declared.mkdir(parents=True)
    (pkg / "package.json").write_text(
        "{"
        "\"openclaw\": {"
        "\"hooks\": [\"nested/demo-hook\", \"../outside\"]"
        "}"
        "}",
        encoding="utf-8",
    )
    (declared / "HOOK.md").write_text(
        "---\n"
        "name: nested-demo\n"
        "description: nested hook\n"
        "enabled: true\n"
        "metadata:\n"
        "  oclaw:\n"
        "    events: [\"command:new\"]\n"
        "---\n",
        encoding="utf-8",
    )
    (declared / "handler.py").write_text("def handle(event):\n    return None\n", encoding="utf-8")

    entries = load_hook_entries_from_dir(str(hooks_root), source="oclaw-managed")
    assert len(entries) == 1
    row = ensure_entry_dict(entries[0])
    hook = row["hook"]
    assert hook["name"] == "nested-demo"
    assert hook["source"] == "oclaw-managed"
    assert row.get("invocation", {}).get("enabled") is True


def test_hook_frontmatter_metadata_normalization() -> None:
    from oclaw.runtime.hooks.frontmatter import parse_frontmatter, resolve_oclaw_metadata

    content = (
        "---\n"
        "name: demo\n"
        "description: demo\n"
        "metadata:\n"
        "  oclaw:\n"
        "    always: true\n"
        "    hookKey: demo-key\n"
        "    export: custom_export\n"
        "    events: [\"command:new\", \"command:reset\", 123]\n"
        "    os: [\"darwin\", \"linux\", \"\"]\n"
        "    requires:\n"
        "      bins: [\"git\", \"\"]\n"
        "      anyBins: [\"python\", \"node\"]\n"
        "      env: [\"OPENAI_API_KEY\"]\n"
        "      config: [\"workspace.dir\"]\n"
        "    install:\n"
        "      - id: bund\n"
        "        kind: bundled\n"
        "      - id: bad\n"
        "        kind: unknown\n"
        "---\n"
    )
    fm = parse_frontmatter(content).frontmatter
    md = resolve_oclaw_metadata(fm)
    assert isinstance(md, dict)
    assert md.get("always") is True
    assert md.get("hookKey") == "demo-key"
    assert md.get("export") == "custom_export"
    assert md.get("events") == ["command:new", "command:reset"]
    assert md.get("os") == ["darwin", "linux"]
    assert md.get("requires", {}).get("bins") == ["git"]
    assert md.get("requires", {}).get("anyBins") == ["python", "node"]
    assert md.get("requires", {}).get("env") == ["OPENAI_API_KEY"]
    assert md.get("requires", {}).get("config") == ["workspace.dir"]
    assert md.get("install") == [{"kind": "bundled", "id": "bund"}]


def test_hook_invocation_policy_disables_loading_even_when_config_enabled(tmp_path: Path) -> None:
    from oclaw.runtime.hooks.loader import load_internal_hooks
    from oclaw.runtime.hooks.internal_hooks import clear_hooks, create_hook_event, trigger_hook

    hooks_root = tmp_path / "hooks"
    demo = hooks_root / "demo"
    demo.mkdir(parents=True)
    (demo / "HOOK.md").write_text(
        "---\n"
        "name: demo\n"
        "description: demo hook\n"
        "enabled: false\n"
        "metadata:\n"
        "  oclaw:\n"
        "    events: [\"command:new\"]\n"
        "---\n",
        encoding="utf-8",
    )
    (demo / "handler.py").write_text(
        "def handle(event):\n"
        "    event.context['calls'] = int(event.context.get('calls') or 0) + 1\n",
        encoding="utf-8",
    )

    cfg = {"hooks": {"internal": {"enabled": True, "entries": {"demo": {"enabled": True}}}}}
    clear_hooks()
    assert load_internal_hooks(cfg, workspace_dir=str(tmp_path), bundled_hooks_dir=str(hooks_root)) == 0

    ctx: dict = {"calls": 0}

    async def _run() -> None:
        ev = create_hook_event("command", "new", "agent:main:main", context=ctx)
        await trigger_hook(ev)

    asyncio.run(_run())
    assert ctx["calls"] == 0


def test_should_include_hook_respects_requires_env_and_config(monkeypatch) -> None:
    from oclaw.runtime.hooks.config import should_include_hook
    from oclaw.runtime.hooks.hook_types import ensure_hook_entry

    entry_raw = {
        "hook": {"name": "demo", "source": "oclaw-managed"},
        "metadata": {
            "events": ["command:new"],
            "requires": {"env": ["DEMO_TOKEN"], "config": ["workspace.dir"]},
        },
        "invocation": {"enabled": True},
    }
    entry = ensure_hook_entry(entry_raw)
    cfg = {"hooks": {"internal": {"entries": {"demo": {"enabled": True}}}}}

    monkeypatch.delenv("DEMO_TOKEN", raising=False)
    assert should_include_hook(entry=entry, config=cfg) is False

    monkeypatch.setenv("DEMO_TOKEN", "x")
    assert should_include_hook(entry=entry, config=cfg) is True


def test_should_include_hook_respects_os_allowlist() -> None:
    from oclaw.runtime.hooks.config import should_include_hook
    from oclaw.runtime.hooks.hook_types import ensure_hook_entry

    entry = ensure_hook_entry({
        "hook": {"name": "demo", "source": "oclaw-managed"},
        "metadata": {"events": ["command:new"], "os": ["amigaos"]},
        "invocation": {"enabled": True},
    })
    cfg = {"hooks": {"internal": {"entries": {"demo": {"enabled": True}}}}}
    assert should_include_hook(entry=entry, config=cfg) is False


def test_should_include_hook_requires_bins_all_must_exist() -> None:
    from oclaw.runtime.hooks.config import should_include_hook
    from oclaw.runtime.hooks.hook_types import ensure_hook_entry

    entry = ensure_hook_entry({
        "hook": {"name": "demo", "source": "oclaw-managed"},
        "metadata": {"events": ["command:new"], "requires": {"bins": ["definitely_missing_binary_123"]}},
        "invocation": {"enabled": True},
    })
    cfg = {"hooks": {"internal": {"entries": {"demo": {"enabled": True}}}}}
    assert should_include_hook(entry=entry, config=cfg) is False


def test_should_include_hook_requires_any_bins_at_least_one() -> None:
    from oclaw.runtime.hooks.config import should_include_hook
    from oclaw.runtime.hooks.hook_types import ensure_hook_entry

    entry_ok = ensure_hook_entry({
        "hook": {"name": "demo", "source": "oclaw-managed"},
        "metadata": {"events": ["command:new"], "requires": {"anyBins": ["python"]}},
        "invocation": {"enabled": True},
    })
    entry_fail = ensure_hook_entry({
        "hook": {"name": "demo", "source": "oclaw-managed"},
        "metadata": {"events": ["command:new"], "requires": {"anyBins": ["missing_bin_abc", "missing_bin_xyz"]}},
        "invocation": {"enabled": True},
    })
    cfg = {"hooks": {"internal": {"entries": {"demo": {"enabled": True}}}}}
    assert should_include_hook(entry=entry_ok, config=cfg) is True
    assert should_include_hook(entry=entry_fail, config=cfg) is False


def test_should_include_hook_requires_config_path_truthy() -> None:
    from oclaw.runtime.hooks.config import should_include_hook
    from oclaw.runtime.hooks.hook_types import ensure_hook_entry

    entry = ensure_hook_entry({
        "hook": {"name": "demo", "source": "oclaw-managed"},
        "metadata": {"events": ["command:new"], "requires": {"config": ["workspace.dir"]}},
        "invocation": {"enabled": True},
    })
    cfg_false = {"workspace": {"dir": ""}, "hooks": {"internal": {"entries": {"demo": {"enabled": True}}}}}
    cfg_true = {"workspace": {"dir": "/tmp/ws"}, "hooks": {"internal": {"entries": {"demo": {"enabled": True}}}}}
    assert should_include_hook(entry=entry, config=cfg_false) is False
    assert should_include_hook(entry=entry, config=cfg_true) is True


def test_parse_hook_manifest_core_roundtrip() -> None:
    from oclaw.runtime.hooks.hook_manifest_core import parse_hook_manifest

    fm = {
        "name": "demo-hook",
        "description": "demo description",
        "enabled": False,
        "metadata": {
            "oclaw": {
                "events": ["command:new", "command:reset", ""],
                "always": True,
                "hookKey": "demo-key",
                "requires": {"bins": ["git"], "anyBins": ["python"], "env": ["X_TOKEN"]},
                "install": [{"kind": "bundled", "id": "bundled"}],
            }
        },
    }
    parsed = parse_hook_manifest(frontmatter=fm, default_name="fallback")
    assert parsed.name == "demo-hook"
    assert parsed.description == "demo description"
    assert parsed.invocation_enabled is False
    md = parsed.metadata.as_dict()
    assert md.get("events") == ["command:new", "command:reset"]
    assert md.get("always") is True
    assert md.get("hookKey") == "demo-key"
    assert md.get("requires", {}).get("bins") == ["git"]
    assert md.get("requires", {}).get("anyBins") == ["python"]
    assert md.get("requires", {}).get("env") == ["X_TOKEN"]
    assert md.get("install") == [{"kind": "bundled", "id": "bundled"}]


def test_compat_wrappers_accept_dict_entries() -> None:
    from oclaw.runtime.hooks.config import should_include_hook_compat
    from oclaw.runtime.hooks.policy import resolve_hook_entries_compat

    entry = {
        "hook": {"name": "demo", "description": "", "source": "oclaw-managed", "filePath": "", "baseDir": "", "handlerPath": ""},
        "metadata": {"events": ["command:new"]},
        "invocation": {"enabled": True},
        "frontmatter": {},
    }
    cfg = {"hooks": {"internal": {"entries": {"demo": {"enabled": True}}}}}
    assert should_include_hook_compat(entry=entry, config=cfg) is True
    out = resolve_hook_entries_compat([entry])
    assert isinstance(out, list) and len(out) == 1
    assert out[0].get("hook", {}).get("name") == "demo"


def test_ensure_hook_entry_normalizes_unknown_source() -> None:
    from oclaw.runtime.hooks.hook_types import ensure_hook_entry

    row = {"hook": {"name": "x", "source": "unknown-source"}}
    entry = ensure_hook_entry(row)
    assert entry.hook.source == "oclaw-managed"


def test_should_include_hook_remote_eligibility_overrides_local_runtime() -> None:
    from oclaw.runtime.hooks.config import should_include_hook
    from oclaw.runtime.hooks.hook_types import ensure_hook_entry

    entry = ensure_hook_entry(
        {
            "hook": {"name": "demo", "source": "oclaw-managed"},
            "metadata": {"events": ["command:new"], "requires": {"bins": ["git"]}},
            "invocation": {"enabled": True},
        }
    )
    cfg = {"hooks": {"internal": {"entries": {"demo": {"enabled": True}}}}}

    called: dict[str, int] = {"hasBin": 0}

    def _has_bin(_bin: str) -> bool:
        called["hasBin"] += 1
        return False

    ok = should_include_hook(
        entry=entry,
        config=cfg,
        eligibility={"remote": {"hasBin": _has_bin, "hasAnyBin": lambda bins: False}},
    )
    assert ok is False
    assert called["hasBin"] == 1


def test_workspace_discovers_enabled_plugin_hook_dirs(tmp_path: Path) -> None:
    from oclaw.runtime.hooks.workspace import load_workspace_hook_entries

    ws = tmp_path / "ws"
    plugin_root = ws / ".openclaw" / "extensions" / "sample-bundle"
    hook_dir = plugin_root / "hooks" / "bundle-hook"
    hook_dir.mkdir(parents=True)
    (plugin_root / ".codex-plugin").mkdir(parents=True)
    (plugin_root / ".codex-plugin" / "plugin.json").write_text(
        '{"name":"Sample Bundle","hooks":"hooks"}',
        encoding="utf-8",
    )
    (hook_dir / "HOOK.md").write_text(
        "---\n"
        "name: bundle-hook\n"
        "description: bundle hook\n"
        "metadata:\n"
        "  oclaw:\n"
        "    events: [\"command:new\"]\n"
        "---\n",
        encoding="utf-8",
    )
    (hook_dir / "handler.py").write_text("def handle(event):\n    return None\n", encoding="utf-8")

    entries = load_workspace_hook_entries(
        str(ws),
        config={"hooks": {"internal": {"enabled": True}}, "plugins": {"entries": {"sample-bundle": {"enabled": True}}}},
    )
    found = [e for e in entries if e.hook.name == "bundle-hook" and e.hook.source == "oclaw-plugin"]
    assert found
    assert found[0].hook.pluginId == "sample-bundle"


def test_workspace_skips_disabled_plugin_hook_dirs(tmp_path: Path) -> None:
    from oclaw.runtime.hooks.workspace import load_workspace_hook_entries

    ws = tmp_path / "ws"
    plugin_root = ws / ".openclaw" / "extensions" / "sample-bundle"
    hook_dir = plugin_root / "hooks" / "bundle-hook"
    hook_dir.mkdir(parents=True)
    (plugin_root / ".codex-plugin").mkdir(parents=True)
    (plugin_root / ".codex-plugin" / "plugin.json").write_text(
        '{"name":"Sample Bundle","hooks":"hooks"}',
        encoding="utf-8",
    )
    (hook_dir / "HOOK.md").write_text(
        "---\nname: bundle-hook\ndescription: bundle hook\nmetadata:\n  oclaw:\n    events: [\"command:new\"]\n---\n",
        encoding="utf-8",
    )
    (hook_dir / "handler.py").write_text("def handle(event):\n    return None\n", encoding="utf-8")

    entries = load_workspace_hook_entries(
        str(ws),
        config={"hooks": {"internal": {"enabled": True}}, "plugins": {"entries": {"sample-bundle": {"enabled": False}}}},
    )
    assert all(not (e.hook.name == "bundle-hook" and e.hook.source == "oclaw-plugin") for e in entries)


def test_legacy_internal_hook_handler_loads_from_workspace_relative_path(tmp_path: Path) -> None:
    from oclaw.runtime.hooks.internal_hooks import (
        clear_hooks,
        create_hook_event,
        set_hooks_enabled,
        trigger_hook,
    )
    from oclaw.runtime.hooks.loader import load_internal_hooks

    (tmp_path / "hooks").mkdir(parents=True, exist_ok=True)
    legacy_path = tmp_path / "legacy_handler.py"
    legacy_path.write_text(
        "def legacy(event):\n"
        "    event.context['legacy_called'] = True\n",
        encoding="utf-8",
    )
    cfg = {
        "hooks": {
            "internal": {
                "enabled": True,
                "handlers": [{"event": "command:new", "module": "legacy_handler.py", "export": "legacy"}],
            }
        }
    }
    clear_hooks()
    set_hooks_enabled(True)
    assert load_internal_hooks(cfg, workspace_dir=str(tmp_path), bundled_hooks_dir=str(tmp_path / "hooks")) >= 1

    async def _run() -> dict:
        ctx: dict = {"seed": True}
        ev = create_hook_event("command", "new", "agent:main:main", context=ctx)
        await trigger_hook(ev)
        return ev.context

    ctx = asyncio.run(_run())
    assert ctx.get("legacy_called") is True


def test_legacy_internal_hook_handler_rejects_path_escape(tmp_path: Path) -> None:
    from oclaw.runtime.hooks.loader import load_internal_hooks

    (tmp_path / "hooks").mkdir(parents=True, exist_ok=True)
    cfg = {
        "hooks": {
            "internal": {
                "enabled": True,
                "handlers": [{"event": "command:new", "module": "../outside.py", "export": "legacy"}],
            }
        }
    }
    assert load_internal_hooks(cfg, workspace_dir=str(tmp_path), bundled_hooks_dir=str(tmp_path / "hooks")) == 0


def test_build_workspace_hook_status_reports_summary(tmp_path: Path) -> None:
    from oclaw.runtime.hooks.hooks_status import build_workspace_hook_status

    ws = tmp_path / "ws"
    ok_dir = ws / "hooks" / "ok-hook"
    blocked_dir = ws / "hooks" / "blocked-hook"
    ok_dir.mkdir(parents=True)
    blocked_dir.mkdir(parents=True)

    (ok_dir / "HOOK.md").write_text(
        "---\nname: ok-hook\ndescription: ok\nmetadata:\n  oclaw:\n    events: [\"command:new\"]\n---\n",
        encoding="utf-8",
    )
    (ok_dir / "handler.py").write_text("def handle(event):\n    return None\n", encoding="utf-8")

    (blocked_dir / "HOOK.md").write_text(
        "---\nname: blocked-hook\ndescription: blocked\nenabled: false\nmetadata:\n  oclaw:\n    events: [\"command:new\"]\n---\n",
        encoding="utf-8",
    )
    (blocked_dir / "handler.py").write_text("def handle(event):\n    return None\n", encoding="utf-8")

    report = build_workspace_hook_status(
        str(ws),
        config={
            "hooks": {
                "internal": {
                    "enabled": True,
                    "entries": {"ok-hook": {"enabled": True}, "blocked-hook": {"enabled": True}},
                }
            }
        },
    )
    summary = report.get("summary") or {}
    hooks = report.get("hooks") or []
    assert summary.get("discovered_total") == 2
    assert summary.get("enabled_by_config_total") == 1
    assert summary.get("loadable_total") == 1
    names = {str(h.get("name")) for h in hooks if isinstance(h, dict)}
    assert "ok-hook" in names and "blocked-hook" in names


def test_build_workspace_hook_status_includes_install_options_and_missing_bins(tmp_path: Path) -> None:
    from oclaw.runtime.hooks.hooks_status import build_workspace_hook_status

    ws = tmp_path / "ws"
    hook_dir = ws / "hooks" / "installable-hook"
    hook_dir.mkdir(parents=True)
    (hook_dir / "HOOK.md").write_text(
        "---\n"
        "name: installable-hook\n"
        "description: hook with install metadata\n"
        "metadata:\n"
        "  oclaw:\n"
        "    events: [\"command:new\"]\n"
        "    requires:\n"
        "      bins: [\"definitely_missing_binary_123\"]\n"
        "    install:\n"
        "      - id: npm-install\n"
        "        kind: npm\n"
        "        label: Install via npm\n"
        "        bins: [\"definitely_missing_binary_123\"]\n"
        "---\n",
        encoding="utf-8",
    )
    (hook_dir / "handler.py").write_text("def handle(event):\n    return None\n", encoding="utf-8")

    report = build_workspace_hook_status(
        str(ws),
        config={"hooks": {"internal": {"enabled": True, "entries": {"installable-hook": {"enabled": True}}}}},
    )
    summary = report.get("summary") or {}
    hooks = report.get("hooks") or []
    assert summary.get("missing_bins_total") == 1
    row = next((h for h in hooks if isinstance(h, dict) and h.get("name") == "installable-hook"), {})
    assert "definitely_missing_binary_123" in list(row.get("missing_bins") or [])
    install_options = list(row.get("install_options") or [])
    assert install_options and install_options[0].get("id") == "npm-install"
    suggestion = row.get("install_suggestion") or {}
    assert suggestion.get("id") == "npm-install"


def test_build_workspace_hook_status_selects_best_install_suggestion(tmp_path: Path) -> None:
    from oclaw.runtime.hooks.hooks_status import build_workspace_hook_status

    ws = tmp_path / "ws"
    hook_dir = ws / "hooks" / "smart-install-hook"
    hook_dir.mkdir(parents=True)
    (hook_dir / "HOOK.md").write_text(
        "---\n"
        "name: smart-install-hook\n"
        "description: hook with multiple install options\n"
        "metadata:\n"
        "  oclaw:\n"
        "    events: [\"command:new\"]\n"
        "    requires:\n"
        "      bins: [\"missing_a\", \"missing_b\"]\n"
        "    install:\n"
        "      - id: option-single\n"
        "        kind: npm\n"
        "        bins: [\"missing_a\"]\n"
        "      - id: option-better\n"
        "        kind: npm\n"
        "        bins: [\"missing_a\", \"missing_b\"]\n"
        "---\n",
        encoding="utf-8",
    )
    (hook_dir / "handler.py").write_text("def handle(event):\n    return None\n", encoding="utf-8")

    report = build_workspace_hook_status(
        str(ws),
        config={"hooks": {"internal": {"enabled": True, "entries": {"smart-install-hook": {"enabled": True}}}}},
    )
    row = next((h for h in list(report.get("hooks") or []) if h.get("name") == "smart-install-hook"), {})
    suggestion = row.get("install_suggestion") or {}
    assert suggestion.get("id") == "option-better"


def test_hook_dir_prefers_handler_py_over_ts_and_sh(tmp_path: Path) -> None:
    from oclaw.runtime.hooks.workspace import load_hook_entries_from_dir

    h = tmp_path / "h"
    h.mkdir()
    (h / "HOOK.md").write_text(
        "---\n"
        "name: multi\n"
        "description: multi\n"
        "metadata:\n"
        "  oclaw:\n"
        "    events: [\"x:y\"]\n"
        "---\n",
        encoding="utf-8",
    )
    (h / "handler.py").write_text("def handle(e):\n    return None\n", encoding="utf-8")
    (h / "handler.ts").write_text("export default () => undefined\n", encoding="utf-8")
    (h / "handler.sh").write_text("#!/bin/sh\ntrue\n", encoding="utf-8")
    entries = load_hook_entries_from_dir(str(tmp_path), source="oclaw-bundled")
    assert len(entries) == 1
    assert entries[0].hook.handlerPath.endswith("handler.py")


def test_hook_dir_selects_ts_over_sh_when_no_py(tmp_path: Path) -> None:
    from oclaw.runtime.hooks.workspace import load_hook_entries_from_dir

    h = tmp_path / "h2"
    h.mkdir()
    (h / "HOOK.md").write_text(
        "---\n"
        "name: ts-or-sh\n"
        "description: ts or sh\n"
        "metadata:\n"
        "  oclaw:\n"
        "    events: [\"x:y\"]\n"
        "---\n",
        encoding="utf-8",
    )
    (h / "handler.sh").write_text("#!/bin/sh\ntrue\n", encoding="utf-8")
    (h / "handler.ts").write_text("export default () => undefined\n", encoding="utf-8")
    entries = load_hook_entries_from_dir(str(tmp_path), source="oclaw-bundled")
    assert len(entries) == 1
    assert entries[0].hook.handlerPath.endswith("handler.ts")


def test_hook_dir_prefers_mjs_over_sh_and_bash(tmp_path: Path) -> None:
    from oclaw.runtime.hooks.workspace import load_hook_entries_from_dir

    h = tmp_path / "h4"
    h.mkdir()
    (h / "HOOK.md").write_text(
        "---\n"
        "name: mjs\n"
        "description: mjs\n"
        "metadata:\n"
        "  oclaw:\n"
        "    events: [\"x:y\"]\n"
        "---\n",
        encoding="utf-8",
    )
    (h / "handler.mjs").write_text("export default () => undefined\n", encoding="utf-8")
    (h / "handler.bash").write_text("#!/bin/bash\ntrue\n", encoding="utf-8")
    (h / "handler.sh").write_text("#!/bin/sh\ntrue\n", encoding="utf-8")
    entries = load_hook_entries_from_dir(str(tmp_path), source="oclaw-bundled")
    assert len(entries) == 1
    assert entries[0].hook.handlerPath.endswith("handler.mjs")


def test_hook_dir_selects_sh_when_only_shell(tmp_path: Path) -> None:
    from oclaw.runtime.hooks.workspace import load_hook_entries_from_dir

    h = tmp_path / "h3"
    h.mkdir()
    (h / "HOOK.md").write_text(
        "---\n"
        "name: sh-only\n"
        "description: sh\n"
        "metadata:\n"
        "  oclaw:\n"
        "    events: [\"x:y\"]\n"
        "---\n",
        encoding="utf-8",
    )
    (h / "handler.sh").write_text("#!/bin/sh\ntrue\n", encoding="utf-8")
    entries = load_hook_entries_from_dir(str(tmp_path), source="oclaw-bundled")
    assert len(entries) == 1
    assert entries[0].hook.handlerPath.endswith("handler.sh")


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_sh_hook_merges_stdout_context(tmp_path: Path) -> None:
    from oclaw.runtime.hooks.internal_hooks import clear_hooks, create_hook_event, trigger_hook
    from oclaw.runtime.hooks.loader import load_internal_hooks

    hooks = tmp_path / "hooks"
    h = hooks / "sh-hook"
    h.mkdir(parents=True)
    (h / "HOOK.md").write_text(
        "---\n"
        "name: sh-hook\n"
        "description: sh\n"
        "metadata:\n"
        "  oclaw:\n"
        "    events: [\"probe:test\"]\n"
        "---\n",
        encoding="utf-8",
    )
    (h / "handler.sh").write_text(
        "#!/usr/bin/env bash\n"
        "python - <<'PY'\n"
        "import json, sys\n"
        "e = json.load(sys.stdin)\n"
        "c = e.get('context') or {}\n"
        "c['from_sh'] = 1\n"
        "print(json.dumps({'context': c}))\n"
        "PY\n",
        encoding="utf-8",
    )
    clear_hooks()
    n = load_internal_hooks(
        {"hooks": {"internal": {"enabled": True, "entries": {"sh-hook": {"enabled": True}}}}},
        str(tmp_path),
        bundled_hooks_dir=str(hooks),
    )
    assert n == 1
    ctx: dict = {"a": 1}

    async def _go() -> None:
        ev = create_hook_event("probe", "test", "sess-1", context=ctx)
        await trigger_hook(ev)

    asyncio.run(_go())
    assert ctx.get("from_sh") == 1


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_mjs_module_hook_mutates_context(tmp_path: Path) -> None:
    from oclaw.runtime.hooks.internal_hooks import clear_hooks, create_hook_event, trigger_hook
    from oclaw.runtime.hooks.loader import load_internal_hooks

    hooks = tmp_path / "hooks"
    h = hooks / "jmod"
    h.mkdir(parents=True)
    (h / "HOOK.md").write_text(
        "---\n"
        "name: jmod\n"
        "description: mjs mod\n"
        "metadata:\n"
        "  oclaw:\n"
        "    events: [\"probe2:test2\"]\n"
        "---\n",
        encoding="utf-8",
    )
    (h / "handler.mjs").write_text(
        "export default (e) => { e.context = e.context || {}; e.context.mjs = 1; };\n",
        encoding="utf-8",
    )
    clear_hooks()
    n = load_internal_hooks(
        {"hooks": {"internal": {"enabled": True, "entries": {"jmod": {"enabled": True}}}}},
        str(tmp_path),
        bundled_hooks_dir=str(hooks),
    )
    assert n == 1
    ctx: dict = {}

    async def _go() -> None:
        ev = create_hook_event("probe2", "test2", "s2", context=ctx)
        await trigger_hook(ev)

    asyncio.run(_go())
    assert ctx.get("mjs") == 1


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_mjs_script_mode_hook_merges_stdout(tmp_path: Path) -> None:
    from oclaw.runtime.hooks.internal_hooks import clear_hooks, create_hook_event, trigger_hook
    from oclaw.runtime.hooks.loader import load_internal_hooks

    hooks = tmp_path / "hooks2"
    h = hooks / "jscr"
    h.mkdir(parents=True)
    (h / "HOOK.md").write_text(
        "---\n"
        "name: jscr\n"
        "description: mjs script\n"
        "metadata:\n"
        "  oclaw:\n"
        "    events: [\"probe3:test3\"]\n"
        "    hookMode: script\n"
        "---\n",
        encoding="utf-8",
    )
    (h / "handler.mjs").write_text(
        "import { readFileSync } from 'node:fs';\n"
        "const e = JSON.parse(readFileSync(0, 'utf-8'));\n"
        "const c = e.context || {};\n"
        "c.jscript = 1;\n"
        "console.log(JSON.stringify({ context: c }));\n",
        encoding="utf-8",
    )
    clear_hooks()
    n = load_internal_hooks(
        {"hooks": {"internal": {"enabled": True, "entries": {"jscr": {"enabled": True}}}}},
        str(tmp_path),
        bundled_hooks_dir=str(hooks),
    )
    assert n == 1
    ctx: dict = {}

    async def _go() -> None:
        ev = create_hook_event("probe3", "test3", "s3", context=ctx)
        await trigger_hook(ev)

    asyncio.run(_go())
    assert ctx.get("jscript") == 1
