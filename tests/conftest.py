from __future__ import annotations

import importlib
import sys
from pathlib import Path


def _normalize_sys_path_for_repo_layout() -> None:
    """
    Allow running pytest from the ``oclaw`` subdirectory.

    When cwd is ``.../chatgpt/oclaw``, Python may resolve ``import platform``
    to ``oclaw/platform`` instead of stdlib ``platform``. We force sys.path to
    prefer repository root (which contains the ``oclaw`` package directory).
    """
    this_file = Path(__file__).resolve()
    oclaw_dir = this_file.parents[1]
    repo_root = oclaw_dir.parent

    oclaw_dir_str = str(oclaw_dir)
    repo_root_str = str(repo_root)

    sys.path[:] = [p for p in sys.path if p and Path(p).resolve() != oclaw_dir]
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)

    mod = sys.modules.get("platform")
    if mod is not None:
        mod_file = str(getattr(mod, "__file__", "") or "")
        if "oclaw\\platform" in mod_file.replace("/", "\\"):
            sys.modules.pop("platform", None)
            importlib.import_module("platform")


_normalize_sys_path_for_repo_layout()

