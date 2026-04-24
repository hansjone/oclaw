from __future__ import annotations

from typing import Any


def error_shape(code: str, message: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"code": str(code or "UNKNOWN"), "message": str(message or "")}
    if isinstance(data, dict) and data:
        out["data"] = data
    return out


def assert_valid_params(
    params: Any,
    validator: Any,
    method: str,
    respond: Any,
) -> bool:
    """Validate request params and respond with a standardized error on failure."""
    try:
        ok = bool(validator(params)) if callable(validator) else True
    except Exception as exc:
        ok = False
        err = error_shape("INVALID_REQUEST", f"param validator raised: {type(exc).__name__}")
        try:
            respond(False, None, err, None)
        except Exception:
            pass
        return False
    if ok:
        return True
    err = error_shape("INVALID_REQUEST", f"invalid params for {str(method or '').strip() or 'unknown'}")
    try:
        respond(False, None, err, None)
    except Exception:
        pass
    return False


__all__ = ["assert_valid_params", "error_shape"]
