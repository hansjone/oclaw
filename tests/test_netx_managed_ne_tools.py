from __future__ import annotations

from typing import Any

import pytest


def test_netx_list_managed_ne_forwards_params(monkeypatch: pytest.MonkeyPatch) -> None:
    import runtime.tools.experts.network_ops.netx_tools as nt

    calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def fake(method: str, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        calls.append((method, path, params))
        return {"ok": True, "data": {"total": 0, "items": []}}

    monkeypatch.setattr(nt, "_http_json", fake)
    spec = nt.netx_list_managed_ne_tool()
    out = spec.handler({"keyword": "192.168", "connect_status": "pass", "page": 1, "page_size": 20})
    assert out.get("ok") is True
    assert calls[0] == ("GET", "/v1/managed-ne", {"page": 1, "page_size": 20, "keyword": "192.168", "connect_status": "pass"})


def test_netx_exec_managed_ne_posts_body(monkeypatch: pytest.MonkeyPatch) -> None:
    import runtime.tools.experts.network_ops.netx_tools as nt

    bodies: list[dict[str, Any]] = []

    def fake_post(path: str, body: dict[str, Any], *, timeout: float = 180.0) -> dict[str, Any]:
        bodies.append(body)
        return {"ok": True, "data": {"ok": True, "output": "R2#show version\n..."}}

    monkeypatch.setattr(nt, "_http_post_json", fake_post)
    spec = nt.netx_exec_managed_ne_tool()
    out = spec.handler({"ne_id": "abc", "commands": ["show version"], "read_timeout_sec": 90})
    assert out.get("ok") is True
    assert bodies[0]["ne_id"] == "abc"
    assert bodies[0]["commands"] == ["show version"]
    assert bodies[0]["read_timeout_sec"] == 90


def test_netx_exec_requires_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    import runtime.tools.experts.network_ops.netx_tools as nt

    monkeypatch.setattr(nt, "_http_post_json", lambda *a, **k: {"ok": True, "data": {}})
    spec = nt.netx_exec_managed_ne_tool()
    out = spec.handler({"ne_id": "abc"})
    assert out.get("ok") is False
    assert out.get("error_code") == "commands_required"
