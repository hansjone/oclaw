from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .runtime_api import normalize_webhook_path


SecretInput = str | dict[str, str]


@dataclass(frozen=True)
class ConfiguredWebhookRoute:
    route_id: str
    path: str
    session_key: str
    secret: SecretInput
    controller_id: str
    description: str = ""


def _validate_secret(value: Any) -> SecretInput:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        source = str(value.get("source") or "").strip()
        provider = str(value.get("provider") or "").strip()
        sid = str(value.get("id") or "").strip()
        if source in {"env", "file", "exec"} and provider and sid:
            return {"source": source, "provider": provider, "id": sid}
    raise ValueError("invalid webhook secret: must be non-empty string or secretRef dict")


def resolve_webhooks_plugin_config(*, plugin_config: Any) -> list[ConfiguredWebhookRoute]:
    cfg = plugin_config if isinstance(plugin_config, dict) else {}
    routes = cfg.get("routes")
    routes = routes if isinstance(routes, dict) else {}
    out: list[ConfiguredWebhookRoute] = []
    seen_paths: dict[str, str] = {}
    for route_id, raw in routes.items():
        rid = str(route_id or "").strip()
        if not rid or not isinstance(raw, dict):
            continue
        enabled = bool(raw.get("enabled", True))
        if not enabled:
            continue
        session_key = str(raw.get("sessionKey") or "").strip()
        if not session_key:
            raise ValueError(f"webhooks.routes.{rid}.sessionKey is required")
        path = normalize_webhook_path(str(raw.get("path") or f"/plugins/webhooks/{rid}"))
        if path in seen_paths:
            raise ValueError(f"webhooks.routes.{rid}.path conflicts with routes.{seen_paths[path]}.path ({path})")
        seen_paths[path] = rid
        secret = _validate_secret(raw.get("secret"))
        controller_id = str(raw.get("controllerId") or f"webhooks/{rid}").strip()
        description = str(raw.get("description") or "").strip()
        out.append(
            ConfiguredWebhookRoute(
                route_id=rid,
                path=path,
                session_key=session_key,
                secret=secret,
                controller_id=controller_id,
                description=description,
            )
        )
    return out

