from __future__ import annotations

import json

from runtime.tools.public.bailian_webparser_tool import bailian_webparser_tool


class _SseResp:
    def __init__(self, lines: list[str]):
        self._lines = [x.encode("utf-8") for x in lines]

    def readline(self) -> bytes:
        if not self._lines:
            return b""
        return self._lines.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _PostResp:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_bailian_webparser_sse_flow(monkeypatch) -> None:
    sse_lines = [
        "event:endpoint\n",
        "data:/api/v1/mcps/WebParser/message?sessionId=abc\n",
        "\n",
        "event:message\n",
        'data:{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{"listChanged":true}},"serverInfo":{"name":"x","version":"1"}}}\n',
        "\n",
        "event:message\n",
        'data:{"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"webparser","description":"d","inputSchema":{"type":"object"}}]}}\n',
        "\n",
        "event:message\n",
        'data:{"jsonrpc":"2.0","id":3,"result":{"content":[{"type":"text","text":"parsed ok"}]}}\n',
        "\n",
    ]

    def _fake_open(req, timeout=0):  # noqa: ARG001
        method = str(getattr(req, "method", "") or "GET").upper()
        url = str(getattr(req, "full_url", "") or "")
        if method == "GET" and url.endswith("/WebParser/sse"):
            return _SseResp(sse_lines)
        if method == "POST" and "/message?sessionId=abc" in url:
            # Ensure request is valid JSON-RPC object.
            raw = getattr(req, "data", b"") or b""
            _ = json.loads(raw.decode("utf-8"))
            return _PostResp()
        raise AssertionError(f"unexpected request method={method} url={url}")

    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-test")
    monkeypatch.setattr("urllib.request.urlopen", _fake_open)

    out = bailian_webparser_tool().handler({"url": "https://example.com/x"})
    assert out.get("ok") is True, out
    assert out.get("tool_name") == "webparser"
    assert "parsed ok" in str(out.get("text") or "")


def test_bailian_webparser_requires_key(monkeypatch) -> None:
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    out = bailian_webparser_tool().handler({"url": "https://example.com/x"})
    assert out.get("ok") is False
    assert out.get("error_code") == "api_key_missing"


def test_bailian_webparser_missing_url_hint() -> None:
    out = bailian_webparser_tool().handler({})
    assert out.get("ok") is False
    assert out.get("error_code") == "url_required"
    assert "https://example.com/article" in str(out.get("error") or "")

