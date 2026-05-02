"""Load optional env files before the rest of the app reads ``os.environ``.

Only ``_local/system.env`` (next to the committed template ``_local/system.env.example``) is read.
Variables already set in the process environment are never overwritten (shell/export wins).

新增进程环境变量时：必须在 ``_local/system.env.example`` 用中文登记说明（见该文件顶部的仓库约定）。
"""

from __future__ import annotations

import os
from pathlib import Path

_LOADED = False


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _parse_env_file(path: Path) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("export "):
            s = s[7:].strip()
        if "=" not in s:
            continue
        k, _, rest = s.partition("=")
        key = k.strip()
        if not key:
            continue
        val = rest.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        out[key] = val
    return out


def load_system_env(*, force: bool = False) -> list[str]:
    """Merge env files into ``os.environ`` for keys not already set.

    Returns the list of existing files that contributed (merged order).
    """
    global _LOADED
    if _LOADED and not force:
        return []

    root = _project_root()
    candidates = [root / "_local" / "system.env"]

    merged: dict[str, str | None] = {}
    dotenv_values = None
    try:
        from dotenv import dotenv_values as _dv  # type: ignore

        dotenv_values = _dv
    except ImportError:
        pass

    loaded_paths: list[str] = []
    for p in candidates:
        if not p.is_file():
            continue
        loaded_paths.append(str(p.resolve()))
        if dotenv_values is not None:
            vals = dotenv_values(p)
            for k, v in vals.items():
                merged[str(k)] = v
        else:
            merged.update(_parse_env_file(p))

    for key, val in merged.items():
        if not key or key in os.environ:
            continue
        if val is None:
            continue
        os.environ[str(key)] = str(val)

    _LOADED = True
    return loaded_paths


__all__ = ["load_system_env"]
