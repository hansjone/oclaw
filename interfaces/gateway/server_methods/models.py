from __future__ import annotations

from typing import Any

from .shared_types import GatewayRequestHandlers
from .validation import error_shape


def _ok(respond, payload: Any) -> None:
    if callable(respond):
        respond(True, payload, None, None)


def _bad(respond, message: str) -> None:
    if callable(respond):
        respond(False, None, error_shape("INVALID_REQUEST", message), None)


def _unavailable(respond, message: str) -> None:
    if callable(respond):
        respond(False, None, error_shape("UNAVAILABLE", message), None)


def _models_list_handler(opts: dict[str, Any]) -> None:
    params = opts.get("params")
    respond = opts.get("respond")
    context = opts.get("context")
    if params is not None and not isinstance(params, dict):
        _bad(respond, "invalid models.list params")
        return
    load_catalog = context.get("loadGatewayModelCatalog") if isinstance(context, dict) else None
    if not callable(load_catalog):
        # Staging fallback: keep contract shape.
        _ok(respond, {"models": []})
        return
    try:
        catalog = load_catalog()
        if not isinstance(catalog, list):
            catalog = []
    except Exception as exc:
        _unavailable(respond, str(exc))
        return

    # Optional policy hook to emulate TS buildAllowedModelSet behavior.
    allowed_hook = context.get("filterAllowedModels") if isinstance(context, dict) else None
    if callable(allowed_hook):
        try:
            allowed = allowed_hook(catalog)
            if isinstance(allowed, list) and len(allowed) > 0:
                _ok(respond, {"models": allowed})
                return
        except Exception:
            # Non-fatal: fallback to full catalog
            pass
    _ok(respond, {"models": catalog})


models_handlers: GatewayRequestHandlers = {
    "models.list": _models_list_handler,
}

