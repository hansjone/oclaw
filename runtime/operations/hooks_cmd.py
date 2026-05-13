from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from typing import Any

_DEPREC_INSTALL = (
    "oclaw: `hooks install` is deprecated and not implemented in the Python CLI.\n"
    "  • Copy a hook directory to ~/.oclaw/hooks/<name>/ or <workspace>/hooks/<name>/ (HOOK.md + handler).\n"
    "  • See runtime/hooks/README.md for layout and handler priority.\n"
    "  • If you use the OpenClaw app: use `openclaw plugins install` for packaged hook bundles.\n"
)
_DEPREC_UPDATE = (
    "oclaw: `hooks update` is deprecated and not implemented in the Python CLI.\n"
    "  • Update hook sources in place under ~/.oclaw/hooks/ or your workspace hooks/ tree.\n"
    "  • If you use the OpenClaw app: use `openclaw plugins update`.\n"
)

from svc.config.runtime_paths import runtime_hooks_bundled_root
from runtime.hooks.config import should_include_hook
from runtime.hooks.frontmatter import resolve_hook_key
from runtime.hooks.hooks_status import build_workspace_hook_status
from runtime.hooks.hook_types import HookEntry
from runtime.hooks.merge_skill_hook_dirs import merge_skill_hook_extra_dirs_into_config
from runtime.hooks.user_config_hooks import (
    apply_hook_entry_enabled,
    load_storage_config_document,
    resolve_hooks_config_storage_path,
    save_storage_config_document,
)
from runtime.hooks.workspace import load_workspace_hook_entries
from runtime.hooks_runtime import resolve_runtime_config
from runtime.tools.path_guard import workspace_root


def _resolve_cli_workspace(ns: argparse.Namespace) -> str:
    w = getattr(ns, "workspace", None)
    if isinstance(w, str) and w.strip():
        return w.strip()
    env_ws = str(os.getenv("OCLAW_WORKSPACE") or "").strip()
    if env_ws:
        return env_ws
    return str(workspace_root())


def prepare_hooks_cli_config(cfg: dict[str, Any] | None) -> dict[str, Any]:
    base = dict(cfg or resolve_runtime_config() or {})
    return merge_skill_hook_extra_dirs_into_config(base)


