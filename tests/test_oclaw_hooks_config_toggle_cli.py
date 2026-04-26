from __future__ import annotations

import argparse
import json
from pathlib import Path

from oclaw.runtime.hooks.user_config_hooks import apply_hook_entry_enabled, load_storage_config_document, save_storage_config_document


def test_apply_hook_entry_enabled_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OCLAW_CONFIG_PATH", str(tmp_path / "c.json"))
    doc: dict = {"other": 1}
    apply_hook_entry_enabled(doc, "my-hook", True, ensure_internal_hooks_enabled=True)
    assert doc["hooks"]["internal"]["enabled"] is True
    assert doc["hooks"]["internal"]["entries"]["my-hook"]["enabled"] is True
    apply_hook_entry_enabled(doc, "my-hook", False)
    assert doc["hooks"]["internal"]["entries"]["my-hook"]["enabled"] is False
    save_storage_config_document(doc)
    loaded = json.loads((tmp_path / "c.json").read_text(encoding="utf-8"))
    assert loaded["other"] == 1
    assert loaded["hooks"]["internal"]["entries"]["my-hook"]["enabled"] is False


def test_hooks_enable_disable_workspace_hook(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OCLAW_CONFIG_PATH", str(tmp_path / "cfg.json"))
    (tmp_path / "cfg.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "internal": {
                        "enabled": True,
                        "entries": {"toggle-hook": {"enabled": False}},
                    }
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    ws = tmp_path / "ws"
    h = ws / "hooks" / "toggle-hook"
    h.mkdir(parents=True)
    (h / "HOOK.md").write_text(
        "---\n"
        "name: toggle-hook\n"
        "description: t\n"
        "metadata:\n"
        "  oclaw:\n"
        "    events: [\"probe:toggle\"]\n"
        "---\n",
        encoding="utf-8",
    )
    (h / "handler.py").write_text("def handle(event):\n    return None\n", encoding="utf-8")

    from oclaw.runtime.operations.hooks_cmd import _cmd_hooks_disable, _cmd_hooks_enable

    assert _cmd_hooks_enable(argparse.Namespace(workspace=str(ws), name="toggle-hook")) == 0
    doc = json.loads((tmp_path / "cfg.json").read_text(encoding="utf-8"))
    assert doc["hooks"]["internal"]["entries"]["toggle-hook"]["enabled"] is True

    assert _cmd_hooks_disable(argparse.Namespace(workspace=str(ws), name="toggle-hook")) == 0
    doc2 = json.loads((tmp_path / "cfg.json").read_text(encoding="utf-8"))
    assert doc2["hooks"]["internal"]["entries"]["toggle-hook"]["enabled"] is False


def test_load_storage_empty_when_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OCLAW_CONFIG_PATH", str(tmp_path / "missing.json"))
    assert load_storage_config_document() == {}
