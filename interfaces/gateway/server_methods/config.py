from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from .shared_types import GatewayRequestHandlers
from .validation import assert_valid_params, error_shape


@dataclass(frozen=True)
class _ConfigSnapshot:
    exists: bool
    valid: bool
    config: dict[str, Any] | None
    raw: str | None = None


def _read_config_file_snapshot() -> _ConfigSnapshot:
    """Staging adapter.

    The upstream TS version reads JSON5 from Oclaw config root.
    Here we keep a minimal in-memory placeholder until full config I/O is ported.
    """
    return _ConfigSnapshot(exists=False, valid=True, config={})


def _load_schema_with_plugins() -> dict[str, Any]:
    # Placeholder for `loadGatewayRuntimeConfigSchema`.
    return {"schema": "stub", "uiHints": {}}


def _validate_config_get_params(params: Any) -> bool:
    return isinstance(params, dict) or params is None


def _validate_config_schema_params(params: Any) -> bool:
    return isinstance(params, dict) or params is None


def _validate_config_schema_lookup_params(params: Any) -> bool:
    return isinstance(params, dict) and isinstance(params.get("path"), str) and bool(params["path"].strip())


def _validate_config_set_params(params: Any) -> bool:
    return isinstance(params, dict) and isinstance(params.get("raw"), str)


def _validate_config_patch_params(params: Any) -> bool:
    return isinstance(params, dict) and isinstance(params.get("raw"), str)


def _validate_config_apply_params(params: Any) -> bool:
    return isinstance(params, dict) and isinstance(params.get("raw"), str)


def _config_get_handler(opts: dict[str, Any]) -> Any:
    respond = opts.get("respond")
    params = opts.get("params")
    if not callable(respond):
        return None
    if not assert_valid_params(params, _validate_config_get_params, "config.get", respond):
        return None
    snapshot = _read_config_file_snapshot()
    schema = _load_schema_with_plugins()
    respond(True, {"snapshot": snapshot.config, "schema": schema}, None, None)
    return None


def _config_schema_handler(opts: dict[str, Any]) -> Any:
    respond = opts.get("respond")
    params = opts.get("params")
    if not callable(respond):
        return None
    if not assert_valid_params(params, _validate_config_schema_params, "config.schema", respond):
        return None
    respond(True, _load_schema_with_plugins(), None, None)
    return None


def _config_schema_lookup_handler(opts: dict[str, Any]) -> Any:
    respond = opts.get("respond")
    context = opts.get("context") or {}
    params = opts.get("params")
    if not callable(respond):
        return None
    if not assert_valid_params(params, _validate_config_schema_lookup_params, "config.schema.lookup", respond):
        return None
    path = str((params or {}).get("path") or "").strip()
    schema = _load_schema_with_plugins()
    # Minimal lookup: dotted path fetch from schema dict.
    cur: Any = schema
    for seg in path.split("."):
        if not isinstance(cur, dict) or seg not in cur:
            respond(False, None, error_shape("INVALID_REQUEST", "config schema path not found"), None)
            return None
        cur = cur[seg]
    respond(True, {"path": path, "value": cur}, None, None)
    _ = context
    return None


def _parse_raw_json_or_error(raw: str) -> tuple[bool, dict[str, Any] | None, str | None]:
    try:
        obj = json.loads(raw)
    except Exception as exc:
        return (False, None, f"invalid json: {exc}")
    if not isinstance(obj, dict):
        return (False, None, "raw must be a json object")
    return (True, obj, None)


def _config_set_like_handler(opts: dict[str, Any], method: str) -> Any:
    respond = opts.get("respond")
    params = opts.get("params")
    if not callable(respond):
        return None
    validator = _validate_config_set_params if method == "config.set" else _validate_config_apply_params
    if not assert_valid_params(params, validator, method, respond):
        return None
    raw = str((params or {}).get("raw") or "")
    ok, obj, err = _parse_raw_json_or_error(raw)
    if not ok or obj is None:
        respond(False, None, error_shape("INVALID_REQUEST", err or "invalid config"), None)
        return None
    respond(True, {"ok": True, "config": obj}, None, None)
    return None


def _config_patch_handler(opts: dict[str, Any]) -> Any:
    respond = opts.get("respond")
    params = opts.get("params")
    if not callable(respond):
        return None
    if not assert_valid_params(params, _validate_config_patch_params, "config.patch", respond):
        return None
    # Staging patch: treat raw as full next config.
    raw = str((params or {}).get("raw") or "")
    ok, obj, err = _parse_raw_json_or_error(raw)
    if not ok or obj is None:
        respond(False, None, error_shape("INVALID_REQUEST", err or "invalid config"), None)
        return None
    respond(True, {"ok": True, "noop": False, "config": obj}, None, None)
    return None


def _config_open_file_handler(opts: dict[str, Any]) -> Any:
    respond = opts.get("respond")
    params = opts.get("params")
    if not callable(respond):
        return None
    if not assert_valid_params(params, _validate_config_get_params, "config.openFile", respond):
        return None
    config_path = os.getenv("OCLAW_CONFIG_PATH") or "oclaw.json"
    respond(True, {"ok": True, "path": config_path}, None, None)
    return None


config_handlers: GatewayRequestHandlers = {
    "config.get": _config_get_handler,
    "config.schema": _config_schema_handler,
    "config.schema.lookup": _config_schema_lookup_handler,
    "config.set": lambda opts: _config_set_like_handler(opts, "config.set"),
    "config.patch": _config_patch_handler,
    "config.apply": lambda opts: _config_set_like_handler(opts, "config.apply"),
    "config.openFile": _config_open_file_handler,
}

