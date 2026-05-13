from __future__ import annotations

from typing import Any

import pytest


def test_netx_query_ume_ne_inventory_forwards_params(monkeypatch: pytest.MonkeyPatch) -> None:
    import runtime.tools.experts.network_ops.netx_tools as nt

    calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def fake(method: str, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        calls.append((method, path, params))
        return {"ok": True, "data": {"total": 0, "page": 1, "page_size": 50, "items": []}}

    monkeypatch.setattr(nt, "_http_json", fake)
    spec = nt.netx_query_ume_ne_inventory_tool()
    out = spec.handler({"keyword": "10.0.0", "page": 2, "page_size": 100})
    assert out.get("ok") is True
    assert len(calls) == 1
    assert calls[0][0] == "GET"
    assert calls[0][1] == "/v1/ume/inventory/ne"
    assert calls[0][2] == {"page": 2, "page_size": 100, "keyword": "10.0.0"}


def test_netx_get_ume_ne_requires_id(monkeypatch: pytest.MonkeyPatch) -> None:
    import runtime.tools.experts.network_ops.netx_tools as nt

    monkeypatch.setattr(nt, "_http_json", lambda *a, **k: {"ok": True, "data": {}})
    spec = nt.netx_get_ume_ne_tool()
    out = spec.handler({})
    assert out.get("ok") is False
    assert out.get("error_code") == "ne_id_required"


def test_netx_get_ume_ne_quotes_path(monkeypatch: pytest.MonkeyPatch) -> None:
    import runtime.tools.experts.network_ops.netx_tools as nt

    paths: list[str] = []

    def fake(method: str, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        paths.append(path)
        return {"ok": True, "data": {"ne_id": "x"}}

    monkeypatch.setattr(nt, "_http_json", fake)
    spec = nt.netx_get_ume_ne_tool()
    nid = "550e8400-e29b-41d4-a716-446655440000"
    spec.handler({"ne_id": nid})
    assert paths == [f"/v1/ume/inventory/ne/{nid}"]
