from __future__ import annotations

from typing import Any

from oclaw.openclaw_runtime.memory_stage import render_memory_context_block
from oclaw.openclaw_runtime.project_context_prompt import build_project_context_block
from oclaw.openclaw_runtime.skills_prompt import build_skills_catalog_block
from oclaw.openclaw_runtime.types import OpenClawMemoryContext
from oclaw.prompts.loader import render_openclaw_prompt
from oclaw.tools.base import ToolRegistry


def build_openclaw_executor_system_prompt(
    *,
    store: Any,
    tools: ToolRegistry | None,
    base_url: str,
    base_system: str,
    memory_context: OpenClawMemoryContext | None,
    lang: str,
    workspace_dir: str | None = None,
    skill_binding_role: str | None = None,
) -> str:
    """Build the final system string for the oclaw executor (memory block + skills catalog).

    `lang` is reserved for future localized system fragments; current templates are bilingual/static.
    """
    _ = lang  # reserved for i18n extensions
    final_system = str(base_system or "").strip()
    project_block = build_project_context_block(store=store, workspace_dir=workspace_dir)
    if project_block:
        final_system = f"{final_system}\n\n{project_block}".strip()
    mem_block = render_memory_context_block(memory_context or OpenClawMemoryContext())
    if mem_block:
        final_system = render_openclaw_prompt(
            "runtime/system_with_memory.md",
            variables={"system_prompt": final_system, "memory_context": mem_block},
            strict=True,
        )
    if tools is not None:
        cat = build_skills_catalog_block(
            store=store,
            registry=tools,
            base_url=str(base_url or ""),
            skill_binding_role=skill_binding_role,
        )
        if cat.strip():
            final_system = render_openclaw_prompt(
                "runtime/system_with_skills.md",
                variables={"system_body": final_system, "skills_catalog": cat},
                strict=True,
            )
    return final_system


__all__ = ["build_openclaw_executor_system_prompt"]
