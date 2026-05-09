from __future__ import annotations

from oclaw.platform.llm.tool_schema import complete_openai_tools_wire_parameters


def test_complete_tools_coerces_null_function_parameters_to_min_object_schema() -> None:
    raw = [
        {
            "type": "function",
            "function": {
                "name": "mcp__mcp-playwright__browser_click",
                "description": "click",
                "parameters": None,
            },
        }
    ]
    out = complete_openai_tools_wire_parameters(raw)
    assert len(out) == 1
    fn = out[0]["function"]
    params = fn["parameters"]
    assert isinstance(params, dict)
    assert params.get("type") == "object"
    assert params.get("required") == []
    assert params.get("properties") == {}
    assert "additionalProperties" in params


def test_complete_coerces_array_items_null_to_empty_object() -> None:
    raw = [
        {
            "type": "function",
            "function": {
                "name": "mcp__tusharemcp__adj_factor",
                "description": "x",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "codes": {"type": "array", "items": None, "description": "ids"},
                    },
                    "required": [],
                },
            },
        }
    ]
    out = complete_openai_tools_wire_parameters(raw)
    codes = out[0]["function"]["parameters"]["properties"]["codes"]
    assert codes.get("type") == "array"
    assert codes.get("items") == {}


def test_complete_drops_null_combo_keywords_and_fixes_lists() -> None:
    raw = [
        {
            "type": "function",
            "function": {
                "name": "demo",
                "description": "d",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {"anyOf": None, "description": "a"},
                        "y": {"allOf": None},
                        "z": {"prefixItems": None},
                    },
                    "required": [],
                },
            },
        }
    ]
    out = complete_openai_tools_wire_parameters(raw)
    props = out[0]["function"]["parameters"]["properties"]
    assert "anyOf" not in props["x"]
    assert props["y"].get("allOf") == []
    assert props["z"].get("prefixItems") == []


def test_complete_strips_null_entries_from_combo_arrays() -> None:
    raw = [
        {
            "type": "function",
            "function": {
                "name": "demo2",
                "description": "d",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {"anyOf": [None, {"type": "string"}]},
                    },
                    "required": [],
                },
            },
        }
    ]
    out = complete_openai_tools_wire_parameters(raw)
    assert out[0]["function"]["parameters"]["properties"]["x"]["anyOf"] == [{"type": "string"}]


def test_complete_fills_minimal_object_parameters_like_tier_minimal() -> None:
    raw = [
        {
            "type": "function",
            "function": {
                "name": "mcp__srv__ping",
                "description": "p",
                "parameters": {"type": "object", "additionalProperties": True},
            },
        }
    ]
    out = complete_openai_tools_wire_parameters(raw)
    params = out[0]["function"]["parameters"]
    assert params.get("type") == "object"
    assert params.get("required") == []
    assert params.get("properties") == {}


def test_complete_fills_object_type_when_null_with_properties() -> None:
    raw = [
        {
            "type": "function",
            "function": {
                "name": "x",
                "description": "",
                "parameters": {"type": None, "properties": {"a": {"type": "string"}}, "required": []},
            },
        }
    ]
    out = complete_openai_tools_wire_parameters(raw)
    params = out[0]["function"]["parameters"]
    assert params.get("type") == "object"
    assert "a" in params.get("properties", {})


def test_complete_removes_empty_anyof_after_null_strip() -> None:
    raw = [
        {
            "type": "function",
            "function": {
                "name": "demo3",
                "description": "d",
                "parameters": {
                    "type": "object",
                    "properties": {"x": {"anyOf": [None]}},
                    "required": [],
                },
            },
        }
    ]
    out = complete_openai_tools_wire_parameters(raw)
    assert "anyOf" not in out[0]["function"]["parameters"]["properties"]["x"]
