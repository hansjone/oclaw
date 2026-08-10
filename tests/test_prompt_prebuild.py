from __future__ import annotations

from typing import Any

from runtime import prompt_prebuild as pp


class _DummyStore:
    def __init__(self, settings: dict[str, str] | None = None):
        self._settings = dict(settings or {})

    def get_setting(self, key: str) -> str:
        return str(self._settings.get(key, ""))


def test_get_manager_prompt_prebuild_is_legacy_stub(monkeypatch) -> None:
    monkeypatch.setattr(pp, "discover_specialist_ids", lambda: ("generalist", "ops", "memory", "image"))

    out = pp.get_manager_prompt_prebuild(
        store=_DummyStore(),
        registry=object(),
        base_url="",
        memory_enabled=True,
    )
    assert "generalist" in str(out.get("allowed_fixed") or "")
    assert "ops" in str(out.get("allowed_fixed") or "")
    assert str(out.get("manager_context") or "") == ""


def test_warm_startup_prompt_prebuild_warms_specialists_only(monkeypatch) -> None:
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
    assert "manager" not in role_map
    assert "generalist" in role_map
    assert "ops" in role_map


def test_runtime_prewarm_prompts_snapshot_returns_roles(monkeypatch) -> None:
    monkeypatch.setattr(pp, "discover_specialist_ids", lambda: ("generalist", "ops"))
    monkeypatch.setattr(pp, "build_role_system_context", lambda role, template_vars=None: f"{role}_ctx")
    monkeypatch.setattr(pp, "get_executor_prompt_static", lambda **kwargs: f"exec::{kwargs.get('skill_binding_role')}")
    monkeypatch.setattr(pp, "default_registry", lambda **kwargs: object())

    out = pp.runtime_prewarm_prompts_snapshot(store=_DummyStore())
    assert out["ok"] is True
    prompts = out.get("prompts") or {}
    assert "manager" not in prompts
    assert "generalist" in prompts
    assert "ops" in prompts
    assert prompts["generalist"].get("system_prompt") == "exec::generalist"
    assert prompts["ops"].get("system_prompt") == "exec::ops"

    aliased = pp.runtime_prewarm_prompts_snapshot(store=_DummyStore(), role="manager")
    assert aliased["ok"] is True
    assert aliased.get("roles") == ["generalist"]
    assert "generalist" in (aliased.get("prompts") or {})


def test_manager_prompt_prebuild_stub_is_stateless(monkeypatch) -> None:
    monkeypatch.setattr(pp, "discover_specialist_ids", lambda: ("generalist", "ops", "memory"))
    a = pp.get_manager_prompt_prebuild(
        store=_DummyStore(),
        registry=object(),
        base_url="",
        memory_enabled=True,
    )
    b = pp.get_manager_prompt_prebuild(
        store=_DummyStore(),
        registry=object(),
        base_url="",
        memory_enabled=False,
    )
    assert a.get("manager_context") == ""
    assert "memory" not in (b.get("allowed_fixed") or ())
    assert "memory" in (a.get("allowed_fixed") or ())
