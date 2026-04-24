from __future__ import annotations

from typing import Any

from oclaw.tools import tool_inventory


def inventory_snapshot() -> dict[str, Any]:
    tools = tool_inventory()
    data_sources = [
        {"name": "sqlite", "scope": "chat_session/chat_message/tool_log/app_setting/llm_profile"},
        {"name": "attachments", "scope": "user uploaded files parsed as text/image blocks"},
        {"name": "external_api", "scope": "tool handlers (weather/geocode/http)"},
    ]
    permissions = {
        "tool_groups": ["ops", "system"],
        "high_risk_actions": ["port_scan", "network write-like operations", "batch changes"],
        "default_policy": "allow-read, review-before-high-risk",
    }
    return {"tools": tools, "data_sources": data_sources, "permissions": permissions}
