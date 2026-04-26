from __future__ import annotations

import shutil
from typing import Any

from .config import should_include_hook
from .hook_types import HookEligibilityContext
from .policy import resolve_hook_enable_state
from .workspace import load_workspace_hook_entries


def _select_install_suggestion(
    *, install_options: list[dict[str, Any]], missing_bins: list[str]
) -> dict[str, Any] | None:
    if not install_options:
        return None
    if not missing_bins:
        return dict(install_options[0])

    missing = set(missing_bins)
    best: tuple[int, int, dict[str, Any]] | None = None
    for idx, row in enumerate(install_options):
        bins = [str(x).strip() for x in list(row.get("bins") or []) if str(x).strip()]
        overlap = len(missing.intersection(set(bins)))
        # Sort by overlap desc, then idx asc (stable preference for first declared option).
        score = (overlap, -idx)
        if best is None or score > (best[0], best[1]):
            best = (score[0], score[1], row)
    return dict(best[2]) if best else dict(install_options[0])


def build_workspace_hook_status(
    workspace_dir: str,
    *,
    config: dict[str, Any] | None = None,
    managed_hooks_dir: str | None = None,
    bundled_hooks_dir: str | None = None,
    extra_dirs: list[str] | None = None,
    eligibility: HookEligibilityContext | None = None,
) -> dict[str, Any]:
    entries = load_workspace_hook_entries(
        workspace_dir,
        config=config,
        managed_hooks_dir=managed_hooks_dir,
        bundled_hooks_dir=bundled_hooks_dir,
        extra_dirs=extra_dirs,
    )
    rows: list[dict[str, Any]] = []
    summary = {
        "discovered_total": 0,
        "enabled_by_config_total": 0,
        "eligible_total": 0,
        "loadable_total": 0,
        "missing_bins_total": 0,
        "blocked_by_reason": {},
    }

    for entry in entries:
        summary["discovered_total"] += 1
        state = resolve_hook_enable_state(entry, config)
        enabled = bool(state.get("enabled"))
        if enabled:
            summary["enabled_by_config_total"] += 1
        eligible = should_include_hook(entry=entry, config=config, eligibility=eligibility)
        if eligible:
            summary["eligible_total"] += 1
        loadable = enabled and eligible
        if loadable:
            summary["loadable_total"] += 1
        reason = str(state.get("reason") or "")
        if not loadable:
            blocked = reason or ("missing requirements" if enabled else "disabled")
            summary["blocked_by_reason"][blocked] = int(summary["blocked_by_reason"].get(blocked) or 0) + 1

        md = entry.metadata or {}
        req = md.get("requires") if isinstance(md.get("requires"), dict) else {}
        required_bins = [str(x).strip() for x in list(req.get("bins") or []) if str(x).strip()]
        missing_bins = [b for b in required_bins if not shutil.which(b)]
        if missing_bins:
            summary["missing_bins_total"] += len(missing_bins)

        install_rows = md.get("install") if isinstance(md.get("install"), list) else []
        install_options: list[dict[str, Any]] = []
        for idx, row in enumerate(install_rows):
            if not isinstance(row, dict):
                continue
            kind = str(row.get("kind") or "").strip()
            if not kind:
                continue
            install_options.append(
                {
                    "id": str(row.get("id") or f"{kind}-{idx}"),
                    "kind": kind,
                    "label": str(row.get("label") or ""),
                    "bins": [str(x).strip() for x in list(row.get("bins") or []) if str(x).strip()],
                }
            )

        rows.append(
            {
                "name": entry.hook.name,
                "source": entry.hook.source,
                "plugin_id": entry.hook.pluginId,
                "hook_key": str((entry.metadata or {}).get("hookKey") or entry.hook.name),
                "events": list((entry.metadata or {}).get("events") or []),
                "enabled_by_config": enabled,
                "eligible": bool(eligible),
                "loadable": bool(loadable),
                "blocked_reason": "" if loadable else (reason or "missing requirements"),
                "required_bins": required_bins,
                "missing_bins": missing_bins,
                "install_options": install_options,
                "install_suggestion": _select_install_suggestion(
                    install_options=install_options,
                    missing_bins=missing_bins,
                ),
            }
        )

    return {
        "workspace_dir": workspace_dir,
        "summary": summary,
        "hooks": rows,
    }

