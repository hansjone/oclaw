from __future__ import annotations

from pathlib import Path

import oclaw.runtime.operations.main as ops_main


def test_gateway_start_uses_fastapi_only(monkeypatch) -> None:
    called: dict[str, bool] = {"ok": False}

    def fake_fastapi_main() -> int:
        called["ok"] = True
        return 0

    monkeypatch.setattr("oclaw.interfaces.http.fastapi_app.main", fake_fastapi_main)
    rc = ops_main(["gateway", "start", "--host", "127.0.0.1", "--port", "8799"])
    assert rc == 0
    assert called["ok"] is True


def test_gateway_start_rejects_removed_impl_flag() -> None:
    try:
        ops_main(["gateway", "start", "--impl", "httpserver"])
    except SystemExit as exc:
        assert int(exc.code) != 0
    else:
        raise AssertionError("expected argparse to reject removed --impl flag")


def test_memory_daily_generates_run_file(tmp_path: Path) -> None:
    base = tmp_path / "memory-system"
    rc = ops_main(
        [
            "memory",
            "daily",
            "--base-dir",
            str(base),
            "--date",
            "2026-04-21",
            "--review-backlog",
            "35",
        ]
    )
    assert rc == 0
    out = base / "runs" / "daily-2026-04-21.md"
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "Daily Memory Run (2026-04-21)" in text
    assert "Suggested new cards today" in text


def test_memory_weekly_generates_run_file(tmp_path: Path) -> None:
    base = tmp_path / "memory-system"
    rc = ops_main(
        [
            "memory",
            "weekly",
            "--base-dir",
            str(base),
            "--date",
            "2026-04-21",
            "--review-backlog",
            "0",
        ]
    )
    assert rc == 0
    out = base / "runs" / "weekly-2026-W17.md"
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "Weekly Memory Review (2026-W17)" in text
    assert "Auto Focus for Next Week" in text
