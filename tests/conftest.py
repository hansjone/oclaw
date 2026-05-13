from __future__ import annotations

import sys
from pathlib import Path


def _normalize_sys_path_for_repo_layout() -> None:
    """Put the repository root (contains ``svc/``, ``runtime/``, ``interfaces/``) first on ``sys.path``.

    First-party imports use top-level packages ``svc``, ``runtime``, and ``interfaces``; they do not
    depend on the checkout directory being named ``oclaw``.
    """
    this_file = Path(__file__).resolve()
    repo_root = this_file.parents[1]
    rr = str(repo_root.resolve())
    sys.path[:] = [p for p in sys.path if p and Path(p).resolve() != repo_root]
    if rr not in sys.path:
        sys.path.insert(0, rr)


_normalize_sys_path_for_repo_layout()
