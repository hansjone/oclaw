from __future__ import annotations

import time
from typing import Any

try:
    import jsonschema
    from jsonschema import validators
except Exception:  # pragma: no cover
    jsonschema = None
    validators = None


def filter_arguments_to_schema(parameters: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    """Drop keys not declared in tool schema when additionalProperties is false."""
    if not isinstance(arguments, dict):
        return {}
    schema = parameters or {}
    props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    if schema.get("additionalProperties") is False and props:
        return {k: v for k, v in arguments.items() if k in props}
    return dict(arguments)


def _example_from_schema(parameters: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal example object from JSON Schema properties/required."""
    props = parameters.get("properties") if isinstance(parameters.get("properties"), dict) else {}
    required = parameters.get("required") if isinstance(parameters.get("required"), list) else []
    keys = [str(k) for k in required if str(k) in props]
    if not keys:
        # Prefer a few representative optional keys so agents see the shape.
        keys = list(props.keys())[:4]
    example: dict[str, Any] = {}
    for key in keys:
        spec = props.get(key) if isinstance(props.get(key), dict) else {}
        if "default" in spec:
            example[key] = spec["default"]
            continue
        t = spec.get("type")
        if t == "string" or (isinstance(t, list) and "string" in t):
            enum = spec.get("enum")
            example[key] = enum[0] if isinstance(enum, list) and enum else f"<{key}>"
        elif t == "integer" or t == "number":
            example[key] = int(spec.get("minimum") or 1)
        elif t == "boolean":
            example[key] = bool(spec.get("default") if "default" in spec else True)
        elif t == "array":
            example[key] = []
        elif t == "object":
            example[key] = {}
        else:
            example[key] = f"<{key}>"
    return example


def format_invalid_arguments_error(
    parameters: dict[str, Any],
    message: str,
    *,
    lang: str = "en",
) -> dict[str, Any]:
    """Rich invalid-arg payload so the model can self-correct without blind retries."""
    props = parameters.get("properties") if isinstance(parameters.get("properties"), dict) else {}
    required = [str(x) for x in (parameters.get("required") or []) if str(x)]
    example = _example_from_schema(parameters or {})
    if str(lang or "").startswith("zh"):
        err = f"参数不合法: {message}"
        hint = "请按 example 修正参数后重试，不要用相同参数盲目重试。"
    else:
        err = f"Invalid arguments: {message}"
        hint = "Fix arguments to match the schema example; do not retry with the same payload."
    return {
        "ok": False,
        "error_code": "tool_invalid_arguments",
        "error": err,
        "validation_message": message,
        "required": required,
        "properties": sorted(str(k) for k in props.keys()),
        "example": example,
        "hint": hint,
    }


def validate_tool_arguments(parameters: dict[str, Any], arguments: dict[str, Any]) -> tuple[bool, str | None]:
    """校验模型给出的 arguments 是否符合工具的 JSON Schema（OpenAI function parameters）。"""
    if not isinstance(arguments, dict):
        return False, "arguments must be an object"

    schema = parameters or {}
    if not schema:
        return True, None

    if jsonschema is None or validators is None:
        # 依赖未安装时：不阻塞主流程（工具 handler 内仍可自行校验）。
        return True, None

    try:
        cls = validators.validator_for(schema)
        cls(schema).validate(arguments)
    except jsonschema.ValidationError as e:
        return False, e.message
    except Exception as e:
        return False, str(e)
    return True, None


__all__ = [
    "filter_arguments_to_schema",
    "format_invalid_arguments_error",
    "validate_tool_arguments",
]
