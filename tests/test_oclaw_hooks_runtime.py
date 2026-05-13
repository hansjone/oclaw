from __future__ import annotations

import json
from pathlib import Path

from runtime.hooks.eligibility_from_metadata import hook_eligibility_from_message_metadata
from runtime.hooks_runtime import (
    _reset_hooks_runtime_state_for_test,
    initialize_hooks_runtime,
    resolve_runtime_config,
)


def test_resolve_runtime_config_from_env_json(monkeypatch) -> None:
    monkeypatch.setenv(
        "OCLAW_RUNTIME_CONFIG_JSON",
        json.dumps({"hooks": {"internal": {"enabled": False, "entries": {"x": {"enabled": False}}}}}),
    )
    monkeypatch.delenv("OCLAW_CONFIG_PATH", raising=False)
    cfg = resolve_runtime_config()
    assert ((cfg.get("hooks") or {}).get("internal") or {}).get("enabled") is False
    assert ((cfg.get("hooks") or {}).get("internal") or {}).get("entries", {}).get("x", {}).get("enabled") is False


def test_resolve_runtime_config_from_config_path(monkeypatch, tmp_path: Path) -> None:
    cfg_path = tmp_path / "oclaw.custom.json"
    cfg_path.write_text(
        json.dumps({"hooks": {"internal": {"enabled": True, "entries": {"session-memory": {"messages": 99}}}}}),
        encoding="utf-8",
    )
    monkeypatch.delenv("OCLAW_RUNTIME_CONFIG_JSON", raising=False)
    monkeypatch.setenv("OCLAW_CONFIG_PATH", str(cfg_path))
    cfg = resolve_runtime_config()
    assert ((cfg.get("hooks") or {}).get("internal") or {}).get("enabled") is True
    assert (
        ((cfg.get("hooks") or {}).get("internal") or {}).get("entries", {}).get("session-memory", {}).get("messages")
        == 99
    )


def test_initialize_hooks_runtime_passes_remote_eligibility(monkeypatch, tmp_path: Path) -> None:
    _reset_hooks_runtime_state_for_test()
    empty_bundled = tmp_path / "empty-bundled"
    empty_bundled.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("runtime.hooks_runtime.runtime_hooks_bundled_root", lambda: str(empty_bundled))
    monkeypatch.setattr("runtime.hooks.merge_skill_hook_dirs.discover_workspace_skill_manifests", lambda: ())

    ws = tmp_path / "workspace"
    hook_dir = ws / "hooks" / "demo"
    hook_dir.mkdir(parents=True, exist_ok=True)
    (hook_dir / "HOOK.md").write_text(
        "---\n"
        "name: demo\n"
        "description: demo\n"
        "metadata:\n"
        "  oclaw:\n"
        "    events: [\"command:new\"]\n"
        "    requires:\n"
        "      bins: [\"git\"]\n"
        "---\n",
        encoding="utf-8",
    )
    (hook_dir / "handler.py").write_text("def handle(event):\n    return None\n", encoding="utf-8")
    cfg = {"hooks": {"internal": {"enabled": True, "entries": {"demo": {"enabled": True}}}}}
    loaded = initialize_hooks_runtime(
        cfg=cfg,
        workspace_dir=str(ws),
        eligibility={"remote": {"hasBin": lambda _bin: False, "hasAnyBin": lambda _bins: False}},
    )
    assert loaded == 0


def test_initialize_hooks_runtime_loads_when_metadata_bins_present_reports_requirement(
    monkeypatch, tmp_path: Path
) -> None:
    _reset_hooks_runtime_state_for_test()
    empty_bundled = tmp_path / "empty-bundled"
    empty_bundled.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("runtime.hooks_runtime.runtime_hooks_bundled_root", lambda: str(empty_bundled))
    monkeypatch.setattr("runtime.hooks.merge_skill_hook_dirs.discover_workspace_skill_manifests", lambda: ())

    ws = tmp_path / "workspace"
    hook_dir = ws / "hooks" / "demo"
    hook_dir.mkdir(parents=True, exist_ok=True)
    (hook_dir / "HOOK.md").write_text(
        "---\n"
        "name: demo\n"
        "description: demo\n"
        "metadata:\n"
        "  oclaw:\n"
        "    events: [\"command:new\"]\n"
        "    requires:\n"
        "      bins: [\"oclaw_fake_hook_bin\"]\n"
        "---\n",
        encoding="utf-8",
    )
    (hook_dir / "handler.py").write_text("def handle(event):\n    return None\n", encoding="utf-8")
    cfg = {"hooks": {"internal": {"enabled": True, "entries": {"demo": {"enabled": True}}}}}
    elig = hook_eligibility_from_message_metadata(
        {"hookEligibility": {"remote": {"binsPresent": ["oclaw_fake_hook_bin"]}}},
    )
    assert elig is not None
    loaded = initialize_hooks_runtime(cfg=cfg, workspace_dir=str(ws), eligibility=elig)
    assert loaded == 1

