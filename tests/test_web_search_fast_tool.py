from __future__ import annotations

import json

from svc.config.runtime_paths import runtime_skills_root
from runtime.tools.public.web_search_fast_tool import _ENGINE_URLS, _normalize_engine_name, web_search_fast_tool


class _Resp:
    def __init__(self, body: str):
        self._body = body.encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_web_search_fast_api_success(monkeypatch) -> None:
    payload = {
        "Heading": "Python",
        "AbstractText": "Python is a programming language.",
        "AbstractURL": "https://www.python.org/",
        "RelatedTopics": [
            {"Text": "PyPI - Python packages", "FirstURL": "https://pypi.org/"},
        ],
    }

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=0: _Resp(json.dumps(payload)),  # noqa: ARG005
    )
    out = web_search_fast_tool().handler({"query": "python", "provider": "ddg_api"})
    assert out.get("ok") is True, out
    assert out.get("provider") == "ddg_api"
    assert int(out.get("count") or 0) >= 1


def test_web_search_fast_fallback_to_html(monkeypatch) -> None:
    html = """
    <html><body>
      <a class="result__a" href="https://example.com/a">Result A</a>
      <a class="result__snippet">Snippet A</a>
      <a class="result__a" href="https://example.com/b">Result B</a>
      <a class="result__snippet">Snippet B</a>
    </body></html>
    """
    state = {"n": 0}

    def _fake_open(req, timeout=0):  # noqa: ARG001
        state["n"] += 1
        return _Resp(html)

    monkeypatch.setattr("urllib.request.urlopen", _fake_open)
    out = web_search_fast_tool().handler({"query": "x", "provider": "auto"})
    assert out.get("ok") is True, out
    assert out.get("provider") == "ddg_html"
    assert int(out.get("count") or 0) >= 1
    attempts = list(out.get("provider_attempts") or [])
    assert attempts and attempts[0].get("provider") == "ddg_html"


def test_web_search_fast_fallback_to_bing_when_ddg_unavailable(monkeypatch) -> None:
    ddg_html_no_results = "<html><body><div>blocked</div></body></html>"
    bing_html = """
    <html><body>
      <li class="b_algo"><h2><a href="https://example.com/news1">News 1</a></h2><div class="b_caption"><p>Snippet 1</p></div></li>
      <li class="b_algo"><h2><a href="https://example.com/news2">News 2</a></h2><div class="b_caption"><p>Snippet 2</p></div></li>
    </body></html>
    """
    state = {"n": 0}

    def _fake_open(req, timeout=0):  # noqa: ARG001
        state["n"] += 1
        if state["n"] == 1:
            return _Resp(ddg_html_no_results)
        if state["n"] == 2:
            return _Resp(bing_html)
        raise RuntimeError("unexpected_call")

    monkeypatch.setattr("urllib.request.urlopen", _fake_open)
    out = web_search_fast_tool().handler({"query": "iran news", "provider": "auto"})
    assert out.get("ok") is True, out
    assert out.get("provider") == "bing_html"
    assert int(out.get("count") or 0) >= 1
    attempts = list(out.get("provider_attempts") or [])
    assert [x.get("provider") for x in attempts[:2]] == ["ddg_html", "bing_html"]


def test_web_search_fast_supports_engine_and_site(monkeypatch) -> None:
    captured = {"url": ""}
    bing_html = """
    <html><body>
      <li class="b_algo"><h2><a href="https://example.com/news1">News 1</a></h2><div class="b_caption"><p>Snippet 1</p></div></li>
    </body></html>
    """

    def _fake_open(req, timeout=0):  # noqa: ARG001
        captured["url"] = str(getattr(req, "full_url", "") or "")
        return _Resp(bing_html)

    monkeypatch.setattr("urllib.request.urlopen", _fake_open)
    out = web_search_fast_tool().handler({"query": "iran", "engine": "bing", "site": "reuters.com"})
    assert out.get("ok") is True, out
    assert str(out.get("provider") or "").startswith("engine:")
    assert "site%3Areuters.com+iran" in captured["url"] or "site:reuters.com+iran" in captured["url"]


def test_web_search_fast_engine_alias_from_skill_config_name(monkeypatch) -> None:
    captured = {"url": ""}
    bing_html = """
    <html><body>
      <li class="b_algo"><h2><a href="https://example.com/a">A</a></h2><div class="b_caption"><p>S</p></div></li>
    </body></html>
    """

    def _fake_open(req, timeout=0):  # noqa: ARG001
        captured["url"] = str(getattr(req, "full_url", "") or "")
        return _Resp(bing_html)

    monkeypatch.setattr("urllib.request.urlopen", _fake_open)
    out = web_search_fast_tool().handler({"query": "x", "engine": "Bing CN"})
    assert out.get("ok") is True, out
    assert out.get("provider") == "engine:bing_cn"
    assert "cn.bing.com/search" in captured["url"]


