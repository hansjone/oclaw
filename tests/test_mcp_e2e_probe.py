from __future__ import annotations

import unittest

from oclaw.admin.mcp_e2e_probe import build_mcp_e2e_probe_plans, parse_mcp_bound_tool_name
from oclaw.tools.base import ToolRegistry, ToolSpec


class McpE2eProbeTests(unittest.TestCase):
    def test_parse_mcp_bound_tool_name(self) -> None:
        self.assertEqual(parse_mcp_bound_tool_name("mcp__srv__ping"), ("srv", "ping"))
        self.assertIsNone(parse_mcp_bound_tool_name("read_file"))
        self.assertIsNone(parse_mcp_bound_tool_name("mcp__only"))

    def test_build_plans_empty_registry(self) -> None:
        reg = ToolRegistry([])
        plans, skipped = build_mcp_e2e_probe_plans(reg, workspace_root="/tmp")
        self.assertEqual(plans, [])
        self.assertEqual(skipped, [])

    def test_build_one_probe_per_server(self) -> None:
        def _h(_a):
            return {"ok": True}

        reg = ToolRegistry(
            [
                ToolSpec(
                    name="mcp__alpha__zebra",
                    description="z",
                    parameters={"type": "object", "properties": {}, "required": []},
                    handler=_h,
                    tags=frozenset({"mcp"}),
                ),
                ToolSpec(
                    name="mcp__alpha__apple",
                    description="a",
                    parameters={"type": "object", "properties": {}, "required": []},
                    handler=_h,
                    tags=frozenset({"mcp"}),
                ),
                ToolSpec(
                    name="mcp__beta__read_graph",
                    description="g",
                    parameters={"type": "object", "properties": {}, "required": []},
                    handler=_h,
                    tags=frozenset({"mcp"}),
                ),
            ]
        )
        plans, skipped = build_mcp_e2e_probe_plans(reg, workspace_root="/tmp")
        self.assertEqual(skipped, [])
        self.assertEqual(len(plans), 2)
        by_sid = {p[0]: p for p in plans}
        self.assertIn("alpha", by_sid)
        self.assertIn("beta", by_sid)
        # read_graph wins priority over apple/zebra for beta
        self.assertEqual(by_sid["beta"][1], "mcp__beta__read_graph")
        # alpha: apple before zebra lexicographically among equal priority
        self.assertEqual(by_sid["alpha"][1], "mcp__alpha__apple")


if __name__ == "__main__":
    unittest.main()
