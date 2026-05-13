from __future__ import annotations

import importlib.util
import pathlib
import sys
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any, Iterable
from types import SimpleNamespace

from svc.config.runtime_paths import runtime_extensions_root
from runtime.extensions.plugin_api import PluginEntry


def _sanitize_module_name(value: str) -> str:
    out = []
    for ch in value:
        if ch.isalnum() or ch == "_":
            out.append(ch)
        else:
            out.append("_")
    sanitized = "".join(out).strip("_") or "ext"
    if sanitized[0].isdigit():
        sanitized = f"ext_{sanitized}"
    return sanitized


def _load_module_from_path(*, module_name: str, file_path: pathlib.Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to create import spec for {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_package_from_dir(*, package_name: str, package_dir: pathlib.Path) -> ModuleType:
    init_file = package_dir / "__init__.py"
    if not init_file.exists():
        # Allow package-like loading even if __init__.py is missing.
        init_file = package_dir / "index.py"
    spec = importlib.util.spec_from_file_location(
        package_name,
        str(init_file),
        submodule_search_locations=[str(package_dir)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to create package spec for {package_dir}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = module
    spec.loader.exec_module(module)
    return module


def _iter_extension_dirs(root_dir: pathlib.Path) -> Iterable[pathlib.Path]:
    if not root_dir.exists() or not root_dir.is_dir():
        return []
    return (
        p
        for p in root_dir.iterdir()
        if p.is_dir()
        and not p.name.startswith(".")
        and p.name != "__pycache__"
        and ((p / "__init__.py").exists() or (p / "index.py").exists())
    )


@dataclass
class LoadedExtension:
    id: str
    dir_path: str
    module_name: str
    module_file: str
    plugin_entry: PluginEntry


@dataclass
class RuntimePluginApi:
    """Very small in-process plugin API used by the Python gateway."""

    plugin_config: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    runtime: Any = None
    logger: Any = None

    providers: list[dict[str, Any]] = field(default_factory=list)
    tools: list[dict[str, Any]] = field(default_factory=list)
    channels: list[dict[str, Any]] = field(default_factory=list)
    http_routes: list[dict[str, Any]] = field(default_factory=list)
    image_generation_providers: list[dict[str, Any]] = field(default_factory=list)
    active_plugin_id: str = ""

    def __post_init__(self) -> None:
        # Compatibility shim for plugins expecting `api.runtime.task_flow.bind_session(...)`.
        self.runtime = SimpleNamespace(
            task_flow=SimpleNamespace(
                bind_session=lambda **kwargs: {"session_key": str(kwargs.get("session_key") or "")},
            ),
            image_generation_providers=self.image_generation_providers,
        )

    def register_provider(self, provider: dict[str, Any]) -> None:
        self.providers.append(dict(provider or {}))

    def register_tool(self, tool: dict[str, Any], *_args, **_kwargs) -> None:
        row = dict(tool or {})
        pid = str(self.active_plugin_id or "").strip()
        if pid and not str(row.get("plugin_id") or "").strip():
            row["plugin_id"] = pid
        self.tools.append(row)

    def register_channel(self, channel: dict[str, Any]) -> None:
        self.channels.append(dict(channel or {}))

    def register_http_route(
        self,
        *,
        path: str,
        auth: str,
        match: str,
        replace_existing: bool,
        handler: Any,
    ) -> None:
        self.http_routes.append(
            {
                "path": str(path or "").strip(),
                "auth": str(auth or "").strip(),
                "match": str(match or "").strip(),
                "replace_existing": bool(replace_existing),
                "handler": handler,
            }
        )

    def register_image_generation_provider(self, provider: dict[str, Any]) -> None:
        self.image_generation_providers.append(dict(provider or {}))


def _is_plugin_entry_like(value: Any) -> bool:
    return (
        value is not None
        and isinstance(getattr(value, "id", None), str)
        and isinstance(getattr(value, "name", None), str)
        and isinstance(getattr(value, "description", None), str)
        and callable(getattr(value, "register", None))
    )


def discover_python_extension_entries(
    *,
    root_dir: str,
    only_ids: list[str] | None = None,
) -> list[LoadedExtension]:
    root = pathlib.Path(root_dir).resolve()
    wanted = {str(x).strip() for x in (only_ids or []) if str(x).strip()}

    loaded: list[LoadedExtension] = []
    for ext_dir in _iter_extension_dirs(root):
        ext_id = ext_dir.name
        if wanted and ext_id not in wanted:
            continue
        module_name = f"oclaw_pyext_{_sanitize_module_name(ext_id)}"
        module = _load_package_from_dir(package_name=module_name, package_dir=ext_dir)
        entry = getattr(module, "plugin_entry", None)
        if isinstance(entry, PluginEntry):
            pass
        elif _is_plugin_entry_like(entry):
            # Accept PluginEntry-like objects from local extension API.
            pass
        else:
            continue
        loaded.append(
            LoadedExtension(
                id=entry.id,
                dir_path=str(ext_dir),
                module_name=module_name,
                module_file=str(ext_dir / "__init__.py"),
                plugin_entry=entry,
            )
        )

    return loaded


def build_python_extensions_registry(
    *,
    app_config: dict[str, Any],
    workspace_dir: str,
    only_plugin_ids: list[str],
    log: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ws_dir = pathlib.Path(workspace_dir).resolve()
    logger = (log or {}).get("info")
    api = RuntimePluginApi(plugin_config={}, config=app_config, logger=logger)

    # Support both workspace roots:
    # - repo root (contains `oclaw/runtime/extensions`)
    # - `oclaw` package root (contains `runtime/extensions`)
    extension_roots = [runtime_extensions_root(), ws_dir / "oclaw" / "runtime" / "extensions", ws_dir / "runtime" / "extensions"]
    diagnostics: list[dict[str, Any]] = []
    loaded_by_id: dict[str, LoadedExtension] = {}
    for root in extension_roots:
        discovered = discover_python_extension_entries(root_dir=str(root), only_ids=only_plugin_ids)
        for item in discovered:
            pid = str(item.id or "").strip()
            if not pid:
                continue
            if pid in loaded_by_id:
                diagnostics.append(
                    {
                        "plugin_id": pid,
                        "status": "duplicate_plugin_id",
                        "error": "duplicate plugin id ignored (first source kept)",
                        "module": item.module_name,
                        "file": item.module_file,
                    }
                )
                continue
            loaded_by_id[pid] = item
    loaded = list(loaded_by_id.values())

    for item in loaded:
        try:
            plugin_cfg = (
                ((app_config.get("plugins") or {}).get("entries") or {}).get(item.plugin_entry.id)
                if isinstance(app_config, dict)
                else {}
            )
            api.plugin_config = dict(plugin_cfg or {})
            api.active_plugin_id = str(item.plugin_entry.id or "")
            item.plugin_entry.register(api)
            api.active_plugin_id = ""
        except Exception as exc:  # noqa: BLE001
            diagnostics.append(
                {
                    "plugin_id": item.plugin_entry.id,
                    "status": "error",
                    "error": str(exc),
                    "module": item.module_name,
                    "file": item.module_file,
                }
            )

    return {
        "plugins": [
            {
                "id": item.plugin_entry.id,
                "name": item.plugin_entry.name,
                "description": item.plugin_entry.description,
                "config_schema": getattr(item.plugin_entry, "config_schema", None),
                "dir": item.dir_path,
                "module": item.module_name,
                "file": item.module_file,
                "status": "loaded",
            }
            for item in loaded
        ],
        "providers": api.providers,
        "tools": api.tools,
        "channels": api.channels,
        "image_generation_providers": api.image_generation_providers,
        "http_routes": api.http_routes,
        "gateway_handlers": {},
        "diagnostics": diagnostics,
    }

