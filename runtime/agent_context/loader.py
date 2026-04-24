from __future__ import annotations

from pathlib import Path

from oclaw.platform.config.paths import PROJECT_ROOT
from oclaw.prompts.loader import render_runtime_prompt


def _read_text(path: Path) -> str:
    try:
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8", errors="ignore").strip()
    except Exception:
        return ""
    return ""


def _workspace_for_role(role: str) -> str:
    r = str(role or "").strip().lower()
    if r in {"ops", "coding"}:
        return "workspace-coding"
    if r in {"social"}:
        return "workspace-social"
    return "workspace-main"


def build_role_system_context(role: str) -> str:
    """Build role context from runtime asset workspaces with prompt fallback."""
    workspace = _workspace_for_role(role)
    agent_root = (PROJECT_ROOT / "oclaw" / "runtime" / "assets" / "agent_workspaces" / workspace).resolve()
    parts: list[str] = []
    for name in ("AGENTS.md", "IDENTITY.md", "SOUL.md", "USER.md"):
        t = _read_text(agent_root / name)
        if t:
            parts.append(f"# {name}\n{t}")
    role_id = str(role or "").strip().lower()
    if role_id == "ops":
        fallback = render_runtime_prompt("roles/specialists/ops/system.md", strict=True)
    elif role_id == "image":
        fallback = render_runtime_prompt("roles/specialists/image/system.md", strict=True)
    elif role_id == "memory_curator":
        fallback = render_runtime_prompt("roles/specialists/memory_curator/system.md", strict=True)
    else:
        fallback = render_runtime_prompt("roles/specialists/generalist/system.md", strict=True)
    parts.append(f"# FALLBACK_ROLE_SYSTEM\n{fallback}")
    return "\n\n".join([p for p in parts if p.strip()]).strip()


__all__ = ["build_role_system_context"]

