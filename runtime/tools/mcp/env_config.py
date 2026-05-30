from __future__ import annotations

from typing import Any


def mcp_row_env_config(row: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    """Per-server env allowlist + defaults from registry ``env_schema``."""
    from runtime.operations.mcp_env import mcp_env_allowlist_keys

    schema = row.get("env_schema") if isinstance(row.get("env_schema"), dict) else {}
    defaults: dict[str, str] = {}
    schema_keys: list[str] = []
    for k, spec in schema.items():
        key = str(k or "").strip()
        if not key:
            continue
        schema_keys.append(key)
        if isinstance(spec, dict) and spec.get("default") is not None:
            dv = str(spec.get("default") or "").strip()
            if dv:
                defaults[key] = dv
    seen: set[str] = set()
    allowlist: list[str] = []
    for k in [*mcp_env_allowlist_keys(), *schema_keys]:
        if k and k not in seen:
            seen.add(k)
            allowlist.append(k)
    return allowlist, defaults


def mcp_runtime_for_row(row: dict[str, Any], *, store: Any) -> Any:
    from runtime.tools.mcp.filesystem_argv import build_mcp_process_command
    from runtime.tools.mcp.runtime import McpProcessRuntime

    cmd = str(row.get("entry_command") or "").strip()
    args = [str(x) for x in (row.get("entry_args") or []) if str(x).strip()]
    allowlist, defaults = mcp_row_env_config(row)
    return McpProcessRuntime(
        build_mcp_process_command(cmd, args, store=store),
        timeout_s=float(row.get("timeout_s") or 30.0),
        env_allowlist=allowlist,
        env_defaults=defaults,
    )


__all__ = ["mcp_row_env_config", "mcp_runtime_for_row"]
