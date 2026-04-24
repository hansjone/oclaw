from __future__ import annotations

import httpx
import re
import unicodedata
from typing import Any

from oclaw.tools.base import ToolSpec
from .geo_http import NOMINATIM_REQUEST_HEADERS, ipapi_approximate_location, nominatim_reverse

_WEATHER_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    95: "Thunderstorm",
}
_LOCAL_WEATHER_ALIASES: frozenset[str] = frozenset(
    {"here", "local", "locally", "nearby", "current", "current location", "my location", "this location", "local area", "unknown", "anywhere", "本地", "当地", "这里", "附近", "当前位置", "当前", "本地天气"}
)


def _normalize_city_token(s: str) -> str:
    t = unicodedata.normalize("NFKC", (s or "").strip()).casefold()
    t = re.sub(r"\s+", " ", t)
    return t


def _is_local_weather_alias(city: str) -> bool:
    return _normalize_city_token(city) in _LOCAL_WEATHER_ALIASES


def _coerce_city(raw: Any) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str):
        raw = str(raw)
    s = raw.strip()
    return s if s else None


def weather_tool() -> ToolSpec:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        city = _coerce_city(args.get("city"))
        lat = args.get("latitude")
        lon = args.get("longitude")
        if (lat is None) ^ (lon is None):
            return {"ok": False, "error": "Provide both latitude and longitude, or neither (for local-IP weather), or use city alone."}
        has_coords = lat is not None and lon is not None

        try:
            with httpx.Client(timeout=12.0) as client:
                location_basis: str
                resolved_city: str
                lat_f: float
                lon_f: float
                extra: dict[str, Any] = {}
                if has_coords:
                    lat_f = float(lat)
                    lon_f = float(lon)
                    location_basis = "explicit_coordinates"
                    rev = nominatim_reverse(client, lat_f, lon_f)
                    dn = (rev.get("display_name") or "").strip() if rev else ""
                    resolved_city = dn or f"Coordinates ({lat_f}, {lon_f})"
                elif city and not _is_local_weather_alias(city):
                    geo_resp = client.get(
                        "https://nominatim.openstreetmap.org/search",
                        params={"q": city, "format": "json", "limit": 1},
                        headers=NOMINATIM_REQUEST_HEADERS,
                    )
                    geo_resp.raise_for_status()
                    geo_data = geo_resp.json()
                    if not geo_data:
                        return {"ok": False, "error": f"City not found: {city}"}
                    first = geo_data[0]
                    lat_f = float(first["lat"])
                    lon_f = float(first["lon"])
                    resolved_city = first.get("display_name", city)
                    location_basis = "explicit_place"
                else:
                    ip_loc = ipapi_approximate_location(client)
                    if not ip_loc:
                        return {"ok": False, "error": "Could not resolve local weather: failed to detect location from this network. Pass a concrete city/region (e.g. 北京) or both latitude and longitude."}
                    lat_f = ip_loc["latitude"]
                    lon_f = ip_loc["longitude"]
                    resolved_city = ip_loc["display_name"]
                    location_basis = "local_network_ip"
                    if ip_loc.get("ip") is not None:
                        extra["approximate_ip"] = ip_loc["ip"]

                weather_url = "https://api.open-meteo.com/v1/forecast"
                weather_params = {
                    "latitude": lat_f,
                    "longitude": lon_f,
                    "current": ["temperature_2m", "relative_humidity_2m", "apparent_temperature", "is_day", "weather_code", "wind_speed_10m"],
                    "timezone": "auto",
                }
                w_resp = client.get(weather_url, params=weather_params)
                w_resp.raise_for_status()
                current = w_resp.json().get("current", {})
                code = int(current.get("weather_code") or 0)
                condition = _WEATHER_CODES.get(code, "Unknown")
                out: dict[str, Any] = {
                    "ok": True,
                    "city": resolved_city,
                    "temperature": f"{current.get('temperature_2m')}°C",
                    "feels_like": f"{current.get('apparent_temperature')}°C",
                    "condition": condition,
                    "humidity": f"{current.get('relative_humidity_2m')}%",
                    "wind_speed": f"{current.get('wind_speed_10m')} km/h",
                    "is_day": bool(current.get("is_day")),
                    "latitude": lat_f,
                    "longitude": lon_f,
                    "location_basis": location_basis,
                }
                out.update(extra)
                if location_basis == "local_network_ip":
                    out["disclaimer"] = "Weather is for the approximate location of this deployment's public IP (VPN/proxy/corporate NAT may differ from the end user's actual place)."
                return out
        except Exception as e:
            return {"ok": False, "error": f"Failed to fetch weather: {e}"}

    return ToolSpec(
        name="get_weather",
        description="Get current weather (Open-Meteo, no API key). Default: omit city and coordinates — uses this server's outbound public IP for approximate local weather. Override: pass a concrete placename in `city` or both `latitude` and `longitude`.",
        parameters={
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "Optional place name."},
                "latitude": {"type": "number", "description": "Optional. Must pair with longitude."},
                "longitude": {"type": "number", "description": "Optional. Must pair with latitude."},
            },
            "additionalProperties": False,
        },
        handler=handler,
    )


__all__ = ["weather_tool"]
