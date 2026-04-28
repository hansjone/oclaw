from __future__ import annotations

import threading
from typing import Any

from oclaw.runtime.memory_stage import render_memory_context_block
from oclaw.runtime.project_context_prompt import build_project_context_block
from oclaw.runtime.skills_prompt import build_skills_catalog_block
from oclaw.runtime.types import OclawMemoryContext
from oclaw.runtime.workspaces.experts import expert_workspace_signature_token
from oclaw.prompts.loader import render_runtime_prompt
from oclaw.runtime.tools.base import ToolRegistry

_EXECUTOR_STATIC_PROMPT_CACHE_LOCK = threading.Lock()
_EXECUTOR_STATIC_PROMPT_CACHE: dict[tuple[Any, ...], str] = {}


def _executor_prompt_settings_signature(store: Any) -> tuple[str, ...]:
    keys = (
        "AIA_SKILL_RUNTIME_ENABLED",
        "AIA_SKILLS_PROMPT_IN_SYSTEM",
        "AIA_SKILL_DISABLED_NAMES",
        "AIA_SKILL_ROLE_BINDING_ENABLED",
        "AIA_SKILL_ROLE_BINDING_MANAGER_INHERIT",
        "AIA_PROJECT_CONTEXT_MAX_FILE_CHARS",
        "AIA_PROJECT_CONTEXT_MAX_TOTAL_CHARS",
    )
    parts: list[str] = []
    for key in keys:
        try:
            val = str(store.get_setting(key) or "")
        except Exception:
            val = ""
        parts.append(f"{key}={val}")
    return tuple(parts)


def _unified_skill_policy_guidance() -> str:
    # Global policy for all agents (including dynamic/ephemeral) — appended to base_system in build_executor_system_prompt.
    return (
        "- 如果用户问你有哪些技能（skill/技能），请直接根据已注入的技能目录及其 description 回答。\n"
        "- 不要为了“列出技能”而去读取 SKILL.md。只有在你确实需要某个技能的详细使用说明时，才读取对应 SKILL.md。\n"
        "- 当你需要技能细节时，请按目录中给出的 path 读取对应的 SKILL.md。\n"
        "- 当对话涉及长期记忆、用户身份/偏好、项目背景延续、复发问题沉淀时，优先启用 wiki-first-autonomy 技能，并优先使用 memory_wiki_search/memory_wiki_get 检索上下文，再执行与回复。\n"
        "- 当新增事实会影响后续决策时，完成当前任务后使用 memory_wiki_apply 写入结构化记忆，并用 memory_wiki_lint 做质量检查。\n"
        "- 技能包由说明文档和可选文件组成。运行时不会自动执行技能 `scripts/` 目录下的文件；\n"
        "- internal hooks 是独立系统，也不会自动执行这些脚本。\n"
        "- 当用户明确要求运行技能脚本时，请使用项目允许的 terminal/bash/exec（或同类）工具执行；\n"
        "- 如果脚本依赖相对路径（例如 `.learnings/`），请将工作目录设置为用户工作区。\n"
        "- 在没有显式工具调用成功结果前，不要假设脚本已经执行。\n"
        "- 在 Windows 上，`.sh` 可能需要 Git Bash、WSL 或等效环境。\n"
    )


def build_executor_system_prompt(
    *,
    store: Any,
    tools: ToolRegistry | None,
    base_url: str,
    base_system: str,
    memory_context: OclawMemoryContext | None,
    lang: str,
    workspace_dir: str | None = None,
    skill_binding_role: str | None = None,
) -> str:
    """Build the final system string for the oclaw executor (memory block + skills catalog).

    `lang` is reserved for future localized system fragments; current templates are bilingual/static.
    """
    _ = lang  # reserved for i18n extensions
    final_system = get_executor_prompt_static(
        store=store,
        tools=tools,
        base_url=base_url,
        base_system=base_system,
        workspace_dir=workspace_dir,
        skill_binding_role=skill_binding_role,
    )
    mem_block = render_memory_context_block(memory_context or OclawMemoryContext())
    if not mem_block:
        return final_system
    return render_runtime_prompt(
        "runtime/system_with_memory.md",
        variables={"system_prompt": final_system, "memory_context": mem_block},
        strict=True,
    )


def get_executor_prompt_static(
    *,
    store: Any,
    tools: ToolRegistry | None,
    base_url: str,
    base_system: str,
    workspace_dir: str | None = None,
    skill_binding_role: str | None = None,
) -> str:
    cache_key = (
        str(base_url or "").strip(),
        str(base_system or "").strip(),
        str(workspace_dir or "").strip(),
        str(skill_binding_role or "").strip().lower(),
        expert_workspace_signature_token(),
        _executor_prompt_settings_signature(store),
        bool(tools is not None),
    )
    with _EXECUTOR_STATIC_PROMPT_CACHE_LOCK:
        cached = _EXECUTOR_STATIC_PROMPT_CACHE.get(cache_key)
    if isinstance(cached, str):
        return cached
    final_system = str(base_system or "").strip()
    guide = _unified_skill_policy_guidance().strip()
    if guide and guide not in final_system:
        final_system = f"{final_system}\n\n{guide}".strip()
    project_block = build_project_context_block(store=store, workspace_dir=workspace_dir)
    if project_block:
        final_system = f"{final_system}\n\n{project_block}".strip()
    if tools is not None:
        cat = build_skills_catalog_block(
            store=store,
            registry=tools,
            base_url=str(base_url or ""),
            skill_binding_role=skill_binding_role,
        )
        if cat.strip():
            final_system = render_runtime_prompt(
                "runtime/system_with_skills.md",
                variables={"system_body": final_system, "skills_catalog": cat},
                strict=True,
            )
    with _EXECUTOR_STATIC_PROMPT_CACHE_LOCK:
        _EXECUTOR_STATIC_PROMPT_CACHE[cache_key] = final_system
        if len(_EXECUTOR_STATIC_PROMPT_CACHE) > 256:
            _EXECUTOR_STATIC_PROMPT_CACHE.clear()
    return final_system


def warm_executor_prompt_cache(
    *,
    store: Any,
    tools: ToolRegistry | None,
    base_url: str,
    role_base_systems: dict[str, str],
    workspace_dir: str | None = None,
) -> dict[str, int]:
    warmed = 0
    for role, base_system in (role_base_systems or {}).items():
        _ = get_executor_prompt_static(
            store=store,
            tools=tools,
            base_url=base_url,
            base_system=str(base_system or ""),
            workspace_dir=workspace_dir,
            skill_binding_role=str(role or "").strip().lower() or None,
        )
        warmed += 1
    return {"roles_warmed": int(warmed)}


def build_oclaw_executor_system_prompt(**kwargs: Any) -> str:
    return build_executor_system_prompt(**kwargs)


__all__ = [
    "build_executor_system_prompt",
    "build_oclaw_executor_system_prompt",
    "get_executor_prompt_static",
    "warm_executor_prompt_cache",
]
