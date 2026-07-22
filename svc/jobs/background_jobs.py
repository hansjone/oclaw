from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

from svc.config.paths import PROJECT_ROOT

DEFAULT_TIMEOUT_S = 7200  # 2 hours
MAX_TIMEOUT_S = 10800  # 3 hours
MAX_CONCURRENT_RUNNING = 4
_REAPER_INTERVAL_S = 15
_META_NAME = "meta.json"
_STDOUT_NAME = "stdout.log"
_STDERR_NAME = "stderr.log"
_STATUS_RUNNING = "running"
_STATUS_SUCCEEDED = "succeeded"
_STATUS_FAILED = "failed"
_STATUS_TIMEOUT = "timeout"
_STATUS_CANCELLED = "cancelled"
_TERMINAL = {_STATUS_SUCCEEDED, _STATUS_FAILED, _STATUS_TIMEOUT, _STATUS_CANCELLED}


def jobs_dir() -> Path:
    override = str(os.getenv("AIA_JOBS_DIR") or os.getenv("OPS_JOBS_DIR") or "").strip()
    if override:
        p = Path(override).expanduser().resolve()
    else:
        # Prefer data/jobs under project data root.
        data = (Path(PROJECT_ROOT) / "data").resolve()
        nested = (Path(PROJECT_ROOT) / "oclaw" / "data").resolve()
        root = nested if nested.exists() else data
        p = (root / "jobs").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _utc_ts() -> int:
    return int(time.time())


def _clamp_timeout(raw: Any) -> int:
    try:
        val = int(raw)
    except Exception:
        val = DEFAULT_TIMEOUT_S
    return max(1, min(val, MAX_TIMEOUT_S))


def is_shell_exec_enabled() -> tuple[bool, str]:
    """Same gate as run_command (Admin tool policy / AIA_ENABLE_RUN_COMMAND)."""

    def _truthy(v: str | None) -> bool:
        return str(v or "").strip().lower() in {"1", "true", "yes", "on"}

    try:
        enabled: bool | None = None
        dbp = str(os.getenv("OPS_ASSISTANT_DB_PATH") or "").strip()
        try:
            if not dbp:
                from svc.config.paths import db_path

                dbp = str(db_path() or "").strip()
        except Exception:
            dbp = ""
        if dbp:
            try:
                from svc.persistence.sqlite_store import SqliteStore

                raw_db = str(SqliteStore(dbp).get_setting("AIA_ENABLE_RUN_COMMAND") or "").strip()
                if raw_db:
                    enabled = _truthy(raw_db)
            except Exception:
                enabled = None
        if enabled is None:
            raw_env = str(os.getenv("AIA_ENABLE_RUN_COMMAND") or "").strip()
            enabled = _truthy(raw_env) if raw_env else False
        if enabled:
            return True, ""
        return (
            False,
            "run_command/start_job is off: enable AIA_ENABLE_RUN_COMMAND in Admin → Tool policy "
            "or set env AIA_ENABLE_RUN_COMMAND=1.",
        )
    except Exception:
        return False, "shell_exec_gate_failed"


@dataclass
class JobMeta:
    job_id: str
    command: str
    cwd: str
    status: str
    created_at: int
    timeout_s: int
    name: str = ""
    pid: int | None = None
    started_at: int | None = None
    finished_at: int | None = None
    exit_code: int | None = None
    error: str | None = None
    # Optional channel ping when job ends (agent turn may already be gone).
    notify: dict[str, Any] | None = None
    notify_result: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "JobMeta":
        notify = d.get("notify") if isinstance(d.get("notify"), dict) else None
        notify_result = d.get("notify_result") if isinstance(d.get("notify_result"), dict) else None
        return JobMeta(
            job_id=str(d.get("job_id") or ""),
            command=str(d.get("command") or ""),
            cwd=str(d.get("cwd") or ""),
            status=str(d.get("status") or ""),
            created_at=int(d.get("created_at") or 0),
            timeout_s=int(d.get("timeout_s") or DEFAULT_TIMEOUT_S),
            name=str(d.get("name") or ""),
            pid=int(d["pid"]) if d.get("pid") is not None else None,
            started_at=int(d["started_at"]) if d.get("started_at") is not None else None,
            finished_at=int(d["finished_at"]) if d.get("finished_at") is not None else None,
            exit_code=int(d["exit_code"]) if d.get("exit_code") is not None else None,
            error=str(d["error"]) if d.get("error") is not None else None,
            notify=notify,
            notify_result=notify_result,
        )


