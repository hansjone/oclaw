"""通识专家工具清单。"""

from oclaw.runtime.tools.base import ToolSpec


def system_info_tool() -> ToolSpec:
    from .system_info import system_info_tool as factory

    return factory()


__all__ = ["system_info_tool"]
