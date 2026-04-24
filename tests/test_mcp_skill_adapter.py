from __future__ import annotations

from oclaw.runtime.tools.mcp.adapter import materialize_mcp_skills_for_specialist


class _Store:
    def get_setting(self, key: str) -> str:  # noqa: ARG002
        return ""

    def list_mcp_servers(self, enabled_only: bool = True):  # noqa: ARG002
        return [
            {
                "server_id": "fs",
                "entry_command": "python",
                "entry_args": ["-m", "x"],
                "timeout_s": 10.0,
                "required_permissions": [],
            }
        ]

    def list_mcp_server_tools(self, server_id: str):  # noqa: ARG002
        return [{"tool_name": "read", "description": "read", "parameters": {"type": "object", "properties": {}}}]


def test_materialize_mcp_skills_for_specialist() -> None:
    rows = materialize_mcp_skills_for_specialist(_Store(), specialist="generalist")
    assert len(rows) == 1
    assert rows[0].name == "mcp__fs__read"
    assert rows[0].origin == "mcp"

