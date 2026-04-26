from __future__ import annotations

from pathlib import Path
from typing import Any

from oclaw.runtime.skills import discover_workspace_skill_manifests


def merge_skill_hook_extra_dirs_into_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """
    Append skill package ``<skillDir>/hooks`` directories to ``hooks.internal.load.extraDirs``.

    Matches ``initialize_hooks_runtime`` so CLI / status reports see the same hook set as the agent.
    """
    resolved_cfg = dict(cfg)
    extra_dirs: list[str] = []
    try:
        for m in discover_workspace_skill_manifests():
            d = (Path(str(m.skill_dir or "")) / "hooks").resolve()
            if d.exists() and d.is_dir():
                extra_dirs.append(str(d))
    except Exception:
        extra_dirs = []
    if not extra_dirs:
        return resolved_cfg

    hooks_cfg = dict((resolved_cfg.get("hooks") or {})) if isinstance(resolved_cfg.get("hooks"), dict) else {}
    internal = dict((hooks_cfg.get("internal") or {})) if isinstance(hooks_cfg.get("internal"), dict) else {}
    load = dict((internal.get("load") or {})) if isinstance(internal.get("load"), dict) else {}
    prev = load.get("extraDirs")
    merged: list[str] = []
    if isinstance(prev, list):
        merged.extend([str(x) for x in prev if str(x).strip()])
    merged.extend([x for x in extra_dirs if x and x not in set(merged)])
    load["extraDirs"] = merged
    internal["load"] = load
    hooks_cfg["internal"] = internal
    resolved_cfg["hooks"] = hooks_cfg
    return resolved_cfg
