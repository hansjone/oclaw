from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from oclaw.platform.config.paths import db_path


def _runtime_file() -> Path:
    return Path(db_path()).resolve().parent / "ops_runtime_state.json"


def _runtime_log_dir() -> Path:
    p = str(os.getenv("AIA_RUNTIME_LOG_DIR") or "").strip()
    if p:
        return Path(p).expanduser().resolve()
    return Path(db_path()).resolve().parent / "logs"


def _read_state() -> dict[str, Any]:
    p = _runtime_file()
    if not p.exists():
        return {"services": {}}
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"services": {}}
    if not isinstance(obj, dict):
        return {"services": {}}
    if not isinstance(obj.get("services"), dict):
        obj["services"] = {}
    return obj


def _write_state(state: dict[str, Any]) -> None:
    p = _runtime_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            out = subprocess.check_output(
                ["tasklist", "/FI", f"PID eq {int(pid)}", "/FO", "CSV", "/NH"],
                stderr=subprocess.DEVNULL,
                text=True,
            )
            text = (out or "").strip().lower()
            return bool(text and "no tasks are running" not in text and "info:" not in text)
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def is_pid_running(pid: int) -> bool:
    return _is_running(int(pid or 0))


def _python_bin() -> str:
    return sys.executable or "python"


def _service_signature(name: str) -> str | None:
    n = str(name or "").strip().lower()
    if n == "gateway":
        return "-m oclaw.runtime.operations gateway start"
    if n == "ui":
        return "-m oclaw.runtime.operations ui start"
    if n.startswith("channel:"):
        ch = n.split(":", 1)[1].strip()
        if ch:
            return f"-m oclaw.runtime.operations channel {ch} start"
    return None


