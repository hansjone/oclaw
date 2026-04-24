from __future__ import annotations

from dataclasses import asdict
from typing import Any

from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.tools.mcp.manifest import McpServerManifest


class McpRegistry:
    def __init__(self, store: SqliteStore):
        self.store = store

    def upsert_manifest(self, manifest: McpServerManifest) -> None:
        self.store.upsert_mcp_server(
            server_id=manifest.server_id,
            source_type=manifest.source_type,
            source_ref=manifest.source_ref,
            version=manifest.version,
            entry_command=manifest.entry_command,
            entry_args=manifest.entry_args,
            env_schema=manifest.env_schema,
            required_permissions=manifest.permissions,
            risk_level=manifest.risk_level,
            timeout_s=manifest.timeout_s,
            enabled=manifest.enabled,
        )

    def list_servers(self, *, enabled_only: bool = False) -> list[dict[str, Any]]:
        return self.store.list_mcp_servers(enabled_only=enabled_only)

    def snapshot(self) -> dict[str, Any]:
        rows = self.list_servers(enabled_only=False)
        return {"count": len(rows), "servers": rows}

    @staticmethod
    def manifest_to_dict(manifest: McpServerManifest) -> dict[str, Any]:
        return asdict(manifest)


__all__ = ["McpRegistry"]

