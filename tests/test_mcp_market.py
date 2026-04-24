from __future__ import annotations

import unittest
from unittest.mock import patch

from oclaw.runtime.tools.mcp.market import infer_install_template, search_mcp_market, trending_mcp_market


class McpMarketTests(unittest.TestCase):
    @patch("oclaw.runtime.tools.mcp.market.search_github_repos")
    @patch("oclaw.runtime.tools.mcp.market.search_npm_packages")
    @patch("oclaw.runtime.tools.mcp.market.search_pypi_packages")
    def test_aggregate_results(self, pypi_mock, npm_mock, gh_mock) -> None:
        gh_mock.return_value = [{"source_type": "github", "name": "a"}]
        npm_mock.return_value = [{"source_type": "npm", "name": "b"}]
        pypi_mock.return_value = [{"source_type": "pypi", "name": "c"}]
        rows = search_mcp_market("demo", per_source_limit=3)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["source_type"], "github")
        self.assertEqual(rows[1]["source_type"], "npm")
        self.assertEqual(rows[2]["source_type"], "pypi")

    def test_infer_install_template(self) -> None:
        t1 = infer_install_template("npm", "@acme/mcp-demo")
        self.assertEqual(t1["entry_command"], "npx")
        self.assertTrue(isinstance(t1["entry_args"], list))
        t2 = infer_install_template("pypi", "mcp-demo")
        self.assertEqual(t2["entry_command"], "python")
        self.assertEqual(t2["entry_args"][:1], ["-m"])

    @patch("oclaw.runtime.tools.mcp.market.search_mcp_market")
    def test_trending_cache(self, search_mock) -> None:
        search_mock.return_value = [{"source_type": "github", "name": "a", "stars": 9}]
        rows = trending_mcp_market(force_refresh=True, per_source_limit=2)
        self.assertEqual(len(rows), 1)
        rows2 = trending_mcp_market(force_refresh=False, per_source_limit=2)
        self.assertEqual(len(rows2), 1)


if __name__ == "__main__":
    unittest.main()

