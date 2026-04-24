"""通识专家工具清单。"""

from oclaw.runtime.tools.base import ToolSpec


def system_info_tool() -> ToolSpec:
    from .system_info import system_info_tool as factory

    return factory()


def geo_info_tool() -> ToolSpec:
    from .geo_info import geo_info_tool as factory

    return factory()


def weather_tool() -> ToolSpec:
    from .weather import weather_tool as factory

    return factory()


def web_search_tool() -> ToolSpec:
    from .web_search import web_search_tool as factory

    return factory()

__all__ = ["system_info_tool", "geo_info_tool", "weather_tool", "web_search_tool"]
