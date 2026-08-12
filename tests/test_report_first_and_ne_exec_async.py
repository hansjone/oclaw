from __future__ import annotations

import time
from pathlib import Path

from runtime.chat.ops_report_first_guard import (
    maybe_block_cli_before_report,
    report_first_block_payload,
)
from svc.jobs.ne_exec_jobs import (
    count_exec_ne_targets,
    get_ne_exec_job,
    should_run_exec_managed_ne_async,
    start_ne_exec_job,
    strip_async_flag,
)


def test_report_first_blocks_cli_before_report() -> None:
    blocked = maybe_block_cli_before_report(
        tool_name="mcp__netx__execManagedNe",
        intent="fiber_cut",
        store=None,
        session_id="",
        turn_uuid="",
        lang="en",
        local_report_ok=False,
    )
    assert blocked is not None
    assert blocked["error_code"] == "report_first_required"
    assert blocked["next_tool"] == "ume_alarm_xlsx_report"


def test_report_first_allows_after_local_ok() -> None:
    assert (
        maybe_block_cli_before_report(
            tool_name="mcp__netx__listCliTargets",
            intent="offline",
            store=None,
            session_id="s",
            turn_uuid="t",
            local_report_ok=True,
        )
        is None
    )


def test_report_first_ignores_non_report_intents() -> None:
    assert (
        maybe_block_cli_before_report(
            tool_name="mcp__netx__execManagedNe",
            intent="continue",
            store=None,
            session_id="",
            turn_uuid="",
            local_report_ok=False,
        )
        is None
    )


def test_report_first_payload_zh() -> None:
    out = report_first_block_payload(intent="fiber_cut", lang="zh")
    assert "ume_alarm_xlsx_report" in out["hint"]
    assert out["example"].get("mode") == "fiber_cut"


def test_should_async_by_ne_count(monkeypatch) -> None:
    monkeypatch.setenv("AIA_EXEC_MANAGED_NE_ASYNC_MIN_NES", "4")
    assert not should_run_exec_managed_ne_async({"ume_ne_ids": ["a", "b", "c"], "commands": ["show"]})
    assert should_run_exec_managed_ne_async({"ume_ne_ids": ["a", "b", "c", "d"], "commands": ["show"]})
    assert should_run_exec_managed_ne_async({"async": True, "ume_ne_id": "x", "commands": ["show"]})
    assert not should_run_exec_managed_ne_async(
        {"async": False, "ume_ne_ids": ["a", "b", "c", "d", "e"], "commands": ["show"]}
    )


def test_count_and_strip_async() -> None:
    assert count_exec_ne_targets({"targets": [{"ume_ne_id": "1", "commands": ["a"]}, {"ne_id": "2", "commands": ["b"]}]}) == 2
    assert "async" not in strip_async_flag({"async": True, "commands": ["x"]})


def test_ne_exec_job_roundtrip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AIA_NE_EXEC_JOB_DIR", str(tmp_path))

    def _runner() -> dict:
        time.sleep(0.05)
        return {"ok": True, "data": {"results": [1]}}

    ack = start_ne_exec_job(
        tool_name="mcp__netx__execManagedNe",
        arguments={"ume_ne_ids": ["a", "b", "c", "d"], "commands": ["show version"]},
        runner=_runner,
        session_id="sess",
    )
    assert ack["ok"] is True
    assert ack["async"] is True
    jid = ack["job_id"]
    deadline = time.time() + 2.0
    status = ""
    while time.time() < deadline:
        polled = get_ne_exec_job(jid)
        status = str(polled.get("status") or "")
        if status in {"succeeded", "failed", "timeout"}:
            break
        time.sleep(0.05)
    assert status == "succeeded"
    done = get_ne_exec_job(jid)
    assert done["terminal"] is True
    assert done["result"]["ok"] is True
