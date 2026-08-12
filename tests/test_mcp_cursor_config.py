from __future__ import annotations

import unittest

from runtime.tools.mcp.cursor_config import (
    build_cursor_mcp_export,
    config_payload_to_upsert_fields,
    parse_cursor_mcp_document,
    registry_row_to_cursor_server,
)


class CursorConfigTests(unittest.TestCase):
    def test_parse_stdio_and_remote(self) -> None:
        items = parse_cursor_mcp_document(
            {
                "mcpServers": {
                    "fetch": {"command": "npx", "args": ["-y", "mcp-fetch-server"], "env": {"A": "1"}},
                    "remote": {
                        "url": "https://example.com/mcp",
                        "headers": {"Authorization": "Bearer ${TOKEN}"},
                    },
                }
            }
        )
        by_id = {x["server_id"]: x for x in items}
        self.assertEqual(by_id["fetch"]["source_type"], "local")
        self.assertEqual(by_id["fetch"]["entry_command"], "npx")
        self.assertEqual(by_id["fetch"]["entry_args"], ["-y", "mcp-fetch-server"])
        self.assertIn("A", by_id["fetch"]["env_schema"])
        self.assertEqual(by_id["remote"]["source_type"], "npm")
        self.assertEqual(by_id["remote"]["source_ref"], "mcp-remote")
        self.assertEqual(by_id["remote"]["entry_command"], "npx")
        self.assertIn("mcp-remote", by_id["remote"]["entry_args"])
        self.assertIn("https://example.com/mcp", by_id["remote"]["entry_args"])
        self.assertIn("TOKEN", by_id["remote"]["env_schema"])

    def test_url_only_without_type_is_remote(self) -> None:
        items = parse_cursor_mcp_document({"mcpServers": {"x": {"url": "https://example.com/sse"}}})
        self.assertEqual(items[0]["source_ref"], "mcp-remote")

    def test_roundtrip_mcp_remote(self) -> None:
        row = {
            "server_id": "web",
            "entry_command": "npx",
            "entry_args": ["-y", "mcp-remote", "https://example.com/sse", "--header", "Authorization: Bearer ${K}"],
            "env_schema": {"K": {"default": "", "type": "string"}},
        }
        cursor = registry_row_to_cursor_server(row)
        self.assertEqual(cursor.get("url"), "https://example.com/sse")
        self.assertEqual((cursor.get("headers") or {}).get("Authorization"), "Bearer ${K}")
        export = build_cursor_mcp_export([row])
        self.assertIn("web", export["mcpServers"])

    def test_config_payload_preserves_mcp_remote(self) -> None:
        existing = {
            "server_id": "web",
            "source_type": "npm",
            "source_ref": "mcp-remote",
            "entry_command": "npx",
            "entry_args": ["-y", "mcp-remote", "https://old.example/sse"],
            "env_schema": {},
            "enabled": True,
            "timeout_s": 30.0,
            "required_permissions": [],
            "risk_level": "high",
            "version": "",
        }
        fields = config_payload_to_upsert_fields(
            {"server_id": "web", "url": "https://new.example/sse", "headers": {"X": "1"}},
            existing=existing,
        )
        self.assertEqual(fields["source_ref"], "mcp-remote")
        self.assertIn("https://new.example/sse", fields["entry_args"])


if __name__ == "__main__":
    unittest.main()
