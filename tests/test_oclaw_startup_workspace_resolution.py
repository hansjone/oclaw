from __future__ import annotations

from svc.config.paths import PROJECT_ROOT
from interfaces.http.fastapi_app import _resolve_startup_workspace_dir, _resolve_startup_workspace_dirs


def test_resolve_startup_workspace_dir_from_agents_default() -> None:
    cfg = {
        "agents": {
            "list": [
                {"id": "main", "default": True, "workspace": "D:/project/chatgpt/oclaw/workspace-main"},
                {"id": "social", "workspace": "D:/project/chatgpt/oclaw/workspace-social"},
            ]
        }
    }
    got = _resolve_startup_workspace_dir(cfg)
    assert got.replace("\\", "/").endswith("/oclaw/workspace-main")


def test_resolve_startup_workspace_dirs_all_agents() -> None:
    cfg = {
        "agents": {
            "list": [
                {"id": "main", "default": True, "workspace": "D:/project/chatgpt/oclaw/workspace-main"},
                {"id": "social", "workspace": "D:/project/chatgpt/oclaw/workspace-social"},
            ]
        }
    }
    got = _resolve_startup_workspace_dirs(cfg)
    got_norm = [(aid, ws.replace("\\", "/")) for aid, ws in got]
    assert ("main", "D:/project/chatgpt/oclaw/workspace-main") in got_norm
    assert ("social", "D:/project/chatgpt/oclaw/workspace-social") in got_norm


def test_resolve_startup_workspace_dir_fallback_to_repo_runtime_main() -> None:
    got = _resolve_startup_workspace_dir({})
    expect = str((PROJECT_ROOT / "runtime" / "workspaces" / "main").resolve()).replace("\\", "/")
    assert got.replace("\\", "/") == expect

