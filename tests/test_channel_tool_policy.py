from __future__ import annotations

from runtime.tools.catalog import materialize_tool_specs
from runtime.tools.public_registry import clear_public_tool_cache


def test_materialize_tools_respects_user_allow_high_risk_public_tools(monkeypatch) -> None:
    clear_public_tool_cache()
    monkeypatch.delenv("AIA_PUBLIC_TOOLS_ALLOW_HIGH", raising=False)

    class _Store:
        def get_user_workspace_path_allowlist(self, *, tenant_id: str, user_id: str):
            assert tenant_id == "tenant-a"
            assert user_id == "user-a"
            return {"allow_high_risk_public_tools": True}

    names = {
        t.name
        for t in materialize_tool_specs(
            store=_Store(),
            path_policy_tenant_id="tenant-a",
            path_policy_user_id="user-a",
        )
    }
    assert "write_file" in names
    assert "run_command" in names
    assert "save_deliverable_attachment" in names


def test_materialize_tools_blocks_high_risk_without_user_policy(monkeypatch) -> None:
    clear_public_tool_cache()
    monkeypatch.delenv("AIA_PUBLIC_TOOLS_ALLOW_HIGH", raising=False)

    names = {
        t.name
        for t in materialize_tool_specs(
            store=None,
            path_policy_tenant_id="tenant-a",
            path_policy_user_id=None,
        )
    }
    assert "write_file" not in names
    assert "run_command" not in names
    assert "save_deliverable_attachment" in names
