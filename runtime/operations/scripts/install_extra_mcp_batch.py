"""One-off helper: install additional npm MCP servers into local registry (stdio / npx).

Run from repo root: python oclaw/scripts/install_extra_mcp_batch.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# repo root
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from svc.config.paths import db_path  # noqa: E402
from svc.persistence.sqlite_store import SqliteStore  # noqa: E402
from runtime.tools.mcp.installer import McpServerManifest, _safe_server_id, install_mcp_server  # noqa: E402


# (server_id_seed, npm package ref, entry_args for npx)
# Note: mcp-smart-crawler was tried; stdio JSON-RPC handshake failed on Windows — not registered.
BATCH: list[tuple[str, str, list[str]]] = [
    ("mcp-git-cyanheads", "@cyanheads/git-mcp-server", ["-y", "@cyanheads/git-mcp-server"]),
]


def main() -> None:
    store = SqliteStore(db_path())
    for seed, source_ref, entry_args in BATCH:
        server_id = _safe_server_id(seed)
        manifest = McpServerManifest(
            server_id=server_id,
            source_type="npm",
            source_ref=source_ref,
            version="",
            entry_command="npx",
            entry_args=entry_args,
            env_schema={},
            permissions=[],
            risk_level="high",
            enabled=True,
            timeout_s=60.0,
        )
        print(f"\n=== Installing {server_id} ({source_ref}) ===")
        inst = install_mcp_server(manifest, dry_run=False)
        store.upsert_mcp_server(
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
            enabled=manifest.enabled if inst.ok else False,
        )
        store.add_mcp_installation_log(
            server_id=manifest.server_id,
            status="ok" if inst.ok else "error",
            error_code=inst.error_code,
            detail={"error": inst.error, **(inst.details or {})},
            install_command=inst.install_command,
        )
        print("ok:", inst.ok, inst.error_code or "-", inst.install_command)
        if not inst.ok:
            print("stderr snippet:", (inst.error or "")[:400])


if __name__ == "__main__":
    main()
