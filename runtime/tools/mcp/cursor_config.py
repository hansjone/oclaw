# -*- coding: utf-8 -*-
"""Cursor-style ``mcpServers`` JSON ↔ oclaw MCP registry payloads."""

from __future__ import annotations

import json
import re
from typing import Any

_ENV_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_REMOTE_TYPES = {
    "streamablehttp",
    "streamable_http",
    "streamable-http",
    "http",
    "sse",
}


def _safe_server_id(seed: str) -> str:
    v = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(seed or "").strip().lower()).strip("-")
    return v or "mcp-server"


def _env_schema_from_cursor_env(env: dict[str, Any] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if not isinstance(env, dict):
        return out
    for ek, ev in env.items():
        name = str(ek or "").strip()
        if not name:
            continue
        out[name] = {
            "type": "string",
            "default": "" if ev is None else str(ev),
            "description": "From mcpServers env",
        }
    return out


def _env_schema_from_header_placeholders(headers: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for hk, hv in headers.items():
        for m in _ENV_VAR_RE.finditer(str(hv or "")):
            env_name = str(m.group(1) or "").strip()
            if not env_name or env_name in out:
                continue
            out[env_name] = {
                "required": True,
                "type": "string",
                "description": f"Auto-detected from header {str(hk or '').strip()}",
            }
    return out


def _cursor_env_from_schema(env_schema: dict[str, Any] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    if not isinstance(env_schema, dict):
        return out
    for ek, spec in env_schema.items():
        name = str(ek or "").strip()
        if not name:
            continue
        if isinstance(spec, dict):
            default = spec.get("default")
            out[name] = "" if default is None else str(default)
        else:
            out[name] = str(spec)
    return out


def _is_remote_server(server: dict[str, Any]) -> bool:
    transport = str(server.get("type") or "").strip().lower().replace(" ", "")
    url = str(server.get("url") or server.get("baseUrl") or "").strip()
    if transport in _REMOTE_TYPES:
        return True
    # Cursor often omits type and only sets url for remote servers.
    if url and not str(server.get("command") or server.get("entry_command") or "").strip():
        return True
    return False


def cursor_server_to_install_payload(server_id: str, server: dict[str, Any] | None) -> dict[str, Any]:
    """Convert one Cursor mcpServers entry into an oclaw install/upsert payload."""
    sid = _safe_server_id(server_id)
    s = server if isinstance(server, dict) else {}
    headers = s.get("headers") if isinstance(s.get("headers"), dict) else {}
    env_schema = _env_schema_from_header_placeholders(headers)
    enabled = bool(s["isActive"]) if "isActive" in s else True
    if "enabled" in s:
        enabled = bool(s.get("enabled"))
    timeout_s = float(s.get("timeout_s") or 30.0)

    if _is_remote_server(s):
        base_url = str(s.get("url") or s.get("baseUrl") or "").strip()
        if not base_url:
            raise ValueError(f"remote_mcp_missing_url:{sid}")
        entry_args = ["-y", "mcp-remote", base_url]
        for hk, hv in headers.items():
            hn = str(hk or "").strip()
            hvs = str(hv or "").strip()
            if not hn or not hvs:
                continue
            entry_args.extend(["--header", f"{hn}: {hvs}"])
        return {
            "server_id": sid,
            "source_type": "npm",
            "source_ref": "mcp-remote",
            "version": "",
            "entry_command": "npx",
            "entry_args": entry_args,
            "env_schema": env_schema,
            "required_permissions": [],
            "risk_level": "high",
            "enabled": enabled,
            "timeout_s": timeout_s,
        }

    cmd = str(s.get("command") or s.get("entry_command") or "").strip()
    if not cmd:
        raise ValueError(f"stdio_mcp_missing_command:{sid}")
    args_raw = s.get("args") if isinstance(s.get("args"), list) else s.get("entry_args")
    args = [str(x) for x in (args_raw or [])]
    env_from_cursor = _env_schema_from_cursor_env(s.get("env") if isinstance(s.get("env"), dict) else {})
    merged = {**env_from_cursor, **env_schema}
    if isinstance(s.get("env_schema"), dict):
        merged.update(s["env_schema"])
    return {
        "server_id": sid,
        "source_type": "local",
        "source_ref": sid,
        "version": "",
        "entry_command": cmd,
        "entry_args": args,
        "env_schema": merged,
        "required_permissions": [],
        "risk_level": "high",
        "enabled": enabled,
        "timeout_s": timeout_s,
    }


def parse_cursor_mcp_document(doc: Any) -> list[dict[str, Any]]:
    """Parse Cursor ``{ mcpServers: {...} }`` (or bare mcpServers object) into install payloads."""
    if not isinstance(doc, dict):
        raise ValueError("mcp_document_must_be_object")
    servers_obj = doc.get("mcpServers")
    if servers_obj is None and all(isinstance(v, dict) for v in doc.values()) and doc:
        # Allow pasting the inner map directly if every value looks like a server config.
        if any(k in next(iter(doc.values()), {}) for k in ("command", "url", "args", "type")):
            servers_obj = doc
    if not isinstance(servers_obj, dict) or not servers_obj:
        raise ValueError("mcpServers_required")
    out: list[dict[str, Any]] = []
    for raw_key, raw_server in servers_obj.items():
        key = str(raw_key or "").strip()
        if not key:
            continue
        out.append(cursor_server_to_install_payload(key, raw_server if isinstance(raw_server, dict) else {}))
    if not out:
        raise ValueError("mcpServers_empty")
    return out


def _try_parse_mcp_remote(entry_command: str, entry_args: list[str]) -> dict[str, Any] | None:
    cmd = str(entry_command or "").strip().lower()
    args = [str(x) for x in (entry_args or [])]
    if cmd not in {"npx", "npx.cmd"} and not cmd.endswith("npx") and not cmd.endswith("npx.cmd"):
        # Still allow if args contain mcp-remote (custom launcher).
        if "mcp-remote" not in args:
            return None
    if "mcp-remote" not in args:
        return None
    url = ""
    headers: dict[str, str] = {}
    i = 0
    while i < len(args):
        a = args[i]
        if a == "mcp-remote":
            i += 1
            continue
        if a in {"-y", "--yes"}:
            i += 1
            continue
        if a == "--header" and i + 1 < len(args):
            hv = args[i + 1]
            if ":" in hv:
                hk, hval = hv.split(":", 1)
                headers[hk.strip()] = hval.strip()
            i += 2
            continue
        if not url and not a.startswith("-"):
            url = a
            i += 1
            continue
        i += 1
    if not url:
        return None
    out: dict[str, Any] = {"url": url}
    if headers:
        out["headers"] = headers
    return out


def registry_row_to_cursor_server(row: dict[str, Any]) -> dict[str, Any]:
    """Convert one registry row into a Cursor mcpServers value."""
    entry_command = str(row.get("entry_command") or "").strip()
    raw_args = row.get("entry_args")
    entry_args = [str(x) for x in raw_args] if isinstance(raw_args, list) else []
    remote = _try_parse_mcp_remote(entry_command, entry_args)
    env = _cursor_env_from_schema(row.get("env_schema") if isinstance(row.get("env_schema"), dict) else {})
    if remote is not None:
        if env:
            # Keep env for header placeholders / runtime.
            remote = dict(remote)
            remote["env"] = env
        return remote
    out: dict[str, Any] = {"command": entry_command or "npx", "args": entry_args}
    if env:
        out["env"] = env
    return out


def build_cursor_mcp_export(rows: list[dict[str, Any]]) -> dict[str, Any]:
    servers: dict[str, Any] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        sid = str(row.get("server_id") or "").strip()
        if not sid:
            continue
        servers[sid] = registry_row_to_cursor_server(row)
    return {"mcpServers": servers}


def config_payload_to_upsert_fields(payload: dict[str, Any], *, existing: dict[str, Any]) -> dict[str, Any]:
    """Merge Admin edit payload (Cursor-ish) onto an existing registry row."""
    base = dict(existing)
    sid = str(payload.get("server_id") or base.get("server_id") or "").strip()
    if not sid:
        raise ValueError("server_id_required")

    # Prefer a nested cursor server object when provided.
    cursor_server = payload.get("server") if isinstance(payload.get("server"), dict) else None
    if cursor_server is None and (
        "command" in payload or "url" in payload or "args" in payload or "env" in payload or "headers" in payload
    ):
        cursor_server = {
            k: payload.get(k)
            for k in ("command", "args", "env", "url", "baseUrl", "headers", "type", "isActive", "enabled", "timeout_s")
            if k in payload
        }
    if cursor_server is not None:
        converted = cursor_server_to_install_payload(sid, cursor_server)
        if "enabled" in payload:
            converted["enabled"] = bool(payload.get("enabled"))
        if "timeout_s" in payload:
            converted["timeout_s"] = float(payload.get("timeout_s") or 30.0)
        return converted

    # Field-level updates without full Cursor object.
    entry_command = str(payload.get("entry_command") if "entry_command" in payload else base.get("entry_command") or "").strip()
    if "entry_args" in payload:
        entry_args = [str(x) for x in (payload.get("entry_args") or [])] if isinstance(payload.get("entry_args"), list) else []
    else:
        raw = base.get("entry_args")
        entry_args = [str(x) for x in raw] if isinstance(raw, list) else []
    if "env" in payload and isinstance(payload.get("env"), dict):
        env_schema = _env_schema_from_cursor_env(payload.get("env"))
    elif "env_schema" in payload and isinstance(payload.get("env_schema"), dict):
        env_schema = dict(payload.get("env_schema") or {})
    else:
        env_schema = dict(base.get("env_schema") or {}) if isinstance(base.get("env_schema"), dict) else {}
    enabled = bool(payload.get("enabled")) if "enabled" in payload else bool(base.get("enabled"))
    timeout_s = float(payload.get("timeout_s") if "timeout_s" in payload else (base.get("timeout_s") or 30.0))
    source_type = str(base.get("source_type") or "local")
    source_ref = str(base.get("source_ref") or sid)
    # If editing looks like mcp-remote, keep npm/mcp-remote markers.
    if "mcp-remote" in entry_args or source_ref == "mcp-remote":
        source_type = "npm"
        source_ref = "mcp-remote"
    elif source_type not in {"github", "npm", "pypi", "local"}:
        source_type = "local"
        source_ref = sid
    return {
        "server_id": sid,
        "source_type": source_type,
        "source_ref": source_ref,
        "version": str(base.get("version") or ""),
        "entry_command": entry_command,
        "entry_args": entry_args,
        "env_schema": env_schema,
        "required_permissions": list(base.get("required_permissions") or [])
        if isinstance(base.get("required_permissions"), list)
        else [],
        "risk_level": str(base.get("risk_level") or "high"),
        "enabled": enabled,
        "timeout_s": timeout_s,
    }


def dumps_cursor_export(rows: list[dict[str, Any]]) -> str:
    return json.dumps(build_cursor_mcp_export(rows), ensure_ascii=False, indent=2) + "\n"


__all__ = [
    "build_cursor_mcp_export",
    "config_payload_to_upsert_fields",
    "cursor_server_to_install_payload",
    "dumps_cursor_export",
    "parse_cursor_mcp_document",
    "registry_row_to_cursor_server",
]
