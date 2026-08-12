from __future__ import annotations

from pathlib import Path

from runtime.application.gateway.ops_short_intent import detect_ops_short_intent
from runtime.chat.tool_runtime import ToolExecutionContext, ToolExecutor, normalize_tool_result
from runtime.tools.base import ToolRegistry, ToolSpec
from runtime.tools.tool_error_hints import classify_tool_failure
from svc.llm.chat_models import LLMToolCall
from svc.persistence.sqlite_store import SqliteStore


def test_classify_schema_and_timeout() -> None:
    assert (
        classify_tool_failure({"ok": False, "error_code": "tool_invalid_arguments", "error": "bad"})
        == "schema_validation"
    )
    assert (
        classify_tool_failure({"ok": False, "error_code": "tool_timeout_or_failed", "error": "timeout"})
        == "timeout"
    )


def test_normalize_stamps_failure_class() -> None:
    out = normalize_tool_result({"ok": False, "error_code": "tool_invalid_arguments", "error": "x"})
    assert out["failure_class"] == "schema_validation"


def test_license_short_intent() -> None:
    assert detect_ops_short_intent("license expiry report") == "license"
    assert detect_ops_short_intent("@bot licence check") == "license"


def test_congestion_short_intent() -> None:
    assert detect_ops_short_intent("bandwidth congestion top") == "congestion"
    assert detect_ops_short_intent("端口忙 拥塞") == "congestion"


def test_identical_failed_retry_blocked_across_rounds(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "retry.sqlite"))
    sess = store.create_session("t")
    calls = {"n": 0}

    def _handler(_args):
        calls["n"] += 1
        return {"ok": False, "error_code": "tool_timeout_or_failed", "error": "timeout"}

    reg = ToolRegistry(
        [
            ToolSpec(
                name="mcp__netx__execManagedNe",
                description="exec",
                parameters={"type": "object", "properties": {"ne_id": {"type": "string"}}},
                handler=_handler,
                read_only=False,
            )
        ]
    )
    ctx = ToolExecutionContext(
        store=store,
        tools=reg,
        session_id=sess.id,
        turn_uuid="turn-retry-1",
        lang="en",
    )
    uses = [LLMToolCall(id="c1", name="mcp__netx__execManagedNe", arguments={"ne_id": "ne-1", "commands": ["disp"]})]
    ToolExecutor().execute_tool_uses(ctx=ctx, assistant_msg_id=1, tool_uses=uses, signature_budget=2)
    assert calls["n"] == 1

    uses2 = [LLMToolCall(id="c2", name="mcp__netx__execManagedNe", arguments={"ne_id": "ne-1", "commands": ["disp"]})]
    _, results = ToolExecutor().execute_tool_uses(
        ctx=ctx, assistant_msg_id=2, tool_uses=uses2, signature_budget=2
    )
    blocked, _ = results["c2"]
    assert calls["n"] == 1
    assert blocked.get("error_code") == "identical_retry_blocked"
    assert blocked.get("failure_class") == "retry_guard"


def test_retry_forbidden_blocks_same_tool_different_args(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "scope.sqlite"))
    sess = store.create_session("t")
    calls = {"n": 0}

    def _handler(_args):
        calls["n"] += 1
        return {
            "ok": False,
            "error_code": "insufficient_scope",
            "error": "insufficient_scope:sql:query",
            "retry_forbidden": True,
            "failure_class": "auth",
        }

    reg = ToolRegistry(
        [
            ToolSpec(
                name="mcp__netx__sqlQueryUme",
                description="sql",
                parameters={"type": "object", "properties": {"sql": {"type": "string"}}},
                handler=_handler,
                read_only=True,
            )
        ]
    )
    ctx = ToolExecutionContext(
        store=store,
        tools=reg,
        session_id=sess.id,
        turn_uuid="turn-scope-1",
        lang="en",
    )
    ToolExecutor().execute_tool_uses(
        ctx=ctx,
        assistant_msg_id=1,
        tool_uses=[LLMToolCall(id="c1", name="mcp__netx__sqlQueryUme", arguments={"sql": "select 1"})],
        signature_budget=2,
    )
    assert calls["n"] == 1

    _, results = ToolExecutor().execute_tool_uses(
        ctx=ctx,
        assistant_msg_id=2,
        tool_uses=[LLMToolCall(id="c2", name="mcp__netx__sqlQueryUme", arguments={"sql": "select 2"})],
        signature_budget=2,
    )
    blocked, _ = results["c2"]
    assert calls["n"] == 1
    assert blocked.get("error_code") == "retry_forbidden_blocked"
    assert blocked.get("retry_forbidden") is True


