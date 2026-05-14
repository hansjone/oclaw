from __future__ import annotations

from fastapi import FastAPI

from interfaces.http import fastapi_app as app_mod


def test_run_startup_hooks_runs_prebuild_warmup(monkeypatch) -> None:
    class DummyStore:
        def revoke_all_auth_sessions(self) -> int:
            return 0

    monkeypatch.setattr(app_mod, "get_assistant_store", lambda: DummyStore())
    monkeypatch.setattr(app_mod, "prepare_gateway_plugin_bootstrap", lambda **kwargs: {"ok": True})
    monkeypatch.setattr(app_mod, "resolve_runtime_config", lambda: {})
    monkeypatch.setattr(app_mod, "skill_runtime_diagnostics", lambda: {"skills_root": "/tmp", "skills_total": 0})
    monkeypatch.setattr(app_mod, "warm_expert_workspace_cache", lambda: None)
    monkeypatch.setattr(app_mod, "_relocate_root_scan_artifacts", lambda: None)
    monkeypatch.setattr(app_mod, "initialize_hooks_runtime", lambda **kwargs: None)
    monkeypatch.setattr(app_mod, "trigger_hook_event", lambda **kwargs: None)
    monkeypatch.setattr(app_mod, "_resolve_startup_workspace_dirs", lambda _cfg: [("default", "/tmp/ws")])
    called: dict[str, object] = {"scheduler": 0}
    def _run_prewarm(**kwargs):
        called["prewarm"] = kwargs
        return {"ok": True, "elapsed_ms": 1, "freeze": {"frozen": True}}

    monkeypatch.setattr(app_mod, "run_runtime_prewarm", _run_prewarm)
    monkeypatch.setattr(app_mod, "_spawn_periodic_prewarm_loop", lambda: called.__setitem__("scheduler", 1))
    monkeypatch.setattr(app_mod, "_prewarm_interval_seconds", lambda: 600)

    app_mod._run_startup_hooks(FastAPI())
    assert "prewarm" in called
    assert called["scheduler"] == 1
