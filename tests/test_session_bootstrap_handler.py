from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


def _load_handler_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "skills"
        / "session-bootstrap"
        / "hooks"
        / "runtime"
        / "handler.py"
    )
    spec = importlib.util.spec_from_file_location("test_session_bootstrap_handler", str(module_path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_build_bootstrap_reads_skills_root_and_user_name(tmp_path: Path) -> None:
    mod = _load_handler_module()
    repo = tmp_path / "repo"
    ws = repo / "workspace"
    (repo / "skills" / "session-bootstrap").mkdir(parents=True)
    (repo / "data" / "wiki" / "users").mkdir(parents=True)
    ws.mkdir(parents=True)

    (repo / "skills" / "session-bootstrap" / "SOUL.md").write_text("SOUL_OK", encoding="utf-8")
    (repo / "skills" / "session-bootstrap" / "IDENTITY.md").write_text("IDENT_OK", encoding="utf-8")
    (repo / "data" / "wiki" / "users" / "current.md").write_text("name: Alice", encoding="utf-8")

    mod._repo_root = lambda: repo  # type: ignore[attr-defined]
    event = SimpleNamespace(context={"workspaceDir": str(ws), "agentId": "generalist"})
    content = mod._build_bootstrap_content(event)  # type: ignore[attr-defined]
    assert "SOUL_OK" in content
    assert "IDENT_OK" in content
    assert "欢迎回来，Alice" in content


def test_handle_sets_bootstrap_diag(tmp_path: Path) -> None:
    mod = _load_handler_module()
    repo = tmp_path / "repo"
    (repo / "skills" / "session-bootstrap").mkdir(parents=True)
    (repo / "skills" / "session-bootstrap" / "SOUL.md").write_text("x", encoding="utf-8")
    (repo / "skills" / "session-bootstrap" / "IDENTITY.md").write_text("y", encoding="utf-8")
    mod._repo_root = lambda: repo  # type: ignore[attr-defined]
    event = SimpleNamespace(
        type="agent",
        action="bootstrap",
        sessionKey="agent:main:main",
        context={"workspaceDir": str(tmp_path / "ws"), "bootstrapFiles": [], "agentId": "generalist"},
    )
    mod.handle(event)
    diag = event.context.get("sessionBootstrapDiag")
    assert isinstance(diag, dict)
    assert diag.get("soul_found") is True
    assert diag.get("identity_found") is True
