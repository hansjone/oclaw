"""系统工具共用 HTTP 辅助函数（Nominatim 逆地理编码与 ipapi.co）。"""

from __future__ import annotations

from typing import Any

import httpx

NOMINATIM_REQUEST_HEADERS = {"User-Agent": "OpsAssistant/1.0 (internal tool)"}
DEFAULT_HTTP_TIMEOUT = 10.0


def nominatim_reverse(
    client: httpx.Client,
    lat: float,
    lon: float,
    *,
    accept_language: str = "en",
) -> dict[str, Any]:
    """调用 Nominatim 逆地理编码并返回解析后的 JSON，失败时返回空字典。"""
    try:
        r = client.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lon, "format": "json", "accept-language": accept_language},
            headers=NOMINATIM_REQUEST_HEADERS,
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def ipapi_approximate_location(client: httpx.Client) -> dict[str, Any] | None:
    try:
        ip_resp = client.get("https://ipapi.co/json/")
        ip_resp.raise_for_status()
        ip_data = ip_resp.json()
        lat = ip_data.get("latitude")
        lon = ip_data.get("longitude")
        if lat is None or lon is None:
            return None
        lat_f = float(lat)
        lon_f = float(lon)
        geo = nominatim_reverse(client, lat_f, lon_f)
        display_name = geo.get("display_name") if geo else None
        if not display_name or not str(display_name).strip():
            parts = [ip_data.get("city"), ip_data.get("region"), ip_data.get("country_name")]
            display_name = ", ".join(str(p) for p in parts if p)
        if not display_name:
            display_name = f"Approximate ({lat_f:.4f}, {lon_f:.4f})"
        return {
            "latitude": lat_f,
            "longitude": lon_f,
            "display_name": str(display_name).strip(),
            "ip": ip_data.get("ip"),
            "city": ip_data.get("city"),
            "region": ip_data.get("region"),
            "country_name": ip_data.get("country_name"),
            "nominatim": geo,
        }
    except Exception:
        return None


__all__ = ["DEFAULT_HTTP_TIMEOUT", "NOMINATIM_REQUEST_HEADERS", "ipapi_approximate_location", "nominatim_reverse"]
