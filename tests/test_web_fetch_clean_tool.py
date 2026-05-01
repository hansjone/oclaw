from __future__ import annotations

from oclaw.runtime.tools.public.web_fetch_clean_tool import web_fetch_clean_tool


class _Resp:
    def __init__(self, body: bytes, *, status: int = 200, headers: dict[str, str] | None = None):
        self._body = body
        self.status = status
        self.headers = headers or {"content-type": "text/html; charset=utf-8"}

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_web_fetch_clean_html_strip(monkeypatch) -> None:
    html = b"""
    <html><head><title> Hello </title><style>.x{}</style></head>
    <body><h1>Title</h1><p>Para <b>one</b>.</p><script>alert(1)</script></body></html>
    """

    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=0: _Resp(html))  # noqa: ARG005
    out = web_fetch_clean_tool().handler({"url": "https://example.com"})
    assert out.get("ok") is True, out
    assert out.get("title") == "Hello"
    text = str(out.get("text") or "")
    assert "Para" in text
    assert "one" in text
    assert "alert" not in str(out.get("text") or "")


def test_web_fetch_clean_http_error(monkeypatch) -> None:
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=0: _Resp(b"no", status=403))  # noqa: ARG005
    out = web_fetch_clean_tool().handler({"url": "https://example.com"})
    # Our stub doesn't raise HTTPError; status is checked and returns http_error.
    assert out.get("ok") is False
    assert out.get("error_code") == "http_error"
