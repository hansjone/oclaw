from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol


class PluginLogger(Protocol):
    def info(self, message: str) -> None: ...
    def warning(self, message: str) -> None: ...
    def error(self, message: str) -> None: ...


class PluginRuntime(Protocol):
    pass


class PluginApi(Protocol):
    plugin_config: dict[str, Any]
    config: dict[str, Any]
    runtime: PluginRuntime
    logger: PluginLogger


@dataclass(frozen=True)
class PluginEntry:
    id: str
    name: str
    description: str
    register: Callable[[PluginApi], None]


def define_plugin_entry(*, id: str, name: str, description: str, register: Callable[[PluginApi], None]) -> PluginEntry:
    return PluginEntry(id=id, name=name, description=description, register=register)