def test_web_search_fast_covers_all_multi_search_engine_config_names() -> None:
    config_path = (
        runtime_skills_root()
        / "_workspace"
        / "generalist"
        / "multi-search-engine"
        / "config.json"
    )
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    names = [str(x.get("name") or "").strip() for x in list(cfg.get("engines") or [])]
    assert names, "multi-search-engine config engines should not be empty"

    unsupported: list[str] = []
    for raw_name in names:
        norm = _normalize_engine_name(raw_name)
        if norm not in _ENGINE_URLS:
            unsupported.append(raw_name)
    assert not unsupported, f"unmapped engine names in config: {unsupported}"


def test_web_search_fast_failure_reports_category_and_attempts(monkeypatch) -> None:
    def _fake_open(req, timeout=0):  # noqa: ARG001
        raise RuntimeError("ssrf blocked by policy")

    monkeypatch.setattr("urllib.request.urlopen", _fake_open)
    out = web_search_fast_tool().handler({"query": "iran latest", "provider": "auto"})
    assert out.get("ok") is False, out
    assert out.get("error_code") == "search_failed"
    assert out.get("error_category") == "ssrf_blocked"
    attempts = list(out.get("provider_attempts") or [])
    assert attempts and attempts[0].get("provider") == "ddg_html"
    assert all("elapsed_ms" in x for x in attempts)


def test_web_search_fast_official_api_success(monkeypatch) -> None:
    payload = {
        "webPages": {
            "value": [
                {"name": "N1", "url": "https://example.com/n1", "snippet": "S1"},
                {"name": "N2", "url": "https://example.com/n2", "snippet": "S2"},
            ]
        }
    }
    monkeypatch.setenv("OCLAW_WEB_SEARCH_BING_API_KEY", "k")
    monkeypatch.setenv("OCLAW_WEB_SEARCH_BING_API_ENDPOINT", "https://api.bing.microsoft.com/v7.0/search")
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=0: _Resp(json.dumps(payload)))  # noqa: ARG005

    out = web_search_fast_tool().handler({"query": "ai", "provider": "official_api"})
    assert out.get("ok") is True, out
    assert out.get("provider") == "official_bing"
    assert int(out.get("count") or 0) == 2


def test_web_search_fast_official_api_missing_key(monkeypatch) -> None:
    monkeypatch.delenv("OCLAW_WEB_SEARCH_BING_API_KEY", raising=False)
    monkeypatch.delenv("OCLAW_WEB_SEARCH_OFFICIAL_API_KEY", raising=False)
    monkeypatch.delenv("OCLAW_WEB_SEARCH_GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("OCLAW_WEB_SEARCH_GOOGLE_CSE_ID", raising=False)
    out = web_search_fast_tool().handler({"query": "ai", "provider": "official_api"})
    assert out.get("ok") is False, out
    assert out.get("error_code") == "search_failed"
    assert out.get("error_category") == "auth_failed"
    attempts = list(out.get("provider_attempts") or [])
    assert attempts and attempts[0].get("provider") == "official_bing"


def test_web_search_fast_auto_prefers_official_api_when_configured(monkeypatch) -> None:
    state = {"n": 0}
    payload = {"webPages": {"value": [{"name": "N", "url": "https://example.com/n", "snippet": "S"}]}}

    def _fake_open(req, timeout=0):  # noqa: ARG001
        state["n"] += 1
        return _Resp(json.dumps(payload))

    monkeypatch.setenv("OCLAW_WEB_SEARCH_BING_API_KEY", "k")
    monkeypatch.setattr("urllib.request.urlopen", _fake_open)
    out = web_search_fast_tool().handler({"query": "ai", "provider": "auto"})
    assert out.get("ok") is True, out
    assert out.get("provider") == "official_bing"
    attempts = list(out.get("provider_attempts") or [])
    assert attempts and attempts[0].get("provider") == "official_bing"
    assert state["n"] == 1


def test_web_search_fast_official_google_success(monkeypatch) -> None:
    payload = {
        "items": [
            {"title": "G1", "link": "https://example.com/g1", "snippet": "GS1"},
            {"title": "G2", "link": "https://example.com/g2", "snippet": "GS2"},
        ]
    }
    monkeypatch.setenv("OCLAW_WEB_SEARCH_GOOGLE_API_KEY", "gk")
    monkeypatch.setenv("OCLAW_WEB_SEARCH_GOOGLE_CSE_ID", "cx")
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=0: _Resp(json.dumps(payload)))  # noqa: ARG005
    out = web_search_fast_tool().handler({"query": "ai", "provider": "official_google"})
    assert out.get("ok") is True, out
    assert out.get("provider") == "official_google"
    assert int(out.get("count") or 0) == 2


def test_web_search_fast_auto_can_prefer_google(monkeypatch) -> None:
    payload = {"items": [{"title": "G1", "link": "https://example.com/g1", "snippet": "GS1"}]}
    monkeypatch.setenv("OCLAW_WEB_SEARCH_GOOGLE_API_KEY", "gk")
    monkeypatch.setenv("OCLAW_WEB_SEARCH_GOOGLE_CSE_ID", "cx")
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=0: _Resp(json.dumps(payload)))  # noqa: ARG005
    out = web_search_fast_tool().handler({"query": "ai", "provider": "auto", "official_provider": "google"})
    assert out.get("ok") is True, out
    assert out.get("provider") == "official_google"

