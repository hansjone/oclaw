from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from oclaw.runtime.agents.agent_scope import resolve_agent_id_by_workspace_path
from oclaw.runtime.hooks_runtime import get_active_hooks_config, trigger_hook_event
from oclaw.platform.config.paths import PROJECT_ROOT
from oclaw.runtime.prompt_templates import render_runtime_prompt

_PROJECT_CONTEXT_FILES: tuple[str, ...] = (
    "TOOLS.md",
    "HEARTBEAT.md",
    "BOOTSTRAP.md",
)


def _project_context_roots() -> tuple[Path, ...]:
    roots: list[Path] = []
    raw_ws = str(os.getenv("OCLAW_WORKSPACE") or "").strip()
    if raw_ws:
        roots.append(Path(raw_ws).expanduser())
    roots.append(Path(PROJECT_ROOT) / "runtime" / "workspaces" / "main")
    roots.append(Path(PROJECT_ROOT))
    out: list[Path] = []
    seen: set[str] = set()
    for p in roots:
        key = str(p.resolve()) if p.exists() else str(p)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return tuple(out)


def _max_file_chars(store: Any) -> int:
    try:
        raw = str(store.get_setting("AIA_PROJECT_CONTEXT_MAX_FILE_CHARS") or "").strip()
        if raw.isdigit():
            return max(200, min(int(raw), 200_000))
    except Exception:
        pass
    return 12_000


def _max_total_chars(store: Any) -> int:
    try:
        raw = str(store.get_setting("AIA_PROJECT_CONTEXT_MAX_TOTAL_CHARS") or "").strip()
        if raw.isdigit():
            return max(1_000, min(int(raw), 1_000_000))
    except Exception:
        pass
    return 60_000


def build_project_context_block(*, store: Any, workspace_dir: str | None = None) -> str:
    per_file_cap = _max_file_chars(store)
    total_cap = _max_total_chars(store)
    total = 0
    lines: list[str] = []
    cfg = get_active_hooks_config()
    roots: list[Path] = []
    # When workspace_dir is provided, isolate project context to that workspace
    # plus the shared PROJECT_ROOT fallback (avoid cross-agent pollution).
    if isinstance(workspace_dir, str) and workspace_dir.strip():
        roots.append(Path(workspace_dir).expanduser())
        roots.append(Path(PROJECT_ROOT))
    else:
        roots = list(_project_context_roots())
        # Include configured agent workspaces as additional roots (multi-agent support).
        try:
            agents = cfg.get("agents") if isinstance(cfg, dict) else None
            entries = agents.get("list") if isinstance(agents, dict) else None
            if isinstance(entries, list):
                for e in entries:
                    if not isinstance(e, dict):
                        continue
                    ws = str(e.get("workspace") or "").strip()
                    if ws:
                        roots.append(Path(ws).expanduser())
        except Exception:
            pass
    # De-dupe roots while preserving order.
    deduped: list[Path] = []
    seen: set[str] = set()
    for p in roots:
        key = str(p.resolve()) if p.exists() else str(p)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(p)
    roots = deduped
    bootstrap_files: list[dict[str, str]] = []
    root_bootstrap_files: list[tuple[str, list[dict[str, str]]]] = []
    for root in roots:
        one_root_files: list[dict[str, str]] = []
        for name in _PROJECT_CONTEXT_FILES:
            cand = (root / name).resolve()
            if cand.exists() and cand.is_file():
                one_root_files.append({"path": str(cand), "name": name})
        root_bootstrap_files.append((str(root), one_root_files))

    # Trigger bootstrap hooks for each discovered workspace root so multi-agent
    # workspaces can contribute extra bootstrap files independently.
    cfg = cfg
    for idx, (workspace_dir, one_root_files) in enumerate(root_bootstrap_files):
        agent_id = None
        try:
            agent_id = resolve_agent_id_by_workspace_path(cfg, workspace_dir)
        except Exception:
            agent_id = None
        agent_part = str(agent_id or "unknown").strip() or "unknown"
        # keep session keys log-friendly; avoid long absolute paths.
        ws_part = Path(workspace_dir).name or "workspace"
        trigger_hook_event(
            event_type="agent",
            action="bootstrap",
            session_key=f"system:agent:bootstrap:{agent_part}:{ws_part}:{idx}",
            context={
                "workspaceDir": workspace_dir,
                "bootstrapFiles": one_root_files,
                "cfg": cfg,
                "agentId": agent_id,
            },
        )
        bootstrap_files.extend(one_root_files)
    seen_paths: set[str] = set()
    candidate_paths: list[tuple[str, str]] = []
    for item in bootstrap_files:
        if not isinstance(item, dict):
            continue
        p = str(item.get("path") or "").strip()
        n = str(item.get("name") or "").strip() or Path(p).name
        if not p or p in seen_paths:
            continue
        seen_paths.add(p)
        candidate_paths.append((p, n))
    for name in _PROJECT_CONTEXT_FILES:
        p: Path | None = None
        for root in roots:
            cand = (root / name).resolve()
            if cand.exists() and cand.is_file():
                p = cand
                break
        if p is None:
            continue
        if str(p) not in seen_paths:
            seen_paths.add(str(p))
            candidate_paths.append((str(p), name))
    for raw_path, name in candidate_paths:
        p = Path(raw_path)
        if not p.exists() or not p.is_file():
            continue
        try:
            raw = p.read_text(encoding="utf-8")
        except Exception:
            continue
        txt = str(raw or "").strip()
        if not txt:
            continue
        clipped = txt[:per_file_cap]
        remain = max(0, total_cap - total)
        if remain <= 0:
            break
        chunk = clipped[:remain]
        if not chunk:
            continue
        total += len(chunk)
        lines.append(f"[{name}]")
        lines.append(chunk)
        lines.append("")

    if not lines:
        return ""
    return render_runtime_prompt(
        "runtime/project_context_block.md",
        variables={"project_context": "\n".join(lines).strip()},
        strict=True,
    )


__all__ = ["build_project_context_block"]
