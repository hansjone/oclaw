from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Optional

from .internal_hooks import HookEvent, HookHandler

log = logging.getLogger("oclaw.hooks")

# Max wall-clock for external hook child processes
_HOOK_SUBPROCESS_TIMEOUT_S = 120.0


def _runner_ts_path() -> Path:
    return Path(__file__).resolve().parent / "ts_hook_runner.ts"


def _runner_js_path() -> Path:
    return Path(__file__).resolve().parent / "js_hook_runner.mjs"


def _is_script_mode(oclaw: dict[str, Any] | None) -> bool:
    o = oclaw or {}
    if o.get("hookMode") == "script":
        return True
    if o.get("nodeScript") is True:
        return True
    return False


def _event_payload(event: HookEvent) -> dict[str, Any]:
    return {
        "type": event.type,
        "action": event.action,
        "sessionKey": event.sessionKey,
        "context": dict(event.context) if isinstance(event.context, dict) else {},
        "messages": list(getattr(event, "messages", []) or []),
        "timestamp": event.timestamp.isoformat() if getattr(event, "timestamp", None) else None,
    }


def _merge_stdout_into_context(event: HookEvent, raw: str) -> None:
    text = (raw or "").strip()
    if not text:
        return
    try:
        out = json.loads(text)
    except Exception:
        log.warning("Hook subprocess stdout is not valid JSON: %r", text[:200])
        return
    if not isinstance(out, dict):
        return
    ctx = out.get("context")
    if isinstance(ctx, dict) and isinstance(event.context, dict):
        event.context.update(ctx)


def _sh_command(script: Path) -> list[str] | None:
    p = str(script)
    if not script.is_file():
        return None
    if os.name == "nt":
        bash = shutil.which("bash")
        if bash:
            return [bash, p]
        wsl = shutil.which("wsl")
        if wsl:
            return [wsl, "bash", p]
        log.warning("Hook .sh on Windows needs bash in PATH (Git for Windows) or wsl. Skipping %s", p)
        return None
    try:
        if script.stat().st_mode & 0o111 and os.access(p, os.X_OK):
            return [p]
    except OSError:
        pass
    sh = shutil.which("sh") or "/bin/sh"
    return [sh, p]


def _tsx_invocation() -> str | None:
    return shutil.which("tsx") or None


def _ts_command(*, script: Path, export_name: str) -> list[str] | None:
    runner = _runner_ts_path()
    if not runner.is_file():
        log.error("oclaw: missing ts hook runner: %s", runner)
        return None
    hp = str(script.resolve())
    rts = str(runner.resolve())
    ex = export_name.strip() or "default"
    tx = _tsx_invocation()
    if tx:
        return [tx, rts, hp, ex]
    npx = shutil.which("npx")
    if npx:
        return [npx, "--yes", "tsx", rts, hp, ex]
    log.warning("Hook .ts needs `tsx` or `npx` (for `npx tsx`) on PATH. Skipping %s", hp)
    return None


def _ts_script_command(*, script: Path) -> list[str] | None:
    """Run .ts as a free script: stdin JSON / stdout JSON (no import runner)."""
    hp = str(script.resolve())
    tx = _tsx_invocation()
    if tx:
        return [tx, hp]
    npx = shutil.which("npx")
    if npx:
        return [npx, "--yes", "tsx", hp]
    log.warning("Hook .ts in script mode needs `tsx` or `npx` on PATH. Skipping %s", hp)
    return None


def _node_path() -> str | None:
    return shutil.which("node") or None


def _js_module_command(*, script: Path, export_name: str) -> list[str] | None:
    node = _node_path()
    if not node:
        log.warning("Hook .mjs / .cjs needs `node` on PATH. Skipping %s", script)
        return None
    runner = _runner_js_path()
    if not runner.is_file():
        log.error("oclaw: missing js hook runner: %s", runner)
        return None
    hp = str(script.resolve())
    rjs = str(runner.resolve())
    ex = export_name.strip() or "default"
    return [node, rjs, hp, ex]


def _js_script_command(*, script: Path) -> list[str] | None:
    node = _node_path()
    if not node:
        return None
    return [node, str(script.resolve())]


async def _run_cmd_handler(
    *,
    cmd: list[str],
    event: HookEvent,
    base_dir: str,
    script: Path,
    log_label: str,
) -> None:
    data = json.dumps(_event_payload(event), default=str)
    env = {**os.environ, "OCLAW_HOOK_DIR": str(Path(base_dir).resolve()), "OCLAW_HOOK_HANDLER": str(script.resolve())}
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(Path(base_dir).resolve()),
            env=env,
        )
        out_b, err_b = await asyncio.wait_for(
            proc.communicate(input=data.encode("utf-8")),
            timeout=_HOOK_SUBPROCESS_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        log.error("Hook %s timed out after %ss: %s", log_label, int(_HOOK_SUBPROCESS_TIMEOUT_S), script)
        return
    except Exception:
        log.exception("Hook %s failed to spawn: %s", log_label, script)
        return
    if proc.returncode != 0:
        log.error(
            "Hook %s exit %s: %s",
            log_label,
            proc.returncode,
            err_b.decode("utf-8", errors="replace")[:4000],
        )
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Hook %s full stderr: %s", log_label, err_b)
        return
    out_t = out_b.decode("utf-8", errors="replace")
    if not (out_t or "").strip() and err_b:
        log.warning(
            "Hook %s empty stdout, stderr: %s",
            log_label,
            err_b.decode("utf-8", errors="replace")[:2000],
        )
    _merge_stdout_into_context(event, out_t)


def _build_cmd_handler(
    cmd: list[str] | None,
    *,
    base_dir: str,
    script: Path,
    log_label: str,
) -> Optional[HookHandler]:
    if not cmd:
        return None

    async def _handler(event: HookEvent) -> None:
        await _run_cmd_handler(cmd=cmd, event=event, base_dir=base_dir, script=script, log_label=log_label)

    return _handler


def build_script_hook_handler(
    *,
    handler_path: str,
    base_dir: str,
    suffix: str,
    export_name: str,
    oclaw: dict[str, Any] | None = None,
) -> Optional[HookHandler]:
    p = Path(handler_path)
    if not p.is_file():
        return None
    sfx = (suffix or "").lower()
    o = oclaw or {}
    script_mode = _is_script_mode(o)

    # Shell: always JSON stdin/stdout; never use TS/JS import runners
    if sfx in {".sh", ".bash"}:
        sc = _sh_command(p)
        return _build_cmd_handler(sc, base_dir=base_dir, script=p, log_label="sh")

    if script_mode:
        if sfx in {".ts", ".mts", ".cts"}:
            cmd = _ts_script_command(script=p)
            return _build_cmd_handler(cmd, base_dir=base_dir, script=p, log_label="ts:script")
        if sfx in {".mjs", ".cjs"}:
            cmd = _js_script_command(script=p)
            return _build_cmd_handler(cmd, base_dir=base_dir, script=p, log_label="js:script")

    # Module / import path (default for ts and js)
    if sfx in {".ts", ".mts", ".cts"}:
        cmd = _ts_command(script=p, export_name=export_name)
        return _build_cmd_handler(cmd, base_dir=base_dir, script=p, log_label="ts:module")
    if sfx in {".mjs", ".cjs"}:
        cmd = _js_module_command(script=p, export_name=export_name)
        return _build_cmd_handler(cmd, base_dir=base_dir, script=p, log_label="js:module")

    return None
