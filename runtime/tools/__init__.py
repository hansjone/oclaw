"""工具模块：包含 JSON Schema 与处理函数，并通过 :func:`default_registry` 注册。"""

from __future__ import annotations

from runtime.tools.catalog import (
    default_registry,
    materialize_tool_specs,
    tool_inventory,
)

__all__ = [
    "default_registry",
    "materialize_tool_specs",
    "tool_inventory",
]
