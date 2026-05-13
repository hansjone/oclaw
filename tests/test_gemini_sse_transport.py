from __future__ import annotations

import os

from svc.llm.transports.google_gemini_sse import GoogleGeminiChatModel


def test_gemini_tool_decl_uses_parameters_json_schema() -> None:
    m = GoogleGeminiChatModel(model="gemini-3.1-pro", api_key="x", base_url="http://gw")
    decls = m._tool_decls_from_openai_tools(
        [
            {
                "type": "function",
                "function": {
                    "name": "query_route",
                    "description": "d",
                    "parameters": {"type": "object", "properties": {"destination": {"type": "string"}}},
                },
            }
        ]
    )
    assert decls and "parametersJsonSchema" in decls[0]
    assert "parameters" not in decls[0]


def test_gemini_thinking_config_env_off() -> None:
    os.environ["AIA_GEMINI_THINKING"] = "off"
    cfg = GoogleGeminiChatModel._thinking_config_from_env()
    assert cfg == {"includeThoughts": False}

