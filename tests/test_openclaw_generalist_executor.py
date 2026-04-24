from __future__ import annotations

import os
from pathlib import Path

from oclaw.agents.factory import build_gateway_executor
from oclaw.platform.persistence.sqlite_store import SqliteStore


def test_build_gateway_executor_defaults_to_generalist(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    ex = build_gateway_executor(store, lang="zh")
    assert type(ex).__name__ == "Agent"
    assert hasattr(ex, "tools")
    assert hasattr(ex, "model")


def test_build_gateway_executor_generalist_run_command_is_disabled_by_default(tmp_path: Path) -> None:
    os.environ.pop("AIA_ENABLE_RUN_COMMAND", None)
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    ex = build_gateway_executor(store, lang="zh", specialist="generalist")
    run_tool = next((t for t in ex.tools.list() if t.name == "run_command"), None)
    assert run_tool is not None
    out = run_tool.handler({"command": "echo hi"})
    assert isinstance(out, dict)
    assert out.get("ok") is False
    assert out.get("error") == "disabled"

