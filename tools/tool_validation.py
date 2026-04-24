from __future__ import annotations

from typing import Any

try:
    import jsonschema
    from jsonschema import validators
except Exception:  # pragma: no cover
    jsonschema = None
    validators = None


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


__all__ = ["validate_tool_arguments"]

