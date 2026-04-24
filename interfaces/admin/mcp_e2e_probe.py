"""Build dynamic MCP E2E probe plans from the live ToolRegistry (one tool use per MCP server_id)."""
from __future__ import annotations

from typing import Any

from oclaw.runtime.tools.base import ToolRegistry, ToolSpec
from oclaw.runtime.tools.tool_validation import validate_tool_arguments


def parse_mcp_bound_tool_name(full_name: str) -> tuple[str, str] | None:
    """Parse ``mcp__{server_id}__{mcp_tool}`` into (server_id, mcp_tool_name)."""
    if not full_name.startswith("mcp__"):
        return None
    rest = full_name[len("mcp__") :]
    idx = rest.find("__")
    if idx < 0:
        return None
    server_id = rest[:idx].strip()
    tool = rest[idx + 2 :].strip()
    if not server_id or not tool:
        return None
    return server_id, tool


def _json_schema_required_keys(parameters: dict[str, Any]) -> list[str]:
    if not isinstance(parameters, dict) or parameters.get("type") != "object":
        return []
    req = parameters.get("required")
    if not isinstance(req, list):
        return []
    return [str(x).strip() for x in req if str(x).strip()]


def _fill_required_from_properties(
    parameters: dict[str, Any],
    *,
    workspace_root: str,
) -> dict[str, Any] | None:
    props = parameters.get("properties") if isinstance(parameters.get("properties"), dict) else {}
    req = _json_schema_required_keys(parameters)
    out: dict[str, Any] = {}
    for key in req:
        prop = props.get(key) if isinstance(props.get(key), dict) else {}
        t = prop.get("type")
        lk = key.lower()
        if t == "string":
            if lk in ("path", "cwd", "repopath", "directory", "filepath") or lk.endswith("path"):
                out[key] = workspace_root
            elif lk == "url":
                out[key] = "https://example.com"
            elif lk == "query":
                out[key] = "model context protocol"
            elif lk == "message":
                out[key] = "mcp-e2e"
            elif lk == "timezone":
                out[key] = "UTC"
            else:
                out[key] = ""
        elif t == "boolean":
            out[key] = True if lk in ("includeuntracked", "includetracked") else False
        elif t in ("number", "integer"):
            out[key] = 0
        elif t == "array":
            out[key] = []
        elif t == "object":
            out[key] = {}
        else:
            return None
    return out


# MCP tool names (suffix after server_id) with explicit args when schema is missing or validation needs concrete values.
_KNOWN_MCP_TOOL_ARGS: dict[str, dict[str, Any]] = {
    "sequentialthinking": {
        "thought": "e2e",
        "nextThoughtNeeded": False,
        "thoughtNumber": 1,
        "totalThoughts": 1,
    },
}

# Lower index = higher priority when multiple tools are callable.
_PROBE_PRIORITY: tuple[str, ...] = (
    "browser_close",
    "read_graph",
    "db_info",
    "list_pdfs",
    "echo",
    "list_directory",
    "git_status",
    "fetch_markdown",
    "web_search",
    "sequentialthinking",
)


def _probe_args_for_spec(spec: ToolSpec, *, workspace_root: str) -> dict[str, Any] | None:
    parsed = parse_mcp_bound_tool_name(spec.name)
    if not parsed:
        return None
    _, mcp_tool = parsed
    params = spec.parameters if isinstance(spec.parameters, dict) else {}

    if mcp_tool in _KNOWN_MCP_TOOL_ARGS:
        args = dict(_KNOWN_MCP_TOOL_ARGS[mcp_tool])
        ok, _ = validate_tool_arguments(params, args)
        return args if ok else None

    req = _json_schema_required_keys(params)
    if not req:
        args: dict[str, Any] = {}
        ok, _ = validate_tool_arguments(params, args)
        return args if ok else None

    filled = _fill_required_from_properties(params, workspace_root=workspace_root)
    if filled is None:
        return None
    ok, _ = validate_tool_arguments(params, filled)
    return filled if ok else None


def _pick_probe_for_server(specs: list[ToolSpec], *, workspace_root: str) -> tuple[ToolSpec, dict[str, Any]] | None:
    candidates: list[tuple[int, str, ToolSpec, dict[str, Any]]] = []
    for sp in specs:
        args = _probe_args_for_spec(sp, workspace_root=workspace_root)
        if args is None:
            continue
        ok, _ = validate_tool_arguments(sp.parameters or {}, args)
        if not ok:
            continue
        parsed = parse_mcp_bound_tool_name(sp.name)
        mcp_tool = (parsed or ("", ""))[1]
        try:
            pri = _PROBE_PRIORITY.index(mcp_tool)
        except ValueError:
            pri = 900
        candidates.append((pri, mcp_tool, sp, args))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1], x[2].name))
    return candidates[0][2], candidates[0][3]


def build_mcp_e2e_probe_plans(
    reg: ToolRegistry,
    *,
    workspace_root: str,
) -> tuple[list[tuple[str, str, dict[str, Any]]], list[str]]:
    """
    Returns (plans, skipped_server_ids).

    ``plans`` entries are ``(server_id, full_tool_name, arguments)`` for ``ToolExecutor.execute_tool_uses``.
    One probe per MCP ``server_id`` discovered from registry names ``mcp__*__*`` with tag ``mcp``.

    ``skipped_server_ids`` lists servers that had MCP tools in the registry but no schema-safe probe
    could be constructed (no false positives from arbitrary ``tools/call``).
    """
    by_server: dict[str, list[ToolSpec]] = {}
    for spec in reg.list():
        if "mcp" not in (spec.tags or frozenset()):
            continue
        parsed = parse_mcp_bound_tool_name(spec.name)
        if not parsed:
            continue
        sid, _ = parsed
        by_server.setdefault(sid, []).append(spec)

    plans: list[tuple[str, str, dict[str, Any]]] = []
    for sid in sorted(by_server.keys()):
        picked = _pick_probe_for_server(by_server[sid], workspace_root=workspace_root)
        if picked is None:
            continue
        spec, args = picked
        plans.append((sid, spec.name, args))
    planned = {p[0] for p in plans}
    skipped = [s for s in sorted(by_server.keys()) if s not in planned]
    return plans, skipped


__all__ = [
    "build_mcp_e2e_probe_plans",
    "parse_mcp_bound_tool_name",
]

