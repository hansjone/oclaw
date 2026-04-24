from __future__ import annotations

import json
from pathlib import Path

from oclaw.openclaw_runtime.hooks_runtime import resolve_runtime_config


def test_resolve_runtime_config_from_env_json(monkeypatch) -> None:
    monkeypatch.setenv(
        "OPENCLAW_RUNTIME_CONFIG_JSON",
        json.dumps({"hooks": {"internal": {"enabled": False, "entries": {"x": {"enabled": False}}}}}),
    )
    monkeypatch.delenv("OPENCLAW_CONFIG_PATH", raising=False)
    cfg = resolve_runtime_config()
    assert ((cfg.get("hooks") or {}).get("internal") or {}).get("enabled") is False
    assert ((cfg.get("hooks") or {}).get("internal") or {}).get("entries", {}).get("x", {}).get("enabled") is False


def test_resolve_runtime_config_from_config_path(monkeypatch, tmp_path: Path) -> None:
    cfg_path = tmp_path / "openclaw.custom.json"
    cfg_path.write_text(
        json.dumps({"hooks": {"internal": {"enabled": True, "entries": {"session-memory": {"messages": 99}}}}}),
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENCLAW_RUNTIME_CONFIG_JSON", raising=False)
    monkeypatch.setenv("OPENCLAW_CONFIG_PATH", str(cfg_path))
    cfg = resolve_runtime_config()
    assert ((cfg.get("hooks") or {}).get("internal") or {}).get("enabled") is True
    assert (
        ((cfg.get("hooks") or {}).get("internal") or {}).get("entries", {}).get("session-memory", {}).get("messages")
        == 99
    )

