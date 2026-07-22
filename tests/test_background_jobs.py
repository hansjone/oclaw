from __future__ import annotations

import json
import sys
import time

from runtime.tools.public.job_tools import cancel_job_tool, get_job_tool, list_jobs_tool, start_job_tool
from runtime.tools.public.sleep_tool import sleep_tool
from svc.jobs.background_jobs import BackgroundJobStore, get_job_store


def test_sleep_bounds() -> None:
    spec = sleep_tool()
    assert spec.handler({"seconds": 0.2}).get("ok") is True
    bad = spec.handler({"seconds": 999})
    assert bad.get("ok") is False
    assert bad.get("error") == "seconds_too_large"


def test_start_and_get_job_succeeds(tmp_path, monkeypatch) -> None:
    store = BackgroundJobStore(root_dir=tmp_path / "jobs")
    monkeypatch.setattr("runtime.tools.public.job_tools.get_job_store", lambda: store)
    monkeypatch.setattr("runtime.tools.public.job_tools.is_shell_exec_enabled", lambda: (True, ""))
    monkeypatch.setattr(
        "runtime.tools.public.job_tools.resolve_workspace_path",
        lambda raw: tmp_path / "ws",
    )
    (tmp_path / "ws").mkdir(parents=True, exist_ok=True)

    py = sys.executable
    started = start_job_tool().handler(
        {
            "command": f'"{py}" -c "print(123); import time; time.sleep(0.3)"',
            "cwd": str(tmp_path / "ws"),
            "timeout_s": 30,
            "name": "quick",
        }
    )
    assert started.get("ok") is True
    job_id = started["job_id"]

    deadline = time.time() + 10
    last = {}
    while time.time() < deadline:
        last = get_job_tool().handler({"job_id": job_id})
        if last.get("done"):
            break
        time.sleep(0.1)
    assert last.get("ok") is True
    assert last.get("status") == "succeeded"
    assert last.get("exit_code") == 0
    assert "123" in str(last.get("stdout_tail") or "")


def test_get_job_timeout(tmp_path, monkeypatch) -> None:
    store = BackgroundJobStore(root_dir=tmp_path / "jobs")
    monkeypatch.setattr("runtime.tools.public.job_tools.get_job_store", lambda: store)
    monkeypatch.setattr("runtime.tools.public.job_tools.is_shell_exec_enabled", lambda: (True, ""))
    monkeypatch.setattr(
        "runtime.tools.public.job_tools.resolve_workspace_path",
        lambda raw: tmp_path / "ws",
    )
    (tmp_path / "ws").mkdir(parents=True, exist_ok=True)

    py = sys.executable
    started = start_job_tool().handler(
        {
            "command": f'"{py}" -c "import time; time.sleep(30)"',
            "timeout_s": 1,
        }
    )
    assert started.get("ok") is True
    job_id = started["job_id"]
    deadline = time.time() + 15
    last = {}
    while time.time() < deadline:
        last = get_job_tool().handler({"job_id": job_id})
        if last.get("done"):
            break
        time.sleep(0.2)
    assert last.get("status") == "timeout"
    assert last.get("done") is True


def test_cancel_job(tmp_path, monkeypatch) -> None:
    store = BackgroundJobStore(root_dir=tmp_path / "jobs")
    monkeypatch.setattr("runtime.tools.public.job_tools.get_job_store", lambda: store)
    monkeypatch.setattr("runtime.tools.public.job_tools.is_shell_exec_enabled", lambda: (True, ""))
    monkeypatch.setattr(
        "runtime.tools.public.job_tools.resolve_workspace_path",
        lambda raw: tmp_path / "ws",
    )
    (tmp_path / "ws").mkdir(parents=True, exist_ok=True)

    py = sys.executable
    started = start_job_tool().handler(
        {"command": f'"{py}" -c "import time; time.sleep(60)"', "timeout_s": 120}
    )
    assert started.get("ok") is True
    job_id = started["job_id"]
    cancelled = cancel_job_tool().handler({"job_id": job_id})
    assert cancelled.get("ok") is True
    got = get_job_tool().handler({"job_id": job_id})
    assert got.get("status") == "cancelled"
    assert got.get("done") is True