def build_hooks_status_report(workspace_dir: str, *, config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = prepare_hooks_cli_config(config)
    extra = (((cfg.get("hooks") or {}).get("internal") or {}).get("load") or {}).get("extraDirs")
    extra_dirs = [str(x) for x in extra] if isinstance(extra, list) else None
    return build_workspace_hook_status(
        workspace_dir,
        config=cfg,
        bundled_hooks_dir=str(runtime_hooks_bundled_root()),
        extra_dirs=extra_dirs,
    )


def _load_hook_entries_for_workspace(workspace_dir: str, *, config: dict[str, Any] | None = None) -> list[HookEntry]:
    cfg = prepare_hooks_cli_config(config)
    extra = (((cfg.get("hooks") or {}).get("internal") or {}).get("load") or {}).get("extraDirs")
    extra_dirs = [str(x) for x in extra] if isinstance(extra, list) else None
    return load_workspace_hook_entries(
        workspace_dir,
        config=cfg,
        bundled_hooks_dir=str(runtime_hooks_bundled_root()),
        extra_dirs=extra_dirs,
    )


def find_hook_entry_for_name(workspace_dir: str, query: str, *, config: dict[str, Any] | None = None) -> HookEntry | None:
    q = str(query or "").strip()
    if not q:
        return None
    for e in _load_hook_entries_for_workspace(workspace_dir, config=config):
        hook_key = resolve_hook_key(e.hook.name, e.as_dict())
        if e.hook.name == q or hook_key == q:
            return e
    return None


def _status_row_for_entry(workspace_dir: str, entry: HookEntry, *, config: dict[str, Any] | None = None) -> dict[str, Any] | None:
    hook_key = resolve_hook_key(entry.hook.name, entry.as_dict())
    report = build_hooks_status_report(workspace_dir, config=config)
    for h in report.get("hooks") or []:
        if h.get("hook_key") == hook_key or h.get("name") == entry.hook.name:
            return h if isinstance(h, dict) else None
    return None


def _requirements_satisfied_if_entry_enabled(entry: HookEntry, *, config: dict[str, Any] | None = None) -> bool:
    """
    Same gate as OpenClaw ``enableHook`` (``requireEligible`` → ``requirementsSatisfied``):
    would this hook pass eligibility if its config entry were toggled on?
    """
    cfg = copy.deepcopy(prepare_hooks_cli_config(config))
    hook_key = resolve_hook_key(entry.hook.name, entry.as_dict())
    hooks = cfg.setdefault("hooks", {})
    internal = hooks.setdefault("internal", {})
    if not isinstance(internal, dict):
        hooks["internal"] = {}
        internal = hooks["internal"]
    internal["enabled"] = True
    entries = internal.setdefault("entries", {})
    if not isinstance(entries, dict):
        internal["entries"] = {}
        entries = internal["entries"]
    prev = entries.get(hook_key)
    base = dict(prev) if isinstance(prev, dict) else {}
    base["enabled"] = True
    entries[hook_key] = base
    return bool(should_include_hook(entry=entry, config=cfg, eligibility=None))


def _cmd_hooks_list(args: argparse.Namespace) -> int:
    report = build_hooks_status_report(_resolve_cli_workspace(args), config=None)
    hooks = list(report.get("hooks") or [])
    if getattr(args, "eligible", False):
        hooks = [h for h in hooks if h.get("loadable")]
    if args.json:
        out = {
            "workspace_dir": report.get("workspace_dir"),
            "summary": report.get("summary"),
            "hooks": hooks,
        }
        print(json.dumps(out, indent=2, default=str))
        return 0
    summary = report.get("summary") or {}
    ready = int(summary.get("loadable_total") or 0)
    total = int(summary.get("discovered_total") or 0)
    print(f"Hooks ({ready}/{total} ready)  workspace={report.get('workspace_dir')}")
    for h in hooks:
        if h.get("loadable"):
            st = "ready"
        elif not h.get("enabled_by_config"):
            st = "disabled"
        else:
            st = "missing"
        ev = ", ".join(str(x) for x in (h.get("events") or [])[:8])
        print(f"  [{st:8}] {h.get('name','')}  source={h.get('source','')}  events={ev}")
        if getattr(args, "verbose", False):
            br = h.get("blocked_reason") or ""
            mb = h.get("missing_bins") or []
            if br or mb:
                print(f"            blocked={br!r} missing_bins={mb}")
    return 0


def _cmd_hooks_check(args: argparse.Namespace) -> int:
    report = build_hooks_status_report(_resolve_cli_workspace(args), config=None)
    hooks = list(report.get("hooks") or [])
    eligible = [h for h in hooks if h.get("loadable")]
    bad = [h for h in hooks if not h.get("loadable")]
    if args.json:
        print(
            json.dumps(
                {
                    "workspace_dir": report.get("workspace_dir"),
                    "summary": report.get("summary"),
                    "eligible": [h.get("name") for h in eligible],
                    "not_eligible": [
                        {"name": h.get("name"), "blocked_reason": h.get("blocked_reason"), "missing_bins": h.get("missing_bins")}
                        for h in bad
                    ],
                },
                indent=2,
                default=str,
            )
        )
        return 0
    s = report.get("summary") or {}
    print("Hooks status")
    print(f"  total:     {s.get('discovered_total', 0)}")
    print(f"  loadable:  {s.get('loadable_total', 0)}")
    print(f"  blocked:   {len(bad)}")
    if bad:
        print("Not loadable:")
        for h in bad:
            print(f"  - {h.get('name')}: {h.get('blocked_reason') or 'missing requirements'}  missing_bins={h.get('missing_bins')}")
    return 0


def _cmd_hooks_info(args: argparse.Namespace) -> int:
    report = build_hooks_status_report(_resolve_cli_workspace(args), config=None)
    name = str(getattr(args, "name", "") or "").strip()
    hooks = list(report.get("hooks") or [])
    row = next((h for h in hooks if h.get("name") == name or h.get("hook_key") == name), None)
    if row is None:
        if args.json:
            print(json.dumps({"error": "not_found", "hook": name}, indent=2))
        else:
            print(f'Hook "{name}" not found. Try: python -m runtime.operations hooks list')
        return 1
    if args.json:
        print(json.dumps(row, indent=2, default=str))
        return 0
    print(f"{row.get('name')}  loadable={row.get('loadable')}  source={row.get('source')}")
    if row.get("plugin_id"):
        print(f"  plugin_id: {row.get('plugin_id')}")
    print(f"  events: {', '.join(str(x) for x in (row.get('events') or []))}")
    print(f"  enabled_by_config: {row.get('enabled_by_config')}")
    print(f"  eligible: {row.get('eligible')}")
    if not row.get("loadable"):
        print(f"  blocked_reason: {row.get('blocked_reason')}")
        print(f"  missing_bins: {row.get('missing_bins')}")
    opts = row.get("install_options") or []
    if opts:
        print("  install_options:")
        for o in opts:
            print(f"    - {o.get('id')}: {o.get('kind')}  {o.get('label')}")
    return 0


def _cmd_hooks_enable(args: argparse.Namespace) -> int:
    ws = _resolve_cli_workspace(args)
    name = str(getattr(args, "name", "") or "").strip()
    entry = find_hook_entry_for_name(ws, name, config=None)
    if entry is None:
        print(f'Hook "{name}" not found. Try: python -m runtime.operations hooks list --workspace ...')
        return 1
    if entry.hook.source == "oclaw-plugin":
        print("Plugin-managed hooks cannot be enabled via this CLI; enable or configure the plugin instead.")
        return 1
    hook_key = resolve_hook_key(entry.hook.name, entry.as_dict())
    if not _requirements_satisfied_if_entry_enabled(entry, config=None):
        row = _status_row_for_entry(ws, entry, config=None)
        reason = (row or {}).get("blocked_reason") or "missing requirements"
        print(f'Hook "{hook_key}" cannot be enabled: {reason}')
        return 1
    doc = load_storage_config_document()
    apply_hook_entry_enabled(doc, hook_key, True, ensure_internal_hooks_enabled=True)
    save_storage_config_document(doc)
    print(f"Enabled hook {hook_key!r} (config: {resolve_hooks_config_storage_path()})")
    return 0


def _cmd_hooks_disable(args: argparse.Namespace) -> int:
    ws = _resolve_cli_workspace(args)
    name = str(getattr(args, "name", "") or "").strip()
    entry = find_hook_entry_for_name(ws, name, config=None)
    if entry is None:
        print(f'Hook "{name}" not found.')
        return 1
    if entry.hook.source == "oclaw-plugin":
        print("Plugin-managed hooks cannot be disabled via this CLI; disable or configure the plugin instead.")
        return 1
    hook_key = resolve_hook_key(entry.hook.name, entry.as_dict())
    doc = load_storage_config_document()
    apply_hook_entry_enabled(doc, hook_key, False, ensure_internal_hooks_enabled=False)
    save_storage_config_document(doc)
    print(f"Disabled hook {hook_key!r} (config: {resolve_hooks_config_storage_path()})")
    return 0


def _cmd_hooks_install(args: argparse.Namespace) -> int:
    print(_DEPREC_INSTALL, file=sys.stderr, end="")
    spec = str(getattr(args, "spec", "") or "").strip()
    if not spec:
        print("error: missing path or package spec", file=sys.stderr)
        return 1
    print(f"note: spec was not installed: {spec!r}", file=sys.stderr)
    return 2


def _cmd_hooks_update(args: argparse.Namespace) -> int:
    print(_DEPREC_UPDATE, file=sys.stderr, end="")
    hid = getattr(args, "hook_id", None)
    parts = []
    if getattr(args, "dry_run", False):
        parts.append("dry_run")
    if getattr(args, "all", False):
        parts.append("all")
    if hid:
        parts.append(f"id={hid!r}")
    if parts:
        print(f"note: no update performed ({', '.join(parts)})", file=sys.stderr)
    else:
        print("note: no update performed (pass hook id or --all)", file=sys.stderr)
    return 2


def register_hooks_parser(root_sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    hooks = root_sub.add_parser("hooks", help="List and inspect internal hooks (discovery + eligibility)")
    hooks_sub = hooks.add_subparsers(dest="hooks_cmd", required=True)

    def _add_workspace(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--workspace",
            default=None,
            help="Workspace root for discovery (default: OCLAW_WORKSPACE or current directory)",
        )

    p_list = hooks_sub.add_parser("list", help="List discovered hooks")
    _add_workspace(p_list)
    p_list.add_argument("--json", action="store_true", help="JSON output")
    p_list.add_argument("--eligible", action="store_true", help="Only hooks that are loadable")
    p_list.add_argument("-v", "--verbose", action="store_true", help="Include blocked_reason / missing_bins")
    p_list.set_defaults(func=_cmd_hooks_list)

    p_check = hooks_sub.add_parser("check", help="Summary of hook loadability")
    _add_workspace(p_check)
    p_check.add_argument("--json", action="store_true")
    p_check.set_defaults(func=_cmd_hooks_check)

    p_info = hooks_sub.add_parser("info", help="Show details for one hook by name or hook_key")
    _add_workspace(p_info)
    p_info.add_argument("name", help="Hook name (HOOK.md name) or hookKey")
    p_info.add_argument("--json", action="store_true")
    p_info.set_defaults(func=_cmd_hooks_info)

    p_en = hooks_sub.add_parser("enable", help="Enable a hook (writes hooks.internal.entries.<key>.enabled)")
    _add_workspace(p_en)
    p_en.add_argument("name", help="Hook name or hookKey (must currently be loadable)")
    p_en.set_defaults(func=_cmd_hooks_enable)

    p_dis = hooks_sub.add_parser("disable", help="Disable a hook in config")
    _add_workspace(p_dis)
    p_dis.add_argument("name", help="Hook name or hookKey")
    p_dis.set_defaults(func=_cmd_hooks_disable)

    p_inst = hooks_sub.add_parser(
        "install",
        help="[deprecated] Install a hook pack (not implemented; prints migration hints)",
    )
    p_inst.add_argument("spec", help="npm spec, archive path, or directory (not processed)")
    p_inst.add_argument("-l", "--link", action="store_true", help="Ignored (OpenClaw CLI compat)")
    p_inst.add_argument("--pin", action="store_true", help="Ignored (OpenClaw CLI compat)")
    p_inst.set_defaults(func=_cmd_hooks_install)

    p_up = hooks_sub.add_parser(
        "update",
        help="[deprecated] Update hook packs (not implemented; prints migration hints)",
    )
    p_up.add_argument("hook_id", nargs="?", default=None, help="Hook pack id (optional if --all)")
    p_up.add_argument("--all", action="store_true", help="Ignored except for message context")
    p_up.add_argument("--dry-run", action="store_true", help="No-op; only prints deprecation")
    p_up.set_defaults(func=_cmd_hooks_update)