class BackgroundJobStore:
    """Disk-backed background shell jobs for long-running agent scripts."""

    def __init__(self, root_dir: str | Path | None = None, *, enable_reaper: bool = False):
        self.root = Path(root_dir) if root_dir is not None else jobs_dir()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._watchers: dict[str, threading.Thread] = {}
        self._procs: dict[str, subprocess.Popen[Any]] = {}
        self._log_handles: dict[str, tuple[Any, Any]] = {}
        self._reaper_stop = threading.Event()
        self._reaper_thread: threading.Thread | None = None
        if enable_reaper:
            self._ensure_reaper()

    def _ensure_reaper(self) -> None:
        if self._reaper_thread is not None and self._reaper_thread.is_alive():
            return
        self._reaper_stop.clear()
        t = threading.Thread(target=self._reaper_loop, name="oclaw-job-reaper", daemon=True)
        self._reaper_thread = t
        t.start()

    def _reaper_loop(self) -> None:
        # First pass soon after boot so dirty metas from a prior crash are cleared.
        try:
            self.reap()
        except Exception:
            pass
        while not self._reaper_stop.wait(_REAPER_INTERVAL_S):
            try:
                self.reap()
            except Exception:
                pass

    def reap(self) -> dict[str, Any]:
        """Reconcile all running jobs (timeout / dead pid). Safe to call anytime."""
        scanned = 0
        changed = 0
        if not self.root.exists():
            return {"ok": True, "scanned": 0, "changed": 0}
        for p in list(self.root.iterdir()):
            if not p.is_dir():
                continue
            meta = self._read_meta(p.name)
            if meta is None or meta.status != _STATUS_RUNNING:
                continue
            scanned += 1
            before = meta.status
            after = self._reconcile(meta)
            if after.status != before:
                changed += 1
        return {"ok": True, "scanned": scanned, "changed": changed}

    def _job_dir(self, job_id: str) -> Path:
        return self.root / job_id

    def _meta_path(self, job_id: str) -> Path:
        return self._job_dir(job_id) / _META_NAME

    def _read_meta(self, job_id: str) -> Optional[JobMeta]:
        mp = self._meta_path(job_id)
        if not mp.exists():
            return None
        try:
            obj = json.loads(mp.read_text(encoding="utf-8"))
            if not isinstance(obj, dict):
                return None
            return JobMeta.from_dict(obj)
        except Exception:
            return None

    def _write_meta(self, meta: JobMeta) -> None:
        d = self._job_dir(meta.job_id)
        d.mkdir(parents=True, exist_ok=True)
        tmp = self._meta_path(meta.job_id).with_suffix(".tmp")
        tmp.write_text(json.dumps(meta.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self._meta_path(meta.job_id))

    def _count_running(self) -> int:
        """Count live running jobs after reconciling stale metas."""
        n = 0
        if not self.root.exists():
            return 0
        for p in list(self.root.iterdir()):
            if not p.is_dir():
                continue
            meta = self._read_meta(p.name)
            if meta is None:
                continue
            if meta.status == _STATUS_RUNNING:
                meta = self._reconcile(meta)
            if meta.status == _STATUS_RUNNING:
                n += 1
        return n

    def _pid_alive(self, pid: int | None) -> bool:
        if not pid or pid <= 0:
            return False
        try:
            if os.name == "nt":
                out = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                return str(pid) in (out.stdout or "")
            os.kill(pid, 0)
            return True
        except Exception:
            return False

    def _kill_tree(self, pid: int | None) -> None:
        if not pid or pid <= 0:
            return
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            else:
                try:
                    os.killpg(pid, signal.SIGKILL)
                except Exception:
                    os.kill(pid, signal.SIGKILL)
        except Exception:
            pass

    def _close_logs(self, job_id: str) -> None:
        handles = self._log_handles.pop(job_id, None)
        if not handles:
            return
        for h in handles:
            try:
                h.close()
            except Exception:
                pass

    def _finalize(
        self,
        job_id: str,
        *,
        status: str,
        exit_code: int | None,
        error: str | None = None,
        force: bool = False,
    ) -> JobMeta | None:
        with self._lock:
            meta = self._read_meta(job_id)
            if meta is None:
                self._close_logs(job_id)
                self._procs.pop(job_id, None)
                return None
            if meta.status in _TERMINAL:
                # Cancel may race the watcher (kill → non-zero exit → failed).
                # Allow an intentional cancel to override a just-recorded failed/timeout.
                if not (
                    force
                    and status == _STATUS_CANCELLED
                    and meta.status in {_STATUS_FAILED, _STATUS_TIMEOUT}
                ):
                    self._close_logs(job_id)
                    self._procs.pop(job_id, None)
                    return meta
            meta.status = status
            meta.exit_code = exit_code
            meta.finished_at = _utc_ts()
            if error:
                meta.error = error
            elif force and status == _STATUS_CANCELLED:
                meta.error = "cancelled_by_user"
            self._write_meta(meta)
            self._close_logs(job_id)
            self._procs.pop(job_id, None)
            self._watchers.pop(job_id, None)
        # Notify outside the lock (may hit SQLite / network).
        self._notify_complete(job_id)
        return self._read_meta(job_id)

    def _notify_complete(self, job_id: str) -> None:
        meta = self._read_meta(job_id)
        if meta is None or not meta.notify or meta.notify_result:
            return
        notify = dict(meta.notify)
        channel = str(notify.get("channel") or "").strip().lower()
        chat_id = str(notify.get("chat_id") or "").strip()
        if not channel or not chat_id:
            meta.notify_result = {"ok": False, "error": "notify_channel_or_chat_id_missing"}
            self._write_meta(meta)
            return
        if channel in {"wechat", "weixin"}:
            channel = "weixin"
        custom = str(notify.get("message") or "").strip()
        text = custom or (
            f"后台任务已结束\n"
            f"job_id={meta.job_id}\n"
            f"name={meta.name}\n"
            f"status={meta.status}\n"
            f"exit_code={meta.exit_code}\n"
            f"可在对话中发送：查任务 {meta.job_id}"
        )
        account_id = str(notify.get("account_id") or "").strip()
        if not account_id and channel == "whatsapp":
            account_id = str(os.getenv("AIA_WHATSAPP_ACCOUNT_ID") or "wa-default").strip()
        tenant_id = str(notify.get("tenant_id") or "").strip()
        try:
            from svc.config.paths import db_path
            from svc.persistence.sqlite_store import SqliteStore

            store = SqliteStore(db_path())
            source_payload = {
                "kind": "background_job_complete",
                "job_id": meta.job_id,
                "status": meta.status,
            }
            ctx = str(notify.get("context_token") or "").strip()
            if ctx:
                source_payload["context_token"] = ctx
            msg_id = store.enqueue_channel_outbound_message(
                channel=channel,
                chat_id=chat_id,
                text=text,
                tenant_id=tenant_id,
                account_id=account_id,
                source=json.dumps(source_payload, ensure_ascii=False),
            )
            meta.notify_result = {"ok": True, "message_id": msg_id, "channel": channel, "chat_id": chat_id}
        except Exception as exc:
            meta.notify_result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        self._write_meta(meta)

    def _watch(self, job_id: str, proc: subprocess.Popen[Any], timeout_s: int) -> None:
        try:
            try:
                code = proc.wait(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                self._kill_tree(proc.pid)
                try:
                    proc.wait(timeout=10)
                except Exception:
                    pass
                self._finalize(job_id, status=_STATUS_TIMEOUT, exit_code=None, error="job_timeout")
                return
            status = _STATUS_SUCCEEDED if int(code) == 0 else _STATUS_FAILED
            self._finalize(job_id, status=status, exit_code=int(code))
        except Exception as exc:
            self._finalize(job_id, status=_STATUS_FAILED, exit_code=None, error=f"{type(exc).__name__}: {exc}")

    def _reconcile(self, meta: JobMeta) -> JobMeta:
        if meta.status != _STATUS_RUNNING:
            return meta
        started = int(meta.started_at or meta.created_at or 0)
        if started and (_utc_ts() - started) > int(meta.timeout_s or DEFAULT_TIMEOUT_S):
            self._kill_tree(meta.pid)
            proc = self._procs.get(meta.job_id)
            if proc is not None:
                try:
                    proc.wait(timeout=5)
                except Exception:
                    pass
            self._finalize(meta.job_id, status=_STATUS_TIMEOUT, exit_code=None, error="job_timeout_reconcile")
            return self._read_meta(meta.job_id) or meta

        proc = self._procs.get(meta.job_id)
        if proc is not None:
            rc = proc.poll()
            if rc is not None:
                status = _STATUS_SUCCEEDED if int(rc) == 0 else _STATUS_FAILED
                self._finalize(meta.job_id, status=status, exit_code=int(rc))
                return self._read_meta(meta.job_id) or meta
            return meta
        # Process not tracked in this process (gateway/agent restart): infer from pid.
        if meta.pid and self._pid_alive(meta.pid):
            # Still running without local watcher — timeout enforced above on later polls.
            return meta
        # Pid gone — mark failed/unknown unless already terminal on disk.
        self._finalize(
            meta.job_id,
            status=_STATUS_FAILED,
            exit_code=None,
            error="process_exited_untracked",
        )
        return self._read_meta(meta.job_id) or meta

    def start(
        self,
        *,
        command: str,
        cwd: str,
        timeout_s: int | None = None,
        name: str = "",
        notify: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cmd = str(command or "").strip()
        if not cmd:
            return {"ok": False, "error": "command_required"}
        notify_clean: dict[str, Any] | None = None
        if isinstance(notify, dict) and notify:
            channel = str(notify.get("channel") or "").strip().lower()
            chat_id = str(notify.get("chat_id") or "").strip()
            if channel and chat_id:
                notify_clean = {
                    "channel": channel,
                    "chat_id": chat_id,
                    "account_id": str(notify.get("account_id") or "").strip(),
                    "tenant_id": str(notify.get("tenant_id") or "").strip(),
                    "context_token": str(notify.get("context_token") or "").strip(),
                    "message": str(notify.get("message") or "").strip(),
                }
        with self._lock:
            if self._count_running() >= MAX_CONCURRENT_RUNNING:
                return {
                    "ok": False,
                    "error": "too_many_running_jobs",
                    "max_concurrent": MAX_CONCURRENT_RUNNING,
                }
            job_id = "job_" + uuid.uuid4().hex[:12]
            timeout = _clamp_timeout(timeout_s if timeout_s is not None else DEFAULT_TIMEOUT_S)
            workdir = str(Path(cwd).resolve())
            Path(workdir).mkdir(parents=True, exist_ok=True)
            jdir = self._job_dir(job_id)
            jdir.mkdir(parents=True, exist_ok=True)
            stdout_path = jdir / _STDOUT_NAME
            stderr_path = jdir / _STDERR_NAME
            stdout_f = open(stdout_path, "w", encoding="utf-8", errors="replace")
            stderr_f = open(stderr_path, "w", encoding="utf-8", errors="replace")
            now = _utc_ts()
            meta = JobMeta(
                job_id=job_id,
                command=cmd,
                cwd=workdir,
                status=_STATUS_RUNNING,
                created_at=now,
                started_at=now,
                timeout_s=timeout,
                name=str(name or "").strip() or job_id,
                notify=notify_clean,
            )
            run_kwargs: dict[str, Any] = {
                "cwd": workdir,
                "shell": True,
                "stdout": stdout_f,
                "stderr": stderr_f,
                "text": True,
            }
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0
                run_kwargs["startupinfo"] = startupinfo
                run_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            else:
                run_kwargs["start_new_session"] = True
            try:
                proc = subprocess.Popen(cmd, **run_kwargs)
            except Exception as exc:
                stdout_f.close()
                stderr_f.close()
                meta.status = _STATUS_FAILED
                meta.finished_at = _utc_ts()
                meta.error = f"{type(exc).__name__}: {exc}"
                self._write_meta(meta)
                return {"ok": False, "error": "spawn_failed", "detail": str(exc), "job": meta.to_dict()}
            meta.pid = int(proc.pid) if proc.pid else None
            self._write_meta(meta)
            self._procs[job_id] = proc
            self._log_handles[job_id] = (stdout_f, stderr_f)
            t = threading.Thread(target=self._watch, args=(job_id, proc, timeout), daemon=True, name=f"job-{job_id}")
            self._watchers[job_id] = t
            t.start()
            return {
                "ok": True,
                "job_id": job_id,
                "status": meta.status,
                "pid": meta.pid,
                "timeout_s": timeout,
                "cwd": workdir,
                "name": meta.name,
                "log_dir": str(jdir),
                "notify": bool(notify_clean),
                "hint": (
                    "Job started in background and will keep running if this agent turn ends. "
                    "Tell the user the job_id, then end the turn (do NOT sleep for hours). "
                    "Later: get_job/list_jobs to resume. Optional notify pings the channel on completion."
                ),
            }

    def get(self, job_id: str, *, log_tail_chars: int = 4000) -> dict[str, Any]:
        aid = str(job_id or "").strip()
        if not aid:
            return {"ok": False, "error": "job_id_required"}
        meta = self._read_meta(aid)
        if meta is None:
            return {"ok": False, "error": "job_not_found", "job_id": aid}
        meta = self._reconcile(meta)
        tail = max(200, min(int(log_tail_chars or 4000), 50000))
        jdir = self._job_dir(aid)

        def _tail(path: Path) -> str:
            if not path.exists():
                return ""
            try:
                data = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                return ""
            if len(data) <= tail:
                return data
            return data[-tail:]

        out = {
            "ok": True,
            "job_id": meta.job_id,
            "name": meta.name,
            "status": meta.status,
            "command": meta.command,
            "cwd": meta.cwd,
            "pid": meta.pid,
            "timeout_s": meta.timeout_s,
            "created_at": meta.created_at,
            "started_at": meta.started_at,
            "finished_at": meta.finished_at,
            "exit_code": meta.exit_code,
            "error": meta.error,
            "log_dir": str(jdir),
            "stdout_tail": _tail(jdir / _STDOUT_NAME),
            "stderr_tail": _tail(jdir / _STDERR_NAME),
            "done": meta.status in _TERMINAL,
            "notify_result": meta.notify_result,
        }
        if not out["done"]:
            out["hint"] = (
                "still running; prefer ending this turn and checking later with get_job. "
                "Short sleep+poll only for near-term completion (minutes), not multi-hour waits."
            )
        return out

    def cancel(self, job_id: str) -> dict[str, Any]:
        aid = str(job_id or "").strip()
        if not aid:
            return {"ok": False, "error": "job_id_required"}
        with self._lock:
            meta = self._read_meta(aid)
            if meta is None:
                return {"ok": False, "error": "job_not_found", "job_id": aid}
            if meta.status in _TERMINAL:
                return {"ok": True, "job_id": aid, "status": meta.status, "already_done": True}
            proc = self._procs.get(aid)
            pid = meta.pid or (proc.pid if proc else None)
            self._kill_tree(pid)
            if proc is not None:
                try:
                    proc.wait(timeout=10)
                except Exception:
                    pass
        # Finalize + notify outside the lock so other start/get/list calls are not blocked.
        self._finalize(
            aid,
            status=_STATUS_CANCELLED,
            exit_code=None,
            error="cancelled_by_user",
            force=True,
        )
        latest = self._read_meta(aid)
        return {"ok": True, "job_id": aid, "status": (latest.status if latest else _STATUS_CANCELLED)}

    def cancel_all_running(self) -> dict[str, Any]:
        listed = self.list_jobs(limit=100)
        cancelled: list[str] = []
        for row in listed.get("jobs") or []:
            if str(row.get("status") or "") != _STATUS_RUNNING:
                continue
            jid = str(row.get("job_id") or "")
            if not jid:
                continue
            out = self.cancel(jid)
            if out.get("ok"):
                cancelled.append(jid)
        return {"ok": True, "cancelled": cancelled, "count": len(cancelled)}

    def purge(self, job_id: str) -> dict[str, Any]:
        """Remove finished job files from disk. Running jobs must be cancelled first."""
        aid = str(job_id or "").strip()
        if not aid:
            return {"ok": False, "error": "job_id_required"}
        with self._lock:
            meta = self._read_meta(aid)
            if meta is None:
                return {"ok": False, "error": "job_not_found", "job_id": aid}
            if meta.status == _STATUS_RUNNING:
                return {"ok": False, "error": "job_still_running", "hint": "cancel first"}
            self._close_logs(aid)
            self._procs.pop(aid, None)
            self._watchers.pop(aid, None)
            jdir = self._job_dir(aid)
            try:
                import shutil

                shutil.rmtree(jdir, ignore_errors=True)
            except Exception as exc:
                return {"ok": False, "error": "purge_failed", "detail": str(exc)}
            return {"ok": True, "job_id": aid, "purged": True}

    def list_jobs(self, *, limit: int = 20) -> dict[str, Any]:
        lim = max(1, min(int(limit or 20), 100))
        items: list[JobMeta] = []
        for p in self.root.iterdir():
            if not p.is_dir():
                continue
            meta = self._read_meta(p.name)
            if meta is None:
                continue
            if meta.status == _STATUS_RUNNING:
                meta = self._reconcile(meta)
            items.append(meta)
        items.sort(key=lambda m: int(m.created_at or 0), reverse=True)
        jobs = []
        for m in items[:lim]:
            cmd = str(m.command or "")
            jobs.append(
                {
                    "job_id": m.job_id,
                    "name": m.name,
                    "status": m.status,
                    "pid": m.pid,
                    "command": cmd if len(cmd) <= 240 else cmd[:237] + "...",
                    "cwd": m.cwd,
                    "created_at": m.created_at,
                    "started_at": m.started_at,
                    "finished_at": m.finished_at,
                    "exit_code": m.exit_code,
                    "timeout_s": m.timeout_s,
                    "error": m.error,
                }
            )
        # Count all running, not only truncated page.
        running_all = sum(1 for m in items if m.status == _STATUS_RUNNING)
        return {
            "ok": True,
            "jobs": jobs,
            "running_count": running_all,
            "total": len(items),
        }


_STORE: BackgroundJobStore | None = None
_STORE_LOCK = threading.Lock()


def get_job_store(root_dir: str | Path | None = None) -> BackgroundJobStore:
    global _STORE
    if root_dir is not None:
        return BackgroundJobStore(root_dir=root_dir, enable_reaper=False)
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = BackgroundJobStore(enable_reaper=True)
        else:
            _STORE._ensure_reaper()
        return _STORE


__all__ = [
    "BackgroundJobStore",
    "DEFAULT_TIMEOUT_S",
    "MAX_TIMEOUT_S",
    "JobMeta",
    "get_job_store",
    "is_shell_exec_enabled",
    "jobs_dir",
]