def test_start_job_requires_enable_gate(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("runtime.tools.public.job_tools.is_shell_exec_enabled", lambda: (False, "off"))
    monkeypatch.setattr(
        "runtime.tools.public.job_tools.resolve_workspace_path",
        lambda raw: tmp_path,
    )
    out = start_job_tool().handler({"command": "echo hi"})
    assert out.get("ok") is False
    assert out.get("error") == "disabled"


def test_list_jobs(tmp_path, monkeypatch) -> None:
    store = BackgroundJobStore(root_dir=tmp_path / "jobs")
    monkeypatch.setattr("runtime.tools.public.job_tools.get_job_store", lambda: store)
    monkeypatch.setattr("runtime.tools.public.job_tools.is_shell_exec_enabled", lambda: (True, ""))
    monkeypatch.setattr(
        "runtime.tools.public.job_tools.resolve_workspace_path",
        lambda raw: tmp_path / "ws",
    )
    (tmp_path / "ws").mkdir(parents=True, exist_ok=True)
    py = sys.executable
    start_job_tool().handler({"command": f'"{py}" -c "print(1)"', "name": "a"})
    listed = list_jobs_tool().handler({"limit": 5})
    assert listed.get("ok") is True
    assert len(listed.get("jobs") or []) >= 1


def test_reconcile_timeout_for_orphan_meta(tmp_path) -> None:
    store = BackgroundJobStore(root_dir=tmp_path / "jobs")
    job_id = "job_orphan1"
    jdir = tmp_path / "jobs" / job_id
    jdir.mkdir(parents=True)
    meta = {
        "job_id": job_id,
        "command": "sleep 999",
        "cwd": str(tmp_path),
        "status": "running",
        "created_at": int(time.time()) - 100,
        "started_at": int(time.time()) - 100,
        "timeout_s": 1,
        "name": "orphan",
        "pid": 99999999,
    }
    (jdir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (jdir / "stdout.log").write_text("", encoding="utf-8")
    (jdir / "stderr.log").write_text("", encoding="utf-8")
    got = store.get(job_id)
    assert got.get("done") is True
    assert got.get("status") == "timeout"


def test_count_running_reconciles_stale_meta(tmp_path) -> None:
    store = BackgroundJobStore(root_dir=tmp_path / "jobs")
    # Four stale running metas with dead pids would previously block new starts.
    for i in range(4):
        job_id = f"job_stale{i}"
        jdir = tmp_path / "jobs" / job_id
        jdir.mkdir(parents=True)
        meta = {
            "job_id": job_id,
            "command": "sleep 999",
            "cwd": str(tmp_path),
            "status": "running",
            "created_at": int(time.time()) - 10,
            "started_at": int(time.time()) - 10,
            "timeout_s": 7200,
            "name": job_id,
            "pid": 90000000 + i,
        }
        (jdir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        (jdir / "stdout.log").write_text("", encoding="utf-8")
        (jdir / "stderr.log").write_text("", encoding="utf-8")
    assert store._count_running() == 0
    py = sys.executable
    started = store.start(command=f'"{py}" -c "print(1)"', cwd=str(tmp_path), timeout_s=30)
    assert started.get("ok") is True


def test_reap_timeouts_without_get(tmp_path) -> None:
    store = BackgroundJobStore(root_dir=tmp_path / "jobs")
    job_id = "job_reap1"
    jdir = tmp_path / "jobs" / job_id
    jdir.mkdir(parents=True)
    meta = {
        "job_id": job_id,
        "command": "sleep 999",
        "cwd": str(tmp_path),
        "status": "running",
        "created_at": int(time.time()) - 100,
        "started_at": int(time.time()) - 100,
        "timeout_s": 1,
        "name": "reap",
        "pid": 99999998,
    }
    (jdir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (jdir / "stdout.log").write_text("", encoding="utf-8")
    (jdir / "stderr.log").write_text("", encoding="utf-8")
    out = store.reap()
    assert out.get("ok") is True
    assert out.get("changed", 0) >= 1
    got = store._read_meta(job_id)
    assert got is not None
    assert got.status == "timeout"


def test_notify_on_complete(tmp_path, monkeypatch) -> None:
    store = BackgroundJobStore(root_dir=tmp_path / "jobs")
    calls: list[dict] = []

    class _Store:
        def enqueue_channel_outbound_message(self, **kwargs):
            calls.append(kwargs)
            return "msg-1"

    monkeypatch.setattr("svc.config.paths.db_path", lambda: str(tmp_path / "x.sqlite"))
    monkeypatch.setattr("svc.persistence.sqlite_store.SqliteStore", lambda *_a, **_k: _Store())

    py = sys.executable
    started = store.start(
        command=f'"{py}" -c "print(\'ok\')"',
        cwd=str(tmp_path),
        timeout_s=30,
        name="n1",
        notify={"channel": "whatsapp", "chat_id": "628@g.us", "message": "done-test"},
    )
    assert started.get("ok") is True
    job_id = started["job_id"]
    deadline = time.time() + 10
    last = {}
    while time.time() < deadline:
        last = store.get(job_id)
        if last.get("done") and last.get("notify_result"):
            break
        time.sleep(0.1)
    assert last.get("status") == "succeeded"
    assert calls and calls[0]["chat_id"] == "628@g.us"
    assert "done-test" in calls[0]["text"]
    assert (last.get("notify_result") or {}).get("ok") is True
