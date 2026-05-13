"""Locate and optionally launch the ``vendor/cc-mini`` git submodule.

Upstream lives at https://github.com/e10nMa2k/cc-mini — keep it as a submodule
rather than copying sources into this tree. At the time of integration the
submodule repository did not ship a root ``LICENSE`` file; treat compliance as
upstream-owned until one is published.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from svc.config.paths import PROJECT_ROOT


def cc_mini_root() -> Path:
    """Path to the ``cc-mini`` checkout (``<repo>/vendor/cc-mini``)."""
    return (PROJECT_ROOT / "vendor" / "cc-mini").resolve()


def cc_mini_src_dir() -> Path:
    """Directory that must be on ``PYTHONPATH`` for ``python -m tui.app``."""
    return (cc_mini_root() / "src").resolve()


def cc_mini_available() -> bool:
    """True when the submodule tree looks present (``src/core/engine.py``)."""
    return (cc_mini_src_dir() / "core" / "engine.py").is_file()


def cc_mini_pythonpath_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """Return env with ``vendor/cc-mini/src`` prepended to ``PYTHONPATH``."""
    env = dict(base or os.environ)
    src = str(cc_mini_src_dir())
    prev = (env.get("PYTHONPATH") or "").strip()
    env["PYTHONPATH"] = src + (os.pathsep + prev if prev else "")
    return env


def prepend_cc_mini_src_to_sys_path() -> bool:
    """Insert ``vendor/cc-mini/src`` at the front of ``sys.path`` if available.

    Prefer subprocess + :func:`cc_mini_pythonpath_env` when isolation matters;
    importing ``core`` / ``features`` from cc-mini can clash with similarly
    named packages elsewhere on ``sys.path``.
    """
    src = cc_mini_src_dir()
    if not cc_mini_available():
        return False
    s = str(src)
    if s not in sys.path:
        sys.path.insert(0, s)
    return True


def run_cc_mini_cli(
    argv: list[str] | None = None,
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    """Run cc-mini's interactive entry (``python -m tui.app``) like the ``cc-mini`` console script.

    Requires ``cc_mini_available()``; raises ``FileNotFoundError`` if the checkout is missing.
    """
    root = cc_mini_root()
    if not cc_mini_available():
        raise FileNotFoundError(
            f"cc-mini not found under {root}; run: git submodule update --init vendor/cc-mini"
        )
    merged = cc_mini_pythonpath_env(env if env is not None else os.environ)
    cmd = [sys.executable, "-m", "tui.app", *(argv or [])]
    return subprocess.run(
        cmd,
        cwd=str(cwd or root),
        env=merged,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        **kwargs,
    )
