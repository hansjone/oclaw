from __future__ import annotations

from pathlib import Path

from oclaw.openclaw_runtime.project_context_prompt import build_project_context_block


class _Store:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self._v = dict(values or {})

    def get_setting(self, key: str) -> str:
        return str(self._v.get(key) or "")


def test_build_project_context_block_reads_workspace_bootstrap(monkeypatch, tmp_path: Path) -> None:
    ws = tmp_path / "oclaw" / "agent" / "workspace-main"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "AGENTS.md").write_text("agents rules", encoding="utf-8")
    (ws / "SOUL.md").write_text("soul voice", encoding="utf-8")
    monkeypatch.setattr("oclaw.openclaw_runtime.project_context_prompt.PROJECT_ROOT", tmp_path)
    out = build_project_context_block(store=_Store())
    assert "[project_context]" in out
    assert "[AGENTS.md]" in out
    assert "[SOUL.md]" in out


def test_build_project_context_block_empty_when_no_files(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("oclaw.openclaw_runtime.project_context_prompt.PROJECT_ROOT", tmp_path)
    out = build_project_context_block(store=_Store())
    assert out == ""


def test_build_project_context_block_fallback_to_project_root(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("legacy root agents", encoding="utf-8")
    monkeypatch.setattr("oclaw.openclaw_runtime.project_context_prompt.PROJECT_ROOT", tmp_path)
    out = build_project_context_block(store=_Store())
    assert "[AGENTS.md]" in out
    assert "legacy root agents" in out


def test_build_project_context_block_legacy_workspace_fallback(monkeypatch, tmp_path: Path) -> None:
    ws = tmp_path / "oclaw" / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "AGENTS.md").write_text("legacy workspace agents", encoding="utf-8")
    monkeypatch.setattr("oclaw.openclaw_runtime.project_context_prompt.PROJECT_ROOT", tmp_path)
    out = build_project_context_block(store=_Store())
    assert "[AGENTS.md]" in out
    assert "legacy workspace agents" in out


def test_build_project_context_block_workspace_main_fallback(monkeypatch, tmp_path: Path) -> None:
    ws = tmp_path / "oclaw" / "workspace-main"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "AGENTS.md").write_text("legacy workspace-main agents", encoding="utf-8")
    monkeypatch.setattr("oclaw.openclaw_runtime.project_context_prompt.PROJECT_ROOT", tmp_path)
    out = build_project_context_block(store=_Store())
    assert "[AGENTS.md]" in out
    assert "legacy workspace-main agents" in out


def test_build_project_context_block_triggers_bootstrap_for_each_root(monkeypatch, tmp_path: Path) -> None:
    ws_agent = tmp_path / "oclaw" / "agent" / "workspace-main"
    ws_main = tmp_path / "oclaw" / "workspace-main"
    ws_agent.mkdir(parents=True, exist_ok=True)
    ws_main.mkdir(parents=True, exist_ok=True)
    (ws_agent / "AGENTS.md").write_text("agent root", encoding="utf-8")
    (ws_main / "AGENTS.md").write_text("main root", encoding="utf-8")
    monkeypatch.setattr("oclaw.openclaw_runtime.project_context_prompt.PROJECT_ROOT", tmp_path)

    calls: list[dict] = []

    def _capture(**kwargs):
        calls.append(dict(kwargs))

    monkeypatch.setattr("oclaw.openclaw_runtime.project_context_prompt.trigger_hook_event", _capture)
    monkeypatch.setattr(
        "oclaw.openclaw_runtime.project_context_prompt.get_active_hooks_config",
        lambda: {"hooks": {"internal": {"enabled": True}}},
    )
    _ = build_project_context_block(store=_Store())

    workspaces = [str((c.get("context") or {}).get("workspaceDir") or "") for c in calls]
    norm = {w.replace("\\", "/") for w in workspaces}
    assert str(ws_agent).replace("\\", "/") in norm
    assert str(ws_main).replace("\\", "/") in norm


def test_project_context_bootstrap_includes_agent_id_when_config_matches(monkeypatch, tmp_path: Path) -> None:
    ws_agent = tmp_path / "oclaw" / "agent" / "workspace-main"
    ws_social = tmp_path / "oclaw" / "workspace-social"
    ws_agent.mkdir(parents=True, exist_ok=True)
    ws_social.mkdir(parents=True, exist_ok=True)
    (ws_agent / "AGENTS.md").write_text("agent root", encoding="utf-8")
    (ws_social / "AGENTS.md").write_text("social root", encoding="utf-8")
    monkeypatch.setattr("oclaw.openclaw_runtime.project_context_prompt.PROJECT_ROOT", tmp_path)

    calls: list[dict] = []

    def _capture(**kwargs):
        calls.append(dict(kwargs))

    monkeypatch.setattr("oclaw.openclaw_runtime.project_context_prompt.trigger_hook_event", _capture)
    monkeypatch.setattr(
        "oclaw.openclaw_runtime.project_context_prompt.get_active_hooks_config",
        lambda: {
            "hooks": {"internal": {"enabled": True}},
            "agents": {
                "list": [
                    {"id": "main", "default": True, "workspace": str(ws_agent)},
                    {"id": "social", "workspace": str(ws_social)},
                ]
            },
        },
    )
    _ = build_project_context_block(store=_Store())

    contexts = [c.get("context") or {} for c in calls]
    got = {(str(ctx.get("workspaceDir") or ""), str(ctx.get("agentId") or "")) for ctx in contexts}
    assert (str(ws_agent), "main") in got
    assert (str(ws_social), "social") in got