def test_distinct_exec_managed_ne_calls_respect_single_budget(tmp_path: Path, monkeypatch) -> None:
    """Single-NE loops are capped; batch ne_ids remains allowed after the budget."""
    monkeypatch.setenv("AIA_EXEC_MANAGED_NE_SINGLE_BUDGET", "3")
    store = SqliteStore(str(tmp_path / "cli.sqlite"))
    sess = store.create_session("t")
    calls = {"n": 0}

    def _handler(args):
        calls["n"] += 1
        return {"ok": True, "data": {"ne_id": args.get("ne_id") or args.get("ne_ids"), "n": calls["n"]}}

    reg = ToolRegistry(
        [
            ToolSpec(
                name="mcp__netx__execManagedNe",
                description="exec",
                parameters={"type": "object", "properties": {"ne_id": {"type": "string"}}},
                handler=_handler,
                read_only=False,
            )
        ]
    )
    ctx = ToolExecutionContext(
        store=store,
        tools=reg,
        session_id=sess.id,
        turn_uuid="turn-cli-many",
        lang="en",
    )
    for i in range(3):
        ToolExecutor().execute_tool_uses(
            ctx=ctx,
            assistant_msg_id=i + 1,
            tool_uses=[
                LLMToolCall(
                    id=f"c{i}",
                    name="mcp__netx__execManagedNe",
                    arguments={"ne_id": f"ne-{i}", "commands": [f"disp {i}"]},
                )
            ],
            signature_budget=2,
        )
    assert calls["n"] == 3

    _, blocked_results = ToolExecutor().execute_tool_uses(
        ctx=ctx,
        assistant_msg_id=99,
        tool_uses=[
            LLMToolCall(
                id="blocked",
                name="mcp__netx__execManagedNe",
                arguments={"ne_id": "ne-x", "commands": ["disp"]},
            )
        ],
        signature_budget=2,
    )
    blocked, _ = blocked_results["blocked"]
    assert calls["n"] == 3
    assert blocked.get("error_code") == "cli_call_budget_exceeded"

    _, batch_results = ToolExecutor().execute_tool_uses(
        ctx=ctx,
        assistant_msg_id=100,
        tool_uses=[
            LLMToolCall(
                id="batch",
                name="mcp__netx__execManagedNe",
                arguments={"ne_ids": ["a", "b", "c"], "commands": ["show version"]},
            )
        ],
        signature_budget=2,
    )
    batch_out, _ = batch_results["batch"]
    assert calls["n"] == 4
    assert batch_out.get("ok") is True


def test_exec_managed_ne_fail_budget_blocks_further_single(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AIA_EXEC_MANAGED_NE_FAIL_BUDGET", "2")
    monkeypatch.setenv("AIA_EXEC_MANAGED_NE_SINGLE_BUDGET", "10")
    store = SqliteStore(str(tmp_path / "cli-fail.sqlite"))
    sess = store.create_session("t")
    calls = {"n": 0}

    def _handler(_args):
        calls["n"] += 1
        return {"ok": False, "error_code": "tool_timeout_or_failed", "error": "timeout"}

    reg = ToolRegistry(
        [
            ToolSpec(
                name="mcp__netx__execManagedNe",
                description="exec",
                parameters={"type": "object", "properties": {"ne_id": {"type": "string"}}},
                handler=_handler,
                read_only=False,
            )
        ]
    )
    ctx = ToolExecutionContext(
        store=store,
        tools=reg,
        session_id=sess.id,
        turn_uuid="turn-cli-fail",
        lang="en",
    )
    for i in range(2):
        ToolExecutor().execute_tool_uses(
            ctx=ctx,
            assistant_msg_id=i + 1,
            tool_uses=[
                LLMToolCall(
                    id=f"f{i}",
                    name="mcp__netx__execManagedNe",
                    arguments={"ne_id": f"ne-{i}", "commands": ["disp"]},
                )
            ],
            signature_budget=2,
        )
    assert calls["n"] == 2
    _, results = ToolExecutor().execute_tool_uses(
        ctx=ctx,
        assistant_msg_id=9,
        tool_uses=[
            LLMToolCall(
                id="f3",
                name="mcp__netx__execManagedNe",
                arguments={"ne_id": "ne-9", "commands": ["disp"]},
            )
        ],
        signature_budget=2,
    )
    blocked, _ = results["f3"]
    assert calls["n"] == 2
    assert blocked.get("error_code") == "cli_fail_budget_exceeded"
