from __future__ import annotations

import ipaddress
from typing import Any

from oclaw.runtime.tools.base import ToolSpec


def _pick_route(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> dict[str, Any]:
    if isinstance(ip, ipaddress.IPv4Address):
        if ip in ipaddress.ip_network("10.0.0.0/8"):
            return {"prefix": "10.0.0.0/8", "next_hop": "192.168.1.1", "out_if": "GigabitEthernet0/0"}
        if ip in ipaddress.ip_network("172.16.0.0/12"):
            return {"prefix": "172.16.0.0/12", "next_hop": "192.168.2.1", "out_if": "GigabitEthernet0/1"}
        if ip in ipaddress.ip_network("192.168.0.0/16"):
            return {"prefix": "192.168.0.0/16", "next_hop": "direct", "out_if": "Vlan10"}
        return {"prefix": "0.0.0.0/0", "next_hop": "203.0.113.1", "out_if": "GigabitEthernet1/0"}

    if ip in ipaddress.ip_network("fc00::/7"):
        return {"prefix": "fc00::/7", "next_hop": "fe80::1", "out_if": "Vlan20"}
    return {"prefix": "::/0", "next_hop": "2001:db8::1", "out_if": "GigabitEthernet1/0"}


def query_route_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        destination = str(args.get("destination"))
        vrf = args.get("vrf")
        try:
            ip = ipaddress.ip_address(destination)
        except ValueError:
            return {"ok": False, "error": f"Invalid IP address: {destination}"}
        route = _pick_route(ip)
        return {"ok": True, "destination": destination, "vrf": vrf, "route": route}

    return ToolSpec(
        name="query_route",
        description="Look up route egress and next hop for a destination IP (demo data; replace with a real device or controller API).",
        parameters={
            "type": "object",
            "properties": {
                "destination": {"type": "string", "description": "Destination IP address (IPv4 or IPv6)."},
                "vrf": {"type": "string", "description": "Optional VRF name."},
            },
            "required": ["destination"],
            "additionalProperties": False,
        },
        handler=handler,
    )


__all__ = ["query_route_tool"]
