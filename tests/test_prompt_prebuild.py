from __future__ import annotations

from typing import Any

from oclaw.runtime import prompt_prebuild as pp


class _DummyStore:
    def __init__(self, settings: dict[str, str] | None = None):
        self._settings = dict(settings or {})

    def get_setting(self, key: str) -> str:
        return str(self._settings.get(key, ""))


def test_get_manager_prompt_prebuild_includes_structured_skills(monkeypatch) -> None:
    monkeypatch.setattr(pp, "discover_specialist_ids", lambda: ("generalist", "ops", "memory", "image"))
    monkeypatch.setattr(
        pp,
        "list_experts",
        lambda: [
            {"id": "generalist", "files": {"ROLE_SYSTEM.md": "General specialist for broad tasks."}},
            {"id": "ops", "files": {"ROLE_SYSTEM.md": "Ops specialist for runtime and services."}},
        ],
    )
    monkeypatch.setattr(pp, "expert_workspace_signature_token", lambda: ("sig",))

    def _ctx(_role: str, template_vars: dict[str, Any] | None = None) -> str:
        return f"CTX\n{str((template_vars or {}).get('MANAGER_DYNAMIC_EXPERTS_HINT') or '')}"

    monkeypatch.setattr(pp, "build_role_system_context", _ctx)

    out = pp.get_manager_prompt_prebuild(
        store=_DummyStore(),
        registry=object(),
        base_url="",
        memory_enabled=True,
    )
    assert "generalist" in str(out.get("allowed_fixed") or "")
    assert "- generalist:" in str(out.get("manager_context") or "")
    assert "General specialist for broad tasks." in str(out.get("manager_context") or "")


def test_warm_startup_prompt_prebuild_warms_all_roles(monkeypatch) -> None:
    monkeypatch.setattr(
        pp,
        "get_manager_prompt_prebuild",
        lambda **_k: {
            "manager_context": "manager_ctx",
            "allowed_fixed": ("generalist", "ops"),
            "allowed_fixed_quoted": '"generalist", "ops"',
        },
    )
    monkeypatch.setattr(pp, "discover_specialist_ids", lambda: ("generalist", "ops"))
    monkeypatch.setattr(pp, "build_role_system_context", lambda role, template_vars=None: f"{role}_ctx")

    captured: dict[str, Any] = {}

    def _warm(**kwargs):
        captured.update(kwargs)
        return {"roles_warmed": len(kwargs.get("role_base_systems") or {})}

    monkeypatch.setattr(pp, "warm_executor_prompt_cache", _warm)

    out = pp.warm_startup_prompt_prebuild(
        store=_DummyStore(),
        registry=object(),
        base_url="",
        memory_enabled=True,
    )
    assert out["ok"] is True
    role_map = captured.get("role_base_systems") if isinstance(captured, dict) else {}
    assert isinstance(role_map, dict)
    assert "manager" in role_map
    assert "generalist" in role_map
    assert "ops" in role_map


def test_runtime_prewarm_prompts_snapshot_returns_roles(monkeypatch) -> None:
    monkeypatch.setattr(pp, "discover_specialist_ids", lambda: ("generalist", "ops"))
    monkeypatch.setattr(
        pp,
        "get_manager_prompt_prebuild",
        lambda **_k: {
            "manager_context": "manager_ctx",
        },
    )
    monkeypatch.setattr(pp, "build_role_system_context", lambda role, template_vars=None: f"{role}_ctx")
    monkeypatch.setattr(pp, "get_executor_prompt_static", lambda **kwargs: f"exec::{kwargs.get('skill_binding_role')}")
    monkeypatch.setattr(pp, "default_registry", lambda **kwargs: object())

    out = pp.runtime_prewarm_prompts_snapshot(store=_DummyStore())
    assert out["ok"] is True
    prompts = out.get("prompts") or {}
    assert "manager" in prompts
    assert "generalist" in prompts
    assert "ops" in prompts
    assert prompts["manager"].get("system_prompt") == "exec::manager"
    assert prompts["generalist"].get("system_prompt") == "exec::generalist"
    assert prompts["ops"].get("system_prompt") == "exec::ops"
    assert "manager_system_prompt" not in prompts["manager"]
    assert "executor_system_prompt" not in prompts["manager"]
    assert "manager_user_scaffold" not in prompts["manager"]


def test_manager_prompt_prebuild_cache_invalidates_on_workspace_revision_change(monkeypatch) -> None:
    token = {"v": 1}
    calls = {"ctx": 0}

    monkeypatch.setattr(pp, "discover_specialist_ids", lambda: ("generalist", "ops"))
    monkeypatch.setattr(
        pp,
        "list_experts",
        lambda: [{"id": "generalist", "files": {"ROLE_SYSTEM.md": "General specialist"}}],
    )
    monkeypatch.setattr(pp, "expert_workspace_signature_token", lambda: ("revision", token["v"]))

    def _ctx(_role: str, template_vars: dict[str, Any] | None = None) -> str:
        calls["ctx"] += 1
        return f"CTX\n{str((template_vars or {}).get('MANAGER_DYNAMIC_EXPERTS_HINT') or '')}"

    monkeypatch.setattr(pp, "build_role_system_context", _ctx)

    _ = pp.get_manager_prompt_prebuild(
        store=_DummyStore(),
        registry=object(),
        base_url="",
        memory_enabled=True,
    )
    _ = pp.get_manager_prompt_prebuild(
        store=_DummyStore(),
        registry=object(),
        base_url="",
        memory_enabled=True,
    )
    assert calls["ctx"] == 1

    token["v"] = 2
    _ = pp.get_manager_prompt_prebuild(
        store=_DummyStore(),
        registry=object(),
        base_url="",
        memory_enabled=True,
    )
    assert calls["ctx"] == 2
