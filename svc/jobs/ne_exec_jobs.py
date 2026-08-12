"""Background jobs for long execManagedNe batches (oclaw-side, disk + thread)."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from svc.config.paths import PROJECT_ROOT

_STATUS_RUNNING = "running"
_STATUS_SUCCEEDED = "succeeded"
_STATUS_FAILED = "failed"
_STATUS_TIMEOUT = "timeout"
_TERMINAL = {_STATUS_SUCCEEDED, _STATUS_FAILED, _STATUS_TIMEOUT}
_LOCK = threading.Lock()
_INFLIGHT = 0
_MAX_CONCURRENT = 3
_DEFAULT_TIMEOUT_S = 900


def _jobs_dir() -> Path:
    override = str(os.getenv("AIA_NE_EXEC_JOB_DIR") or "").strip()
    if override:
        p = Path(override).expanduser().resolve()
    else:
        data = (Path(PROJECT_ROOT) / "data").resolve()
        nested = (Path(PROJECT_ROOT) / "oclaw" / "data").resolve()
        root = nested if nested.exists() else data
        p = (root / "ne_exec_jobs").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _job_path(job_id: str) -> Path:
    return _jobs_dir() / f"{job_id}.json"


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")
    tmp.replace(path)


def _read_job(job_id: str) -> dict[str, Any] | None:
    path = _job_path(job_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _write_job(job: dict[str, Any]) -> None:
    jid = str(job.get("job_id") or "").strip()
    if not jid:
        return
    _atomic_write(_job_path(jid), job)


def _env_int(name: str, default: int, *, min_v: int, max_v: int) -> int:
    raw = str(os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        n = int(raw)
    except Exception:
        return default
    return max(min_v, min(int(n), max_v))


def async_min_ne_count() -> int:
    """Auto-async when batch NE count >= this (set 0 to disable auto; explicit async=true still works)."""
    return _env_int("AIA_EXEC_MANAGED_NE_ASYNC_MIN_NES", 4, min_v=0, max_v=50)


def count_exec_ne_targets(args: dict[str, Any] | None) -> int:
    a = args if isinstance(args, dict) else {}
    n = 0
    for key in ("ne_ids", "ume_ne_ids"):
        val = a.get(key)
        if isinstance(val, list):
            n = max(n, len([x for x in val if str(x or "").strip()]))
    targets = a.get("targets")
    if isinstance(targets, list):
        n = max(n, len([t for t in targets if isinstance(t, dict)]))
    if n == 0 and (str(a.get("ne_id") or "").strip() or str(a.get("ume_ne_id") or "").strip()):
        return 1
    return int(n)


def _truthy_async_flag(raw: Any) -> bool | None:
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    text = str(raw).strip().lower()
    if not text:
        return None
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return None


def should_run_exec_managed_ne_async(args: dict[str, Any] | None) -> bool:
    a = dict(args or {})
    flag = _truthy_async_flag(a.get("async"))
    if flag is False:
        return False
    if flag is True:
        return True
    min_n = async_min_ne_count()
    if min_n <= 0:
        return False
    return count_exec_ne_targets(a) >= int(min_n)


def strip_async_flag(args: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(args or {})
    out.pop("async", None)
    return out


def start_ne_exec_job(
    *,
    tool_name: str,
    arguments: dict[str, Any],
    runner: Callable[[], dict[str, Any]],
    session_id: str = "",
    timeout_s: int | None = None,
) -> dict[str, Any]:
    """Start background runner; returns immediate ack with job_id."""
    global _INFLIGHT
    with _LOCK:
        if _INFLIGHT >= _MAX_CONCURRENT:
            return {
                "ok": False,
                "error_code": "ne_exec_job_busy",
                "error": "ne_exec_job_busy",
                "hint": (
                    f"Too many concurrent NE exec jobs (max {_MAX_CONCURRENT}). "
                    "Poll get_ne_exec_job for running jobs or shrink the batch."
                ),
            }
        _INFLIGHT += 1

    job_id = uuid.uuid4().hex
    timeout = int(timeout_s) if timeout_s is not None else _DEFAULT_TIMEOUT_S
    timeout = max(60, min(timeout, 1800))
    now = int(time.time() * 1000)
    job = {
        "job_id": job_id,
        "status": _STATUS_RUNNING,
        "tool_name": str(tool_name or ""),
        "session_id": str(session_id or ""),
        "arguments": dict(arguments or {}),
        "ne_count": count_exec_ne_targets(arguments),
        "created_at_ms": now,
        "updated_at_ms": now,
        "timeout_s": timeout,
        "result": None,
        "error": "",
    }
    _write_job(job)

    def _worker() -> None:
        global _INFLIGHT
        started = time.time()
        try:
            result = runner()
            if not isinstance(result, dict):
                result = {"ok": False, "error": "invalid_runner_result", "payload_type": type(result).__name__}
            status = _STATUS_SUCCEEDED if result.get("ok") is not False else _STATUS_FAILED
            if time.time() - started > timeout:
                status = _STATUS_TIMEOUT
            cur = _read_job(job_id) or job
            cur.update(
                {
                    "status": status,
                    "updated_at_ms": int(time.time() * 1000),
                    "result": result,
                    "error": str(result.get("error") or "") if status != _STATUS_SUCCEEDED else "",
                    "duration_ms": int((time.time() - started) * 1000),
                }
            )
            _write_job(cur)
        except Exception as exc:
            cur = _read_job(job_id) or job
            cur.update(
                {
                    "status": _STATUS_FAILED,
                    "updated_at_ms": int(time.time() * 1000),
                    "error": f"{type(exc).__name__}: {exc}",
                    "result": {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                    "duration_ms": int((time.time() - started) * 1000),
                }
            )
            _write_job(cur)
        finally:
            with _LOCK:
                _INFLIGHT = max(0, _INFLIGHT - 1)

    threading.Thread(target=_worker, name=f"ne-exec-{job_id[:8]}", daemon=True).start()
    return {
        "ok": True,
        "async": True,
        "status": _STATUS_RUNNING,
        "job_id": job_id,
        "ne_count": int(job["ne_count"]),
        "poll_tool": "get_ne_exec_job",
        "hint": (
            f"execManagedNe started in background (job_id={job_id}, ne_count={job['ne_count']}). "
            "Tell the user the job_id and end the turn; later call get_ne_exec_job(job_id=...) "
            "or ask the user to continue. Do not sleep/busy-wait in this turn."
        ),
        "example_poll": {"job_id": job_id},
    }


def get_ne_exec_job(job_id: str) -> dict[str, Any]:
    jid = str(job_id or "").strip()
    if not jid:
        return {"ok": False, "error_code": "job_id_required", "error": "job_id_required"}
    job = _read_job(jid)
    if not job:
        return {"ok": False, "error_code": "job_not_found", "error": "job_not_found", "job_id": jid}
    status = str(job.get("status") or "")
    out: dict[str, Any] = {
        "ok": True,
        "job_id": jid,
        "status": status,
        "tool_name": job.get("tool_name"),
        "ne_count": job.get("ne_count"),
        "created_at_ms": job.get("created_at_ms"),
        "updated_at_ms": job.get("updated_at_ms"),
        "duration_ms": job.get("duration_ms"),
        "terminal": status in _TERMINAL,
    }
    if status in _TERMINAL:
        out["result"] = job.get("result")
        if job.get("error"):
            out["error"] = job.get("error")
    else:
        out["hint"] = "Still running; poll get_ne_exec_job again later or ask the user to continue."
    return out


__all__ = [
    "async_min_ne_count",
    "count_exec_ne_targets",
    "get_ne_exec_job",
    "should_run_exec_managed_ne_async",
    "start_ne_exec_job",
    "strip_async_flag",
]