def _find_pids_by_signature(signature: str) -> list[int]:
    sig = str(signature or "").strip().lower()
    if not sig:
        return []
    out: list[int] = []
    if os.name == "nt":
        try:
            raw = subprocess.check_output(
                ["wmic", "process", "where", "name='python.exe'", "get", "ProcessId,CommandLine"],
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except Exception:
            return []
        for line in (raw or "").splitlines():
            txt = line.strip()
            if not txt or txt.lower().startswith("commandline"):
                continue
            parts = txt.rsplit(None, 1)
            if len(parts) != 2:
                continue
            cmd, pid_s = parts[0].strip(), parts[1].strip()
            if not pid_s.isdigit():
                continue
            if sig in cmd.lower():
                out.append(int(pid_s))
        return out
    try:
        raw = subprocess.check_output(
            ["ps", "-eo", "pid=,args="],
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except Exception:
        return []
    for line in (raw or "").splitlines():
        txt = line.strip()
        if not txt:
            continue
        parts = txt.split(None, 1)
        if len(parts) != 2:
            continue
        pid_s, cmd = parts
        if not pid_s.isdigit():
            continue
        if sig in cmd.lower():
            out.append(int(pid_s))
    return out


def _kill_pid_force(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            subprocess.call(["taskkill", "/PID", str(pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.kill(pid, signal.SIGTERM)
        return True
    except Exception:
        return False


def _cleanup_orphan_service_processes(name: str, *, keep_pids: set[int] | None = None) -> list[int]:
    sig = _service_signature(name)
    if not sig:
        return []
    keep = keep_pids or set()
    killed: list[int] = []
    for pid in _find_pids_by_signature(sig):
        if pid in keep:
            continue
        if _kill_pid_force(pid):
            killed.append(pid)
    return killed


def detect_orphan_service_processes(name: str, *, keep_pids: set[int] | None = None) -> list[int]:
    sig = _service_signature(name)
    if not sig:
        return []
    keep = keep_pids or set()
    out: list[int] = []
    for pid in _find_pids_by_signature(sig):
        if pid in keep:
            continue
        out.append(pid)
    return out


def list_service_process_pids(name: str) -> list[int]:
    sig = _service_signature(name)
    if not sig:
        return []
    return sorted(int(x) for x in _find_pids_by_signature(sig) if int(x) > 0)


def list_listen_ports_for_pid(pid: int) -> list[int]:
    p = int(pid or 0)
    if p <= 0:
        return []
    ports: set[int] = set()
    if os.name == "nt":
        try:
            raw = subprocess.check_output(
                ["netstat", "-ano", "-p", "tcp"],
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except Exception:
            return []
        for line in (raw or "").splitlines():
            txt = " ".join(str(line or "").strip().split())
            if not txt or not txt.lower().startswith("tcp "):
                continue
            parts = txt.split(" ")
            if len(parts) < 5:
                continue
            local_addr = parts[1]
            state = parts[3].strip().upper()
            pid_s = parts[4].strip()
            if pid_s != str(p):
                continue
            if state != "LISTENING":
                continue
            sep = local_addr.rfind(":")
            if sep < 0:
                continue
            port_s = local_addr[sep + 1 :].strip().strip("]")
            if port_s.isdigit():
                ports.add(int(port_s))
        return sorted(ports)
    try:
        raw = subprocess.check_output(
            ["ss", "-ltnp"],
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except Exception:
        return []
    for line in (raw or "").splitlines():
        txt = " ".join(str(line or "").strip().split())
        if not txt or "LISTEN" not in txt:
            continue
        if f"pid={p}," not in txt and f"pid={p})" not in txt:
            continue
        parts = txt.split(" ")
        if len(parts) < 4:
            continue
        local_addr = parts[3]
        sep = local_addr.rfind(":")
        if sep < 0:
            continue
        port_s = local_addr[sep + 1 :].strip().strip("]")
        if port_s.isdigit():
            ports.add(int(port_s))
    return sorted(ports)


def cleanup_orphan_service_processes(name: str, *, keep_pids: set[int] | None = None) -> list[int]:
    return _cleanup_orphan_service_processes(name, keep_pids=keep_pids)


def cleanup_service_processes_by_pid(name: str, pids: list[int] | tuple[int, ...] | set[int]) -> list[int]:
    sig = _service_signature(name)
    if not sig:
        return []
    target = {int(x) for x in (pids or []) if int(x) > 0}
    if not target:
        return []
    live = set(_find_pids_by_signature(sig))
    victims = sorted([x for x in target if x in live])
    killed: list[int] = []
    for pid in victims:
        if _kill_pid_force(pid):
            killed.append(int(pid))
    return killed


@dataclass(frozen=True)
class ServiceState:
    name: str
    pid: int
    command: list[str]
    running: bool


def start_service(*, name: str, command: list[str], env: dict[str, str] | None = None, cwd: str | None = None) -> int:
    state = _read_state()
    services = state.setdefault("services", {})
    existing = services.get(name)
    if isinstance(existing, dict):
        pid = int(existing.get("pid") or 0)
        if _is_running(pid):
            # Keep recorded primary pid, kill only duplicate peers.
            _cleanup_orphan_service_processes(name, keep_pids={pid})
            return pid
    # No stable primary pid: kill all matching peers and restart cleanly.
    _cleanup_orphan_service_processes(name)
    merged_env = os.environ.copy()
    if env:
        merged_env.update({str(k): str(v) for k, v in env.items()})
    merged_env.setdefault("PYTHONUNBUFFERED", "1")
    log_dir = _runtime_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    safe_name = str(name).replace(":", "_").replace("/", "_").replace("\\", "_")
    stdout_path = log_dir / f"{safe_name}.out.log"
    stderr_path = log_dir / f"{safe_name}.err.log"
    stdout_fh = open(stdout_path, "ab")
    stderr_fh = open(stderr_path, "ab")
    kwargs: dict[str, Any] = {
        "env": merged_env,
        "cwd": cwd or str(Path.cwd()),
        "stdin": subprocess.DEVNULL,
        "stdout": stdout_fh,
        "stderr": stderr_fh,
    }
    if os.name == "nt":
        create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        create_detached = getattr(subprocess, "DETACHED_PROCESS", 0)
        create_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        kwargs["creationflags"] = create_group | create_detached | create_no_window
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        kwargs["startupinfo"] = startupinfo
    else:
        kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen(command, **kwargs)
    finally:
        try:
            stdout_fh.close()
        except Exception:
            pass
        try:
            stderr_fh.close()
        except Exception:
            pass
    services[name] = {
        "pid": int(proc.pid),
        "command": command,
        "stdout_log": str(stdout_path),
        "stderr_log": str(stderr_path),
    }
    _write_state(state)
    return int(proc.pid)


def status_services() -> list[ServiceState]:
    state = _read_state()
    services = state.get("services")
    if not isinstance(services, dict):
        services = {}
        state["services"] = services
    # Reconcile state-file PIDs with live processes by command signature.
    # This prevents false "missing service" reports when cwd/env drift starts
    # services successfully but runtime state was written from another context.
    changed = False
    known_names: list[str] = []
    for n in services.keys():
        nn = str(n or "").strip()
        if nn and nn not in known_names:
            known_names.append(nn)
    for n in ("gateway", "channel:wecom"):
        if n not in known_names:
            known_names.append(n)
    out: list[ServiceState] = []
    for name in known_names:
        meta = services.get(name)
        if not isinstance(meta, dict):
            meta = {}
        pid = int(meta.get("pid") or 0)
        running = _is_running(pid)
        cmd = meta.get("command") if isinstance(meta.get("command"), list) else []
        if not running:
            sig = _service_signature(str(name))
            pids = _find_pids_by_signature(sig) if sig else []
            # Safe reconcile only when exactly one candidate exists.
            # If multiple workers exist, avoid guessing a primary pid.
            if len(pids) == 1:
                pid = int(sorted(pids)[0])
                running = _is_running(pid)
                if running and int(meta.get("pid") or 0) != pid:
                    services[str(name)] = {
                        "pid": int(pid),
                        "command": cmd,
                        "stdout_log": str(meta.get("stdout_log") or ""),
                        "stderr_log": str(meta.get("stderr_log") or ""),
                    }
                    changed = True
        out.append(ServiceState(name=str(name), pid=pid, command=[str(x) for x in cmd], running=running))
    if changed:
        _write_state(state)
    return out


def stop_service(name: str) -> bool:
    state = _read_state()
    services = state.get("services")
    if not isinstance(services, dict):
        return False
    meta = services.get(name)
    if not isinstance(meta, dict):
        return False
    pid = int(meta.get("pid") or 0)
    ok = False
    if _is_running(pid):
        ok = _kill_pid_force(pid)
    services.pop(name, None)
    _write_state(state)
    orphan_killed = _cleanup_orphan_service_processes(name, keep_pids={pid})
    return bool(ok or orphan_killed)


def stop_all() -> list[str]:
    stopped: list[str] = []
    for s in status_services():
        if stop_service(s.name):
            stopped.append(s.name)
    return stopped


def default_python_command(args: list[str]) -> list[str]:
    return [_python_bin(), *args]

