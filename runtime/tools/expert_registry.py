from __future__ import annotations

import importlib.util
import inspect
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from oclaw.runtime.tools.base import ToolSpec

logger = logging.getLogger(__name__)

ToolFactory = Callable[[], ToolSpec]
_EXPERTS_ROOT = Path(__file__).resolve().parent / "experts"
_CACHED_FACTORIES_BY_EXPERT: dict[str, list[ToolFactory]] | None = None
_CACHED_SPECS_BY_EXPERT: dict[str, list[ToolSpec]] | None = None
_DEPRECATED_TOOL_NAMES: set[str] = {
    # Deprecated internal tool from legacy src/tools chain.
    "get_weather",
}


def _load_module_from_path(module_path: Path, module_name: str) -> Any | None:
    try:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if not spec or not spec.loader:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as exc:
        logger.warning("skip expert module %s: %s", module_path, exc)
        return None


def discover_expert_tool_factories() -> dict[str, list[ToolFactory]]:
    """按专家目录发现工具工厂函数（命名约定：`*_tool`）。"""
    global _CACHED_FACTORIES_BY_EXPERT
    if _CACHED_FACTORIES_BY_EXPERT is not None:
        # 返回浅拷贝，避免调用方误改缓存
        return {k: list(v) for k, v in _CACHED_FACTORIES_BY_EXPERT.items()}

    result: dict[str, list[ToolFactory]] = {}
    if not _EXPERTS_ROOT.exists():
        _CACHED_FACTORIES_BY_EXPERT = {}
        return {}

    for expert_dir in sorted([p for p in _EXPERTS_ROOT.iterdir() if p.is_dir()]):
        expert = expert_dir.name
        factories: list[ToolFactory] = []
        for module_path in sorted(expert_dir.glob("*.py")):
            if module_path.name == "__init__.py":
                continue
            mod_name = f"oclaw.runtime.tools.experts.{expert}.{module_path.stem}"
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
        if factories:
            result[expert] = factories
    _CACHED_FACTORIES_BY_EXPERT = {k: list(v) for k, v in result.items()}
    return result


def materialize_tools_by_expert() -> dict[str, list[ToolSpec]]:
    global _CACHED_SPECS_BY_EXPERT
    if _CACHED_SPECS_BY_EXPERT is not None:
        return {k: list(v) for k, v in _CACHED_SPECS_BY_EXPERT.items()}

    rows: dict[str, list[ToolSpec]] = {}
    for expert, factories in discover_expert_tool_factories().items():
        specs: list[ToolSpec] = []
        for factory in factories:
            try:
                spec = factory()
                if str(spec.name or "").strip() in _DEPRECATED_TOOL_NAMES:
                    continue
                specs.append(spec)
            except Exception as exc:
                logger.warning("skip expert tool factory %s for %s: %s", factory, expert, exc)
        if specs:
            rows[expert] = specs
    _CACHED_SPECS_BY_EXPERT = {k: list(v) for k, v in rows.items()}
    return rows


def materialize_tools_for_expert(expert: str | None) -> list[ToolSpec]:
    """获取某个专家工具，expert 为空时返回所有专家工具合集。"""
    if expert:
        # Support composition: "generalist+workspace"
        if "+" in expert:
            parts = [p.strip() for p in str(expert).split("+") if p.strip()]
            merged: list[ToolSpec] = []
            seen: set[str] = set()
            for p in parts:
                for spec in materialize_tools_for_expert(p):
                    if spec.name in seen:
                        continue
                    seen.add(spec.name)
                    merged.append(spec)
            return merged
    by_expert = materialize_tools_by_expert()
    if not expert:
        out: list[ToolSpec] = []
        for key in sorted(by_expert.keys()):
            out.extend(by_expert[key])
        return out
    return list(by_expert.get(expert, []))


def clear_expert_tool_cache() -> None:
    global _CACHED_FACTORIES_BY_EXPERT, _CACHED_SPECS_BY_EXPERT
    _CACHED_FACTORIES_BY_EXPERT = None
    _CACHED_SPECS_BY_EXPERT = None


def preview_expert_tools(expert: str | None) -> dict[str, Any]:
    """Preview expert tool load outcome, including skip reasons.

    This bypasses caches so Admin UI can reflect current filesystem state.
    """
    exp = str(expert or "").strip()
    # Support composition: "generalist+workspace"
    parts = [p.strip() for p in exp.split("+") if p.strip()] if exp and "+" in exp else ([exp] if exp else [])
    targets = parts if parts else sorted([p.name for p in _EXPERTS_ROOT.iterdir() if p.is_dir()]) if _EXPERTS_ROOT.exists() else []

    out_tools: list[ToolSpec] = []
    skipped: list[dict[str, str]] = []
    seen: set[str] = set()

    for ex in targets:
        expert_dir = _EXPERTS_ROOT / ex
        if not expert_dir.exists() or not expert_dir.is_dir():
            continue
        for module_path in sorted(expert_dir.glob("*.py")):
            if module_path.name == "__init__.py":
                continue
            mod_name = f"oclaw.runtime.tools.experts.{ex}.{module_path.stem}"
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
            for factory in factories:
                try:
                    spec = factory()
                except Exception as exc:
                    skipped.append(
                        {
                            "module": str(module_path),
                            "error_code": "tool_factory_failed",
                            "error": str(exc),
                            "factory": str(getattr(factory, "__name__", "") or str(factory)),
                        }
                    )
                    continue
                if str(spec.name or "").strip() in _DEPRECATED_TOOL_NAMES:
                    skipped.append(
                        {
                            "module": str(module_path),
                            "error_code": "tool_deprecated",
                            "error": f"deprecated_tool:{spec.name}",
                            "factory": str(getattr(factory, "__name__", "") or str(factory)),
                        }
                    )
                    continue
                if spec.name in seen:
                    continue
                seen.add(spec.name)
                out_tools.append(spec)

    return {"tools": out_tools, "skipped": skipped}


__all__ = [
    "ToolFactory",
    "clear_expert_tool_cache",
    "discover_expert_tool_factories",
    "materialize_tools_by_expert",
    "materialize_tools_for_expert",
    "preview_expert_tools",
]
