from __future__ import annotations

import hashlib
import threading
from pathlib import Path
from typing import Any

from oclaw.platform.config.paths import PROJECT_ROOT
from oclaw.runtime.memory_stage import render_memory_context_block
from oclaw.runtime.project_context_prompt import build_project_context_block
from oclaw.runtime.skills_prompt import build_skills_catalog_block
from oclaw.runtime.skills_workspace_lane import (
    fs_safe_workspace_lane_segment,
    workspace_lane_segment,
)
from oclaw.runtime.types import OclawMemoryContext
from oclaw.runtime.workspaces.experts import expert_workspace_signature_token
from oclaw.runtime.prompt_templates import render_runtime_prompt
from oclaw.runtime.tools.base import ToolRegistry

_EXECUTOR_STATIC_PROMPT_CACHE_LOCK = threading.Lock()
_EXECUTOR_STATIC_PROMPT_CACHE: dict[tuple[Any, ...], str] = {}


def _file_stat_signature(path: Path) -> str:
    try:
        st = path.stat()
        return f"{path.as_posix()}:{int(st.st_mtime_ns)}:{int(st.st_size)}"
    except Exception:
        return f"{path.as_posix()}:missing"


def _session_bootstrap_content_signature(*, skill_binding_role: str | None, workspace_dir: str | None) -> str:
    """Best-effort signature for session-bootstrap content sources.

    When this signature changes, cached executor system prompts are invalidated,
    so the next turn rebuilds project context and re-runs bootstrap hooks.
    """
    repo = Path(PROJECT_ROOT).resolve()
    role = str(skill_binding_role or "").strip().lower()
    ws = Path(workspace_dir).expanduser().resolve() if str(workspace_dir or "").strip() else None

    targets: list[Path] = []
    # session-bootstrap static source files
    targets.append((repo / "runtime" / "skills" / "session-bootstrap" / "SOUL.md").resolve())
    targets.append((repo / "runtime" / "skills" / "session-bootstrap" / "IDENTITY.md").resolve())
    # wiki global memory/improvement sources
    targets.append((repo / "data" / "wiki" / "improvement" / "learnings.md").resolve())
    targets.append((repo / "data" / "wiki" / "improvement" / "errors.md").resolve())
    targets.append((repo / "data" / "wiki" / "improvement" / "feature-requests.md").resolve())

    core_dir = (repo / "data" / "wiki" / "core").resolve()
    if core_dir.exists() and core_dir.is_dir():
        for p in sorted(core_dir.glob("*.md"), key=lambda x: x.name.lower()):
            targets.append(p.resolve())

    if role:
        role_dir = (repo / "data" / "wiki" / "experts" / role).resolve()
        if role_dir.exists() and role_dir.is_dir():
            for p in sorted(role_dir.glob("*.md"), key=lambda x: x.name.lower()):
                targets.append(p.resolve())

    if ws is not None:
        mem_dir = (ws / "memory").resolve()
        if mem_dir.exists() and mem_dir.is_dir():
            mem_files = [p for p in mem_dir.glob("*.md") if p.is_file()]
            mem_files.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0.0, reverse=True)
            if mem_files:
                targets.append(mem_files[0].resolve())

    h = hashlib.sha256()
    for p in targets:
        h.update(_file_stat_signature(p).encode("utf-8", errors="ignore"))
        h.update(b"\n")
    return h.hexdigest()[:24]


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
        "## 技能使用政策（Skill Usage Policy）：\n"
        "- 如果用户问你有哪些技能（skill/技能），请直接根据已注入的技能目录及其 description 回答。\n"
        "- 不要为了“列出技能”而去读取 SKILL.md。只有在你确实需要某个技能的详细使用说明时，才读取对应 SKILL.md。\n"
        "- 当你需要技能细节时，请按目录中给出的 path 读取对应的 SKILL.md。\n"
        "- 当对话涉及长期记忆、用户身份/偏好、项目背景延续、复发问题沉淀时，优先启用 wiki-first-autonomy 技能，并优先使用 memory_wiki_search/memory_wiki_get 检索上下文，再执行与回复。\n"
        "- 使用 memory_wiki_search 时默认采用三段检索：先 `query` 精确检索；若结果不足再启用 `expand_query=true`；仍不足时加 `path_prefix` 定向到候选目录后重检。\n"
        "- 三段检索建议参数：第一段 `limit=5~8`；第二段 `expand_query=true,max_rounds=2~3`；第三段在保留前述参数基础上增加 `path_prefix` 并分页（`offset`/`limit`）。\n"
        "- 每段检索后先依据 `queries_attempted`、`total_hits_estimate`、`next_offset` 判断是否继续，避免一次无命中就直接下结论。\n"
        "- memory wiki 请仅传相对 wiki 根的路径（相对 `data/wiki`），例如 `improvement/learnings.md`；不要传 `data/wiki/...` 或绝对路径。\n"
        "- 当新增事实会影响后续决策时，完成当前任务后使用 memory_wiki_apply 写入结构化记忆，并用 memory_wiki_lint 做质量检查。\n"
        "- 技能包由说明文档和可选文件组成。运行时不会自动执行技能 `scripts/` 目录下的文件；\n"
        "- internal hooks 是独立系统，也不会自动执行这些脚本。\n"
        "- 当用户明确要求运行技能脚本时，请使用项目允许的 terminal/bash/exec（或同类）工具执行；\n"
        "- 如果脚本依赖相对路径（例如 `.learnings/`），请将工作目录设置为用户工作区。\n"
        "- 在没有显式工具调用成功结果前，不要假设脚本已经执行。\n"
        "- 在 Windows 上，`.sh` 可能需要 Git Bash、WSL 或等效环境。\n"
        "- 工具调用必须通过模型的原生 `tool_calls` 协议返回；不要在正文输出 DSML/XML/工具协议 JSON 模板。\n"
        "- 若当前模型链路不支持原生 `tool_calls`，请用自然语言明确说明“当前无法发起工具调用”，并请求切换到支持该协议的链路；不要伪造或模拟工具调用。\n"
        "- 当用户目标是“安装 skill/技能”时，必须遵循 `oclaw-skill-manager` 的安装策略，并以其为唯一规范来源。\n"
        "- 安装路径强约束：仅允许 `skill_auto_install`（`_workspace` lane）；不得改用任何非 auto 路径或脚本绕过。\n"
        "- 严禁臆测前置条件：不要把未在规范中声明的环境变量、端口、服务启动状态当作必需前提。\n"
        "- 若安装失败，仅输出可验证事实（至少包含 `error_code` 与 `detail`）和最小下一步，不得编造基础设施依赖。\n"
    )


