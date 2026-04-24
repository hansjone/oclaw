from __future__ import annotations

import importlib.util
import inspect
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from oclaw.tools.base import ToolSpec

logger = logging.getLogger(__name__)

ToolFactory = Callable[[], ToolSpec]
_PUBLIC_ROOT = Path(__file__).resolve().parent / "public"
_CACHED_FACTORIES: list[ToolFactory] | None = None
_CACHED_SPECS: list[ToolSpec] | None = None


def _load_module_from_path(module_path: Path, module_name: str) -> Any | None:
    try:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if not spec or not spec.loader:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as exc:
        logger.warning("skip public module %s: %s", module_path, exc)
        return None


def discover_public_tool_factories() -> list[ToolFactory]:
    """Discover public tool factories (naming convention: `*_tool`)."""
    global _CACHED_FACTORIES
    if _CACHED_FACTORIES is not None:
        return list(_CACHED_FACTORIES)
    if not _PUBLIC_ROOT.exists():
        _CACHED_FACTORIES = []
        return []
    factories: list[ToolFactory] = []
    for module_path in sorted(_PUBLIC_ROOT.glob("*.py")):
        if module_path.name == "__init__.py":
            continue
        mod_name = f"oclaw.tools.public.{module_path.stem}"
        module = _load_module_from_path(module_path, mod_name)
        if module is None:
            continue
        exported = getattr(module, "__all__", None)
        if isinstance(exported, list) and exported:
            for name in sorted(exported):
                value = getattr(module, name, None)
                if callable(value) and name.endswith("_tool"):
                    factories.append(value)
            continue
        for name, value in sorted(inspect.getmembers(module)):
            if callable(value) and name.endswith("_tool"):
                factories.append(value)
    _CACHED_FACTORIES = list(factories)
    return list(factories)


def materialize_public_tools() -> list[ToolSpec]:
    global _CACHED_SPECS
    if _CACHED_SPECS is not None:
        return list(_CACHED_SPECS)
    specs: list[ToolSpec] = []
    for factory in discover_public_tool_factories():
        try:
            specs.append(factory())
        except Exception as exc:
            logger.warning("skip public tool factory %s: %s", factory, exc)
    _CACHED_SPECS = list(specs)
    return list(specs)


def clear_public_tool_cache() -> None:
    global _CACHED_FACTORIES, _CACHED_SPECS
    _CACHED_FACTORIES = None
    _CACHED_SPECS = None


def preview_public_tools() -> dict[str, Any]:
    """Preview public tool load outcome, including skip reasons.

    This intentionally bypasses caches so Admin UI can reflect current filesystem state.
    """
    out_tools: list[ToolSpec] = []
    skipped: list[dict[str, str]] = []
    if not _PUBLIC_ROOT.exists():
        return {"tools": [], "skipped": []}
    for module_path in sorted(_PUBLIC_ROOT.glob("*.py")):
        if module_path.name == "__init__.py":
            continue
        mod_name = f"oclaw.tools.public.{module_path.stem}"
        module = None
        try:
            module = _load_module_from_path(module_path, mod_name)
        except Exception as exc:
            skipped.append({"module": str(module_path), "error_code": "module_load_exception", "error": str(exc)})
            continue
        if module is None:
            skipped.append({"module": str(module_path), "error_code": "module_load_failed", "error": "load_failed"})
            continue
        factories: list[ToolFactory] = []
        exported = getattr(module, "__all__", None)
        if isinstance(exported, list) and exported:
            for name in sorted(exported):
                value = getattr(module, name, None)
                if callable(value) and name.endswith("_tool"):
                    factories.append(value)
        else:
            for name, value in sorted(inspect.getmembers(module)):
                if callable(value) and name.endswith("_tool"):
                    factories.append(value)
        if not factories:
            continue
        for factory in factories:
            try:
                out_tools.append(factory())
            except Exception as exc:
                skipped.append(
                    {
                        "module": str(module_path),
                        "error_code": "tool_factory_failed",
                        "error": str(exc),
                        "factory": str(getattr(factory, "__name__", "") or str(factory)),
                    }
                )
    return {"tools": out_tools, "skipped": skipped}


__all__ = [
    "ToolFactory",
    "clear_public_tool_cache",
    "discover_public_tool_factories",
    "materialize_public_tools",
    "preview_public_tools",
]

