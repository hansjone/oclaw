from __future__ import annotations

import httpx
from typing import Any

from oclaw.runtime.tools.base import ToolSpec
from .geo_http import DEFAULT_HTTP_TIMEOUT, ipapi_approximate_location, nominatim_reverse


def _reverse_geocode(lat: float, lon: float) -> dict[str, Any]:
    with httpx.Client(timeout=DEFAULT_HTTP_TIMEOUT) as client:
        return nominatim_reverse(client, lat, lon)


def geo_info_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        lat = args.get("latitude")
        lon = args.get("longitude")
        if lat is None or lon is None:
            return {"ok": False, "error": "latitude and longitude are required"}
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except (TypeError, ValueError):
            return {"ok": False, "error": "latitude and longitude must be numbers"}
        data = _reverse_geocode(lat_f, lon_f)
        if not data or "error" in data:
            error_msg = data.get("error") if data else "Unknown error"
            return {"ok": False, "error": error_msg}
        return {"ok": True, "address": data.get("display_name"), "details": data.get("address"), "latitude": lat_f, "longitude": lon_f}

    return ToolSpec(
        name="reverse_geocode",
        description="Reverse geocode: get a human-readable address from latitude and longitude.",
        parameters={
            "type": "object",
            "properties": {
                "latitude": {"type": "number", "description": "Latitude in decimal degrees."},
                "longitude": {"type": "number", "description": "Longitude in decimal degrees."},
            },
            "required": ["latitude", "longitude"],
            "additionalProperties": False,
        },
        handler=handler,
    )


def system_location_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=DEFAULT_HTTP_TIMEOUT) as client:
                loc = ipapi_approximate_location(client)
                if not loc:
                    return {"ok": False, "error": "Could not detect coordinates for this network"}
                geo = loc.get("nominatim") or {}
                return {
                    "ok": True,
                    "latitude": loc["latitude"],
                    "longitude": loc["longitude"],
                    "address": loc["display_name"],
                    "ip": loc.get("ip"),
                    "city": loc.get("city"),
                    "region": loc.get("region"),
                    "country": loc.get("country_name"),
                    "details": geo.get("address") if geo else None,
                }
        except Exception as e:
            return {"ok": False, "error": f"Failed to detect location: {e}"}

    return ToolSpec(
        name="get_system_location",
        description="Detect this machine's public IP and approximate location (coordinates and address).",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        handler=handler,
    )


__all__ = ["geo_info_tool", "system_location_tool"]