def _skill_catalog_lane_flags(
    *,
    skill_binding_role: str | None,
    workspace_owner_session_id: str | None,
    session_id: str | None,
) -> tuple[bool, str | None]:
    role = str(skill_binding_role or "").strip().lower()
    if role:
        return True, fs_safe_workspace_lane_segment(role)
    o = str(workspace_owner_session_id or "").strip()
    s = str(session_id or "").strip()
    if not o and not s:
        return False, None
    seg = workspace_lane_segment(workspace_owner_session_id=o or None, session_id=s or None)
    return True, seg


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
    workspace_owner_session_id: str | None = None,
    session_id: str | None = None,
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
        workspace_owner_session_id=workspace_owner_session_id,
        session_id=session_id,
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
    workspace_owner_session_id: str | None = None,
    session_id: str | None = None,
) -> str:
    excl, lane_seg = _skill_catalog_lane_flags(
        skill_binding_role=skill_binding_role,
        workspace_owner_session_id=workspace_owner_session_id,
        session_id=session_id,
    )
    cache_key = (
        str(base_url or "").strip(),
        str(base_system or "").strip(),
        str(workspace_dir or "").strip(),
        str(skill_binding_role or "").strip().lower(),
        expert_workspace_signature_token(),
        _executor_prompt_settings_signature(store),
        bool(tools is not None),
        int(bool(excl)),
        str(lane_seg or ""),
        _session_bootstrap_content_signature(skill_binding_role=skill_binding_role, workspace_dir=workspace_dir),
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
            exclude_foreign_private_workspace_skills=excl,
            private_workspace_lane_segment=lane_seg,
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
            workspace_owner_session_id=None,
            session_id=None,
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
