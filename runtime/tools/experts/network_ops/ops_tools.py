"""网络运维专家工具清单。"""

from oclaw.runtime.tools.base import ToolSpec


def query_route_tool() -> ToolSpec:
    from .query_route import query_route_tool as factory

    return factory()


def get_path_tool() -> ToolSpec:
    from .get_path import get_path_tool as factory

    return factory()


def config_diff_tool() -> ToolSpec:
    from .config_diff import config_diff_tool as factory

    return factory()


def device_status_tool() -> ToolSpec:
    from .device_status import device_status_tool as factory

    return factory()


def log_analysis_tool() -> ToolSpec:
    from .log_analysis import log_analysis_tool as factory

    return factory()


def dns_lookup_tool() -> ToolSpec:
    from .network_probe_tools import dns_lookup_tool as factory

    return factory()


def ssl_check_tool() -> ToolSpec:
    from .network_probe_tools import ssl_check_tool as factory

    return factory()


def port_check_tool() -> ToolSpec:
    from .network_probe_tools import port_check_tool as factory

    return factory()


def port_scan_tool() -> ToolSpec:
    from .network_probe_tools import port_scan_tool as factory

    return factory()


def local_net_info_tool() -> ToolSpec:
    from .network_probe_tools import local_net_info_tool as factory

    return factory()


__all__ = [
    "query_route_tool",
    "get_path_tool",
    "config_diff_tool",
    "device_status_tool",
    "log_analysis_tool",
    "dns_lookup_tool",
    "ssl_check_tool",
    "port_check_tool",
    "port_scan_tool",
    "local_net_info_tool",
]
