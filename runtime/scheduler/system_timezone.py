from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo, available_timezones

# Windows registry TimeZoneKeyName -> IANA (common subset; unmapped names fall back to offset).
_WINDOWS_IANA_TZ: dict[str, str] = {
    "Afghanistan Standard Time": "Asia/Kabul",
    "Alaskan Standard Time": "America/Anchorage",
    "Arab Standard Time": "Asia/Riyadh",
    "Arabian Standard Time": "Asia/Dubai",
    "Arabic Standard Time": "Asia/Baghdad",
    "Argentina Standard Time": "America/Buenos_Aires",
    "AUS Central Standard Time": "Australia/Darwin",
    "AUS Eastern Standard Time": "Australia/Sydney",
    "Azores Standard Time": "Atlantic/Azores",
    "Bangladesh Standard Time": "Asia/Dhaka",
    "Canada Central Standard Time": "America/Regina",
    "Cape Verde Standard Time": "Atlantic/Cape_Verde",
    "Caucasus Standard Time": "Asia/Yerevan",
    "Cen. Australia Standard Time": "Australia/Adelaide",
    "Central America Standard Time": "America/Guatemala",
    "Central Asia Standard Time": "Asia/Almaty",
    "Central Brazilian Standard Time": "America/Cuiaba",
    "Central Europe Standard Time": "Europe/Budapest",
    "Central European Standard Time": "Europe/Warsaw",
    "Central Pacific Standard Time": "Pacific/Guadalcanal",
    "Central Standard Time": "America/Chicago",
    "Central Standard Time (Mexico)": "America/Mexico_City",
    "China Standard Time": "Asia/Shanghai",
    "Dateline Standard Time": "Etc/GMT+12",
    "E. Africa Standard Time": "Africa/Nairobi",
    "E. Australia Standard Time": "Australia/Brisbane",
    "E. Europe Standard Time": "Europe/Chisinau",
    "E. South America Standard Time": "America/Sao_Paulo",
    "Eastern Standard Time": "America/New_York",
    "Egypt Standard Time": "Africa/Cairo",
    "Ekaterinburg Standard Time": "Asia/Yekaterinburg",
    "Fiji Standard Time": "Pacific/Fiji",
    "FLE Standard Time": "Europe/Kiev",
    "Georgian Standard Time": "Asia/Tbilisi",
    "GMT Standard Time": "Europe/London",
    "Greenland Standard Time": "America/Godthab",
    "Greenwich Standard Time": "Atlantic/Reykjavik",
    "GTB Standard Time": "Europe/Bucharest",
    "Hawaiian Standard Time": "Pacific/Honolulu",
    "India Standard Time": "Asia/Kolkata",
    "Iran Standard Time": "Asia/Tehran",
    "Israel Standard Time": "Asia/Jerusalem",
    "Jordan Standard Time": "Asia/Amman",
    "Kaliningrad Standard Time": "Europe/Kaliningrad",
    "Korea Standard Time": "Asia/Seoul",
    "Libya Standard Time": "Africa/Tripoli",
    "Line Islands Standard Time": "Pacific/Kiritimati",
    "Magadan Standard Time": "Asia/Magadan",
    "Mauritius Standard Time": "Indian/Mauritius",
    "Mid-Atlantic Standard Time": "Etc/GMT+2",
    "Middle East Standard Time": "Asia/Beirut",
    "Montevideo Standard Time": "America/Montevideo",
    "Morocco Standard Time": "Africa/Casablanca",
    "Mountain Standard Time": "America/Denver",
    "Mountain Standard Time (Mexico)": "America/Chihuahua",
    "Myanmar Standard Time": "Asia/Yangon",
    "N. Central Asia Standard Time": "Asia/Novosibirsk",
    "Namibia Standard Time": "Africa/Windhoek",
    "Nepal Standard Time": "Asia/Kathmandu",
    "New Zealand Standard Time": "Pacific/Auckland",
    "Newfoundland Standard Time": "America/St_Johns",
    "North Asia East Standard Time": "Asia/Ulaanbaatar",
    "North Asia Standard Time": "Asia/Krasnoyarsk",
    "Pacific SA Standard Time": "America/Santiago",
    "Pacific Standard Time": "America/Los_Angeles",
    "Pacific Standard Time (Mexico)": "America/Tijuana",
    "Pakistan Standard Time": "Asia/Karachi",
    "Paraguay Standard Time": "America/Asuncion",
    "Romance Standard Time": "Europe/Paris",
    "Russia Time Zone 10": "Asia/Srednekolymsk",
    "Russia Time Zone 11": "Asia/Kamchatka",
    "Russia Time Zone 3": "Europe/Samara",
    "Russian Standard Time": "Europe/Moscow",
    "SA Eastern Standard Time": "America/Cayenne",
    "SA Pacific Standard Time": "America/Bogota",
    "SA Western Standard Time": "America/La_Paz",
    "SE Asia Standard Time": "Asia/Bangkok",
    "Singapore Standard Time": "Asia/Singapore",
    "South Africa Standard Time": "Africa/Johannesburg",
    "Sri Lanka Standard Time": "Asia/Colombo",
    "Syria Standard Time": "Asia/Damascus",
    "Taipei Standard Time": "Asia/Taipei",
    "Tasmania Standard Time": "Australia/Hobart",
    "Tokyo Standard Time": "Asia/Tokyo",
    "Tonga Standard Time": "Pacific/Tongatapu",
    "Turkey Standard Time": "Europe/Istanbul",
    "US Eastern Standard Time": "America/Indianapolis",
    "US Mountain Standard Time": "America/Phoenix",
    "UTC": "UTC",
    "UTC+12": "Etc/GMT-12",
    "UTC-02": "Etc/GMT+2",
    "UTC-11": "Etc/GMT+11",
    "Venezuela Standard Time": "America/Caracas",
    "Vladivostok Standard Time": "Asia/Vladivostok",
    "W. Australia Standard Time": "Australia/Perth",
    "W. Central Africa Standard Time": "Africa/Lagos",
    "W. Europe Standard Time": "Europe/Berlin",
    "West Asia Standard Time": "Asia/Tashkent",
    "West Pacific Standard Time": "Pacific/Port_Moresby",
    "Yakutsk Standard Time": "Asia/Yakutsk",
}


