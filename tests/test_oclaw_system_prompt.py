from __future__ import annotations

from pathlib import Path

import pytest

from oclaw.runtime.system_prompt import build_oclaw_executor_system_prompt
from oclaw.runtime.types import OclawMemoryContext
from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.runtime.tools.base import ToolRegistry, ToolSpec


def _spec(name: str) -> ToolSpec:
    return ToolSpec(
        name=name,
        description="d",
        parameters={"type": "object", "properties": {}},
        handler=lambda _a: {"ok": True},
        read_only=True,
    )


def test_build_oclaw_executor_system_prompt_includes_skills_block(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "sp.sqlite"))
    store.create_session("s")
    reg = ToolRegistry([_spec("demo_tool")])
    out = build_oclaw_executor_system_prompt(
        store=store,
        tools=reg,
        base_url="",
        base_system="You are helpful.",
        memory_context=OclawMemoryContext(),
        lang="zh",
    )
    assert "## 技能（skills）：" in out
    assert '- name:"' in out


def test_build_oclaw_executor_system_prompt_without_tools_has_no_skills_block(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "sp1.sqlite"))
    store.create_session("s")
    out = build_oclaw_executor_system_prompt(
        store=store,
        tools=None,
        base_url="",
        base_system="  plain  ",
        memory_context=OclawMemoryContext(),
        lang="zh",
    )
    assert "## 技能（skills）：" not in out
    assert "不会自动执行技能 `scripts/` 目录下的文件" in out
    assert "scripts/" in out


def test_build_oclaw_executor_system_prompt_with_tools_has_skills(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "sp2.sqlite"))
    store.create_session("s")
    reg = ToolRegistry([_spec("x")])
    out = build_oclaw_executor_system_prompt(
        store=store,
        tools=reg,
        base_url="",
        base_system="base",
        memory_context=OclawMemoryContext(),
        lang="zh",
    )
    assert "## 技能（skills）：" in out
    assert '- name:"' in out


def test_executor_static_prompt_cache_invalidates_on_settings_change(monkeypatch: pytest.MonkeyPatch) -> None:
    from oclaw.runtime import system_prompt as sp

    class DummyStore:
        def __init__(self) -> None:
            self.values: dict[str, str] = {}

        def get_setting(self, key: str) -> str:
            return str(self.values.get(key, ""))

    class DummyReg:
        pass

    calls = {"n": 0}

    def _skills_block(**kwargs) -> str:
        _ = kwargs
        calls["n"] += 1
        return "skills-block"

    monkeypatch.setattr(sp, "expert_workspace_signature_token", lambda: ("sig",))
    monkeypatch.setattr(sp, "build_project_context_block", lambda **kwargs: "")
    monkeypatch.setattr(sp, "build_skills_catalog_block", _skills_block)
    monkeypatch.setattr(
        sp,
        "render_runtime_prompt",
        lambda prompt_id, variables, strict: f"{prompt_id}\n{variables.get('skills_catalog') or ''}",
    )

    store = DummyStore()
    reg = DummyReg()
    _ = sp.get_executor_prompt_static(
        store=store,
        tools=reg,  # type: ignore[arg-type]
        base_url="",
        base_system="base",
        workspace_dir=None,
        skill_binding_role="generalist",
    )
    _ = sp.get_executor_prompt_static(
        store=store,
        tools=reg,  # type: ignore[arg-type]
        base_url="",
        base_system="base",
        workspace_dir=None,
        skill_binding_role="generalist",
    )
    assert calls["n"] == 1

    store.values["AIA_SKILL_DISABLED_NAMES"] = "[\"weather\"]"
    _ = sp.get_executor_prompt_static(
        store=store,
        tools=reg,  # type: ignore[arg-type]
        base_url="",
        base_system="base",
        workspace_dir=None,
        skill_binding_role="generalist",
    )
    assert calls["n"] == 2


def test_executor_static_prompt_cache_invalidates_on_skill_role_binding_change(monkeypatch: pytest.MonkeyPatch) -> None:
    from oclaw.runtime import system_prompt as sp

    class DummyStore:
        def __init__(self) -> None:
            self.values: dict[str, str] = {"skill_role_binding": "{}"}

        def get_setting(self, key: str) -> str:
            return str(self.values.get(key, ""))

    class DummyReg:
        pass

    calls = {"n": 0}

    def _skills_block(**kwargs) -> str:
        _ = kwargs
        calls["n"] += 1
        return "skills-block"

    monkeypatch.setattr(sp, "expert_workspace_signature_token", lambda: ("sig",))
    monkeypatch.setattr(sp, "build_project_context_block", lambda **kwargs: "")
    monkeypatch.setattr(sp, "build_skills_catalog_block", _skills_block)
    monkeypatch.setattr(
        sp,
        "render_runtime_prompt",
        lambda prompt_id, variables, strict: f"{prompt_id}\n{variables.get('skills_catalog') or ''}",
    )

    store = DummyStore()
    reg = DummyReg()
    _ = sp.get_executor_prompt_static(
        store=store,
        tools=reg,  # type: ignore[arg-type]
        base_url="",
        base_system="base",
        workspace_dir=None,
        skill_binding_role="generalist",
    )
    _ = sp.get_executor_prompt_static(
        store=store,
        tools=reg,  # type: ignore[arg-type]
        base_url="",
        base_system="base",
        workspace_dir=None,
        skill_binding_role="generalist",
    )
    assert calls["n"] == 1

    store.values["skill_role_binding"] = '{"generalist": ["alpha-skill"]}'
    _ = sp.get_executor_prompt_static(
        store=store,
        tools=reg,  # type: ignore[arg-type]
        base_url="",
        base_system="base",
        workspace_dir=None,
        skill_binding_role="generalist",
    )
    assert calls["n"] == 2


def test_executor_static_prompt_cache_invalidates_on_workspace_revision_change(monkeypatch: pytest.MonkeyPatch) -> None:
    from oclaw.runtime import system_prompt as sp

    class DummyStore:
        def get_setting(self, key: str) -> str:
            _ = key
            return ""

    class DummyReg:
        pass

    calls = {"n": 0}
    token = {"v": 1}

    def _skills_block(**kwargs) -> str:
        _ = kwargs
        calls["n"] += 1
        return "skills-block"

    monkeypatch.setattr(sp, "expert_workspace_signature_token", lambda: ("revision", token["v"]))
    monkeypatch.setattr(sp, "build_project_context_block", lambda **kwargs: "")
    monkeypatch.setattr(sp, "build_skills_catalog_block", _skills_block)
    monkeypatch.setattr(
        sp,
        "render_runtime_prompt",
        lambda prompt_id, variables, strict: f"{prompt_id}\n{variables.get('skills_catalog') or ''}",
    )

    store = DummyStore()
    reg = DummyReg()
    _ = sp.get_executor_prompt_static(
        store=store,
        tools=reg,  # type: ignore[arg-type]
        base_url="",
        base_system="base",
        workspace_dir=None,
        skill_binding_role="generalist",
    )
    _ = sp.get_executor_prompt_static(
        store=store,
        tools=reg,  # type: ignore[arg-type]
        base_url="",
        base_system="base",
        workspace_dir=None,
        skill_binding_role="generalist",
    )
    assert calls["n"] == 1

    token["v"] = 2
    _ = sp.get_executor_prompt_static(
        store=store,
        tools=reg,  # type: ignore[arg-type]
        base_url="",
        base_system="base",
        workspace_dir=None,
        skill_binding_role="generalist",
    )
    assert calls["n"] == 2
