from __future__ import annotations

import importlib.util
import sysconfig
from pathlib import Path


def _load_stdlib_platform() -> object | None:
    stdlib_dir = Path(sysconfig.get_paths().get("stdlib") or "")
    platform_py = (stdlib_dir / "platform.py").resolve()
    if not platform_py.exists():
        return None
    spec = importlib.util.spec_from_file_location("_stdlib_platform", str(platform_py))
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_stdlib = _load_stdlib_platform()
if _stdlib is not None:
    for _name in dir(_stdlib):
        if _name in {"__name__", "__package__", "__loader__", "__spec__", "__file__", "__cached__"}:
            continue
        globals()[_name] = getattr(_stdlib, _name)
    __all__ = list(getattr(_stdlib, "__all__", []))
else:
    __all__ = []