def _validate_iana(name: str) -> str | None:
    tz = str(name or "").strip()
    if not tz:
        return None
    try:
        ZoneInfo(tz)
    except Exception:
        return None
    if tz not in available_timezones() and tz != "UTC":
        # Allow Etc/* aliases even if not enumerated on some platforms.
        if not tz.startswith("Etc/"):
            return None
    return tz


def _offset_fallback_timezone() -> str:
    local = datetime.now().astimezone()
    offset = local.utcoffset()
    if offset is None:
        return "UTC"
    hours = int(offset.total_seconds() // 3600)
    if hours == 0:
        return "UTC"
    # Etc/GMT sign is inverted: Etc/GMT-8 == UTC+8.
    sign = "-" if hours > 0 else "+"
    return f"Etc/GMT{sign}{abs(hours)}"


def _windows_system_timezone() -> str | None:
    try:
        import winreg
    except ImportError:
        return None
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\TimeZoneInformation",
        ) as key:
            win_name = str(winreg.QueryValueEx(key, "TimeZoneKeyName")[0] or "").strip()
    except Exception:
        return None
    mapped = _WINDOWS_IANA_TZ.get(win_name)
    if mapped:
        return _validate_iana(mapped)
    return None


def _unix_system_timezone() -> str | None:
    try:
        local_tz = datetime.now().astimezone().tzinfo
        key = getattr(local_tz, "key", None)
        if isinstance(key, str):
            return _validate_iana(key)
    except Exception:
        return None
    return None


@lru_cache(maxsize=1)
def default_system_timezone() -> str:
    """Return the host IANA timezone used as the scheduler default."""
    for candidate in (
        os.environ.get("AIA_SCHEDULER_DEFAULT_TIMEZONE"),
        os.environ.get("TZ"),
    ):
        validated = _validate_iana(str(candidate or ""))
        if validated:
            return validated

    if sys.platform == "win32":
        win_tz = _windows_system_timezone()
        if win_tz:
            return win_tz
    else:
        unix_tz = _unix_system_timezone()
        if unix_tz:
            return unix_tz

    offset_tz = _validate_iana(_offset_fallback_timezone())
    return offset_tz or "UTC"


def reset_default_system_timezone_cache() -> None:
    default_system_timezone.cache_clear()


__all__ = ["default_system_timezone", "reset_default_system_timezone_cache"]
